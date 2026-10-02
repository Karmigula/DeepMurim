"""A typed line the engine did not know, asked of the model and waited for (phase 6 spec 14.1-14.6).

`start` builds the prompt on the game's thread and asks in a daemon thread; `poll` (every frame) hands back the
answer once it has come or the wait is over; `cancel` lets it go (Esc). `resolve` checks the proposals, commits what
stands, and says what to show: the model's paragraph, and in assist mode the engine's line for each change. Any
failure changes nothing and says so.
"""

import hashlib
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass

from ai import deeds as D
from ai.guard import refusal
from ai.intent import TALK_LINES, dialogue_job, dialogue_prompt, intent_job, intent_prompt, timeout_for
from ai.narrate import RECENT, unwrap
from ai.validate import DIALOGUE_KINDS, KINDS, Scene, accept

GRACE = 5.0  # past the job's own timeout, the wait is over even if the worker never answers
HESITATE = ("You hesitate; nothing comes of it.", "dim")
AMISS = ("You try, but it does not go as you meant.", "dim")


@dataclass
class Waiting:
    typed: str
    job: object
    future: Future
    began: float
    talk_to: int | None  # the person spoken to (a conversation), or None (a typed action)
    prompt: str
    who: str             # the backend's name, for the waiting line


class Typed:
    def __init__(self, narration, clock=time.monotonic) -> None:
        self.narration = narration  # its backend, mode and recent paragraphs are shared
        self.clock = clock
        self.waiting: Waiting | None = None
        self.talk: tuple[int | None, list[str]] = (None, [])  # the conversation so far, with whom
        self.last: dict = {}  # the last exchange, as the overlay and the session log keep it

    def ready(self) -> bool:
        """Whether a typed line may be asked of the model now (the AI on, its backend able)."""
        n = self.narration
        if n.mode == "off" or n.unavailable() is not None:
            return False
        paused = getattr(n.bridge, "paused", None)
        return not (callable(paused) and paused())

    def start(self, game, typed: str, choices: list) -> None:
        bridge = self.narration.bridge
        timeout, recent = timeout_for(bridge), self.narration.recent
        if game.focus is not None:
            job, prompt = dialogue_job(timeout), dialogue_prompt(game, typed, game.focus, self._talk(game.focus),
                                                                   recent)
        else:
            job, prompt = intent_job(timeout), intent_prompt(game, typed, choices, recent)
        future: Future = Future()

        def work() -> None:
            if not future.set_running_or_notify_cancel():
                return
            try:
                future.set_result(bridge.call(job, prompt))
            except BaseException as exc:  # handed to `poll`: the world stays as it was
                future.set_exception(exc)
        threading.Thread(target=work, name="typed", daemon=True).start()
        self.waiting = Waiting(typed, job, future, self.clock(), game.focus, prompt,
                               getattr(bridge, "name", None) or "Claude")

    def poll(self):
        """(waiting, reply) once the answer has come or the wait is over (reply None: it failed); else None."""
        w = self.waiting
        if w is None:
            return None
        if w.future.done():
            try:
                reply = w.future.result()
            except Exception:
                reply = None
        elif self.clock() - w.began > w.job.timeout + GRACE:
            reply = None
        else:
            return None
        self.waiting = None
        return w, reply

    def cancel(self) -> Waiting | None:
        """Esc: the wait is let go; an answer that comes after is never read."""
        w, self.waiting = self.waiting, None
        if w is not None:
            w.future.cancel()
        return w

    def _talk(self, person: int) -> list[str]:
        with_whom, lines = self.talk
        return lines if with_whom == person else []

    def resolve(self, game, w: Waiting, reply, choices: list, mode: str):
        """(the turn or None, the lines to show). Accepted changes are committed even when the paragraph is not
        shown: they are what really happened."""
        record = {"job": w.job.name, "typed": w.typed, "prompt": w.prompt, "reply": reply, "accepted": [],
                  "rejected": [], "refused": None, "seconds": round(self.clock() - w.began, 2)}
        self.last = record
        if not isinstance(reply, dict):
            record["refused"] = "no reply"
            return None, [HESITATE]
        world, me, here = game.world, game.player.id, game.place.id
        dialogue = w.talk_to is not None
        salt = f"{world.time}:{hashlib.sha1(w.typed.encode()).hexdigest()[:8]}"
        done = accept(Scene(world, me, here, list(choices), salt), reply.get("proposals"),
                      DIALOGUE_KINDS if dialogue else KINDS)
        events = list(done.events)
        prose = unwrap(str(reply.get("reply" if dialogue else "prose") or ""))
        if dialogue:
            summary = " ".join(str(reply.get("summary") or "").split())
            if not summary or refusal(world, summary, me, here, w.prompt) is not None:
                summary = "They spoke with you."
            events.append(D.talked(me, w.talk_to, here, summary, w.typed))
        turn = game.apply_proposals(events, done.action)
        given = w.prompt + "\n" + "\n".join(text for text, _ in turn.lines)
        why = refusal(world, prose, me, here, given) if prose else "no prose"
        record.update(accepted=[e.data.get("proposal", {"kind": e.kind}) for e in events],
                      rejected=[[p, reason] for p, reason in done.rejected], refused=why)
        if why is not None:
            return turn, list(turn.lines) + [AMISS]
        self.narration.recent = (self.narration.recent + [prose])[-RECENT:]
        if dialogue:
            name = world.entity(w.talk_to).name
            _, lines = self.talk if self.talk[0] == w.talk_to else (None, [])
            self.talk = (w.talk_to, (lines + [f"You: {w.typed}", f"{name}: {prose}"])[-TALK_LINES:])
        return turn, [(prose, "prose")] + ([] if mode == "ai_only" else list(turn.lines))
