"""Claude's prose for each turn (phase 6 spec 3, 6): asked for in a worker thread, shown when it comes.

One request per turn, over all of the turn's briefs (plan ruling 3): a turn reads as one passage, and a turn costs
one call. The prompt is built on the main thread (the world's connection belongs to it); only `claude -p` runs in
the worker. A reply is guarded, then replaces the turn's procedural lines in the log (assist) or its "…"
(ai_only). Anything that goes wrong leaves the procedural text where it is.
"""

import json
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field

from ai.bridge import Bridge, Job
from ai.guard import refusal
from ai.pack import build_pack

MODES = ("off", "assist", "ai_only")
MODE_WORDS = {"off": "AI prose off", "assist": "AI prose: procedural first, then Claude's",
              "ai_only": "AI prose only"}
MODEL, TIMEOUT = "claude-haiku-4-5", 10.0  # a prose call takes about 4 s without thinking (plan ruling 2)
WAITING = ("…", "dim")
RECENT = 3
PROSE_SCHEMA = {"type": "object", "properties": {"prose": {"type": "string", "maxLength": 900}},
                "required": ["prose"], "additionalProperties": False}
SYSTEM = (
    "You are the narrator of DeepMurim, a wuxia text game. Rewrite the turn below as 1-4 sentences of vivid "
    "second-person prose in the register of a wuxia novel. Use only what the EVENT blocks and the STATE say: add no "
    "person, item, place, number or outcome they do not carry, and never contradict an OUTCOME line. Keep names "
    "exactly as given, and keep every number an OUTCOME line states, written as digits. Do not address the "
    "player as 'the player'. "
    "Reply with JSON: {\"prose\": \"...\"}."
)


def narrate_job(model: str = MODEL, timeout: float = TIMEOUT) -> Job:
    return Job("narrate", model, timeout, PROSE_SCHEMA, SYSTEM)


def turn_prompt(briefs, pack: str, recent: list[str]) -> str:
    events = "\n\n".join(b.to_prompt() for b in briefs)
    told = "\n".join(f"- {line}" for line in recent[-RECENT:]) or "- (the story begins)"
    return f"STATE:\n{pack}\n\nTOLD JUST BEFORE:\n{told}\n\nTHIS TURN:\n{events}"


def unwrap(prose: str) -> str:
    """The prose itself, even when a reply wraps it in JSON a second time (seen with Haiku)."""
    prose = prose.strip()
    if prose.startswith("{"):
        try:
            inner = json.loads(prose)
        except ValueError:
            return prose
        if isinstance(inner, dict) and isinstance(inner.get("prose"), str):
            return inner["prose"].strip()
    return prose


@dataclass
class Pending:
    start: int                 # where the turn's lines begin in the log
    lines: list                # the turn's lines as the engine made them
    narrated: list[int]        # which of them the narrator wrote
    key: tuple
    given: str                 # all Claude was told: the guard's measure
    future: Future | None
    shown: list = field(default_factory=list)  # what the log holds for the turn now
    prompt: str = ""


class Narration:
    def __init__(self, bridge: Bridge | None = None, mode: str = "off", factory=None) -> None:
        self._bridge = bridge
        self._factory = factory  # makes the backend the settings name (phase 6b); a plain Bridge without one
        self.mode = mode if mode in MODES else "off"
        self.job = narrate_job()
        self.cache: dict[tuple, str] = {}
        self.pending: Pending | None = None
        self.refused: str | None = None  # why the last reply was not shown (the debug overlay)
        self.last: dict = {}  # the last exchange as the session log keeps it: asked, answered, shown
        self.recent: list[str] = []
        self.worker: threading.Thread | None = None  # a daemon: it never holds the game open (6a minors)

    @property
    def bridge(self) -> Bridge:
        if self._bridge is None:
            self._bridge = self._factory() if self._factory is not None else Bridge()
        return self._bridge

    def set_backend(self, backend) -> None:
        """Another backend (phase 6b's menu): the old one is closed; None makes the next use build anew."""
        old, self._bridge = self._bridge, backend
        if old is not None and old is not backend and hasattr(old, "close"):
            old.close()

    def cycle(self) -> str:
        self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
        return self.mode

    def unavailable(self) -> str | None:
        """Why the AI modes cannot be used (None: they can)."""
        ok, why = self.bridge.available()
        return None if ok else why

    def close(self) -> None:
        """Nothing to wait for: a request still out runs on a daemon thread and dies with the game."""
        self.pending = None
        if self._bridge is not None and hasattr(self._bridge, "close"):
            self._bridge.close()  # a warm OpenCode server, an open Claude Code session

    def reset(self) -> None:
        """A game is closed: its prose is no one else's (6a minors)."""
        self.cache.clear()
        self.recent, self.pending, self.refused, self.last = [], None, None, {}

    def _ask(self, prompt: str) -> Future:
        future: Future = Future()

        def work() -> None:
            if not future.set_running_or_notify_cancel():
                return
            try:
                future.set_result(self.bridge.call(self.job, prompt))
            except BaseException as exc:  # handed to `poll`, which puts the engine's words back
                future.set_exception(exc)
        self.worker = threading.Thread(target=work, name="claude", daemon=True)
        self.worker.start()
        return future

    # --- a turn ------------------------------------------------------------------------------------------------
    def start(self, log: list, start: int, turn, game) -> None:
        """A turn has just been put in the log at `start`: ask for its prose (and in ai_only, hide its lines).
        The caller settles the turn before (`settle`) before it puts this one in the log, so `start` holds."""
        narrated = list(getattr(turn, "narrated", []))
        if self.mode == "off" or not narrated or not game.last_briefs or self.unavailable():
            return
        me = game.player
        if me.data.get("dying") or me.data.get("dead") or not game.world.targets(me.id, "located_in"):
            return  # the death screen keeps the engine's words (6a review)
        lines = list(turn.lines)
        pack = build_pack(game)
        prompt = turn_prompt(game.last_briefs, pack, self.recent)
        given = prompt + "\n" + "\n".join(t for t, _ in lines)
        key = tuple((b.seed, b.salt, b.kind) for b in game.last_briefs)
        pending = Pending(start, lines, narrated, key, given, None, lines, prompt)
        if key in self.cache:
            _put(log, pending, _without(pending), prose=self.cache[key])
            return
        if self.mode == "ai_only":
            _put(log, pending, _without(pending, WAITING))
        pending.future = self._ask(prompt)
        self.pending = pending

    def poll(self, log: list, game) -> list:
        """Apply a reply that has come (called every frame). Returns lines to add to the log (notices)."""
        notices = []
        if getattr(self.bridge, "just_paused", False):
            self.bridge.just_paused = False
            notices.append(("Claude has failed three times; its prose rests for five minutes.", "dim"))
        pending = self.pending
        if pending is None or not pending.future.done():
            return notices
        self.pending = None
        try:
            reply = pending.future.result()
            prose = unwrap(reply.get("prose", "")) if reply else ""
            needed = "\n".join(pending.lines[i][0] for i in pending.narrated)
            why = refusal(game.world, prose, game.player.id, game.place.id, pending.given, needed) if prose \
                else "no prose"
        except Exception as exc:  # the worker broke: the engine's words stand (6a review)
            reply, prose, why = None, "", f"the request failed ({exc.__class__.__name__})"
        if why is None:
            self.cache[pending.key] = prose
            _put(log, pending, _without(pending), prose=prose)
            self.recent = (self.recent + [prose])[-RECENT:]
        else:
            _put(log, pending, pending.lines)  # the procedural text stands
        self.refused = why
        exchange = self.bridge.exchanges[-1] if self.bridge.exchanges else None
        self.last = {"prompt": pending.prompt, "reply": reply, "shown": prose if why is None else None,
                     "refused": why, "error": exchange.error if exchange else "",
                     "seconds": exchange.seconds if exchange else 0.0}
        off = self.unavailable()
        if off is not None and self.mode != "off":
            self.mode = "off"
            notices.append((f"Claude's prose is off: {off}.", "system"))
        return notices

    def settle(self, log: list) -> None:
        """A turn left before its prose came: in ai_only its procedural text is put back."""
        pending, self.pending = self.pending, None
        if pending is None:
            return
        pending.future.cancel()
        _put(log, pending, pending.lines)


# --- the log ----------------------------------------------------------------------------------------------------
def _without(p: Pending, placeholder=None) -> list:
    """The turn's lines with the narrated ones taken out (and a placeholder where the first was)."""
    out = []
    for i, line in enumerate(p.lines):
        if i == p.narrated[0] and placeholder is not None:
            out.append(placeholder)
        if i not in p.narrated:
            out.append(line)
    return out


def _put(log: list, p: Pending, lines: list, prose: str | None = None) -> None:
    """Put these lines where the turn's lines are now (with the prose where its first narrated line was)."""
    if prose is not None:
        at = p.narrated[0]
        lines = lines[:at] + [(prose, "prose")] + lines[at:]
    end = p.start + len(p.shown)
    if log[p.start:end] == p.shown:  # the log still holds the turn where it was
        log[p.start:end] = lines
        p.shown = lines
