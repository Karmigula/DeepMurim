# Phase 6a: The Claude Layer's Foundation and Narration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude can write the game's prose. A turn shows the engine's text at once and Claude's prose in its place when it comes (assist), or only Claude's prose (ai_only). Everything runs, and every test passes, without Claude.

**Architecture:**
- **`ai/bridge.py`:** the one door to `claude -p`. A `Job` names the model, timeout, schema and system prompt. Every failure returns `None`, and three in a row pause the door.
- **`ai/fake.py`:** `FakeClaude` answers tests from a script through the same `call(job, prompt)`.
- **`ai/pack.py`:** the state pack, built from pages the player can already read.
- **`mcp_server/`:** read-only tools over `World.open_readonly`, as the player knows the world. They serve the Sonnet jobs of 6b, and are built and tested now.
- **`ai/narrate.py`:** `Narration` asks once per turn, in a worker thread, over the lines `Game` marks as the narrator's (`Turn.narrated`).
- **`ai/guard.py`:** refuses prose that brings anything in.
- **`App`:** settles, starts and polls narration; the main loop polls every frame.

**Tech Stack:** Python 3.14, SQLite, pytest, the Claude Code CLI (`claude -p`), the `mcp` Python SDK 2.x (`MCPServer`, `ClientSession`, `stdio_client`).

**Spec:** `docs/superpowers/specs/2026-10-01-phase6-claude-layer-design.md` (sections 2-6, 8, 10-11; 6b's sections 7 and 9 are not in this plan)

## Global Constraints

- **Claude never writes the world.** In 6a, nothing Claude returns reaches the database; prose is display only.
- **Without Claude, everything works.**
  - Every failure (no CLI, logged out, offline, a timeout, bad JSON, a misfit reply) leaves the procedural text standing.
  - No test calls the real CLI except `tests/test_ai_live.py`, which is marked `live` and needs `DEEPMURIM_LIVE=1`.
- **Off costs nothing.** With `ai_mode = "off"` (the default), a turn starts no thread, builds no pack, and calls nothing.
- **Knowledge vs truth:** the pack and the MCP tools show only what the player could read on a page. They show no entity ids, and no person the player has not heard of except those present.
- **Speed:** the pack is built in under 15 ms; each MCP tool answers in under 30 ms; prose is cached per turn.
- **Dependency:** `mcp>=2.2` joins `requirements.txt`.
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The player acts again before Claude's prose comes** (ai_only shows "…"): the waiting turn gets its own text back, and the late prose never lands on the wrong turn. Task 4 pins it with `test_acting_before_the_prose_comes_puts_the_text_back`.
2. **Prose that drops or invents an outcome** ("you pay the man" for "you pay 30 silver"; a stranger's name): it is refused and the procedural text stands. Task 4 pins it with `test_prose_that_brings_in_a_stranger_or_a_number_is_refused`.
3. **A save read while the game is running:** the MCP server never writes, and the save's bytes are unchanged. Task 3 pins it with `test_no_answer_carries_an_id_and_none_writes`.
4. **A machine without Claude Code installed or logged in:** F1 says why and stays off. Task 4 pins it with `test_without_claude_the_modes_stay_off_and_say_why`.
5. **A dead backend:** three failures pause it for five minutes, said once. Task 1 pins it with `test_three_failures_in_a_row_pause_the_door_for_five_minutes`; Task 4 with `test_a_pause_is_told_once`.

## Plan-time rulings (deviations from the spec, argued)

1. **F1 cycles the AI mode, not F3:** F3 already hides the art frame. *Cost if wrong:* none.
2. **The CLI is run stripped bare, with thinking off.**
   - Measured: a bare `claude -p` loaded the user's whole setup (CLAUDE.md, plugins, skills, hooks, MCP servers) and cost 20 s and $0.30 a call.
   - `--setting-sources "" --disable-slash-commands --strict-mcp-config --tools "" --effort low`, with `MAX_THINKING_TOKENS=0` in its environment, makes a prose call about 4 s and $0.003.
   - `--bare` was not used: it reads only an API key, never the subscription's login.
   - A `Job` may ask for thinking (`thinking=True`) in 6b.
   - *Cost if wrong:* none measured.
3. **Prose is asked once per turn, over all of the turn's briefs,** not once per brief as a `Narrator` would. A turn reads as one passage, and costs one call. *Cost if wrong:* a long turn's prose is a little coarser.
4. **The prose timeout is 10 s, not 8:** measured calls took 3.8-4.7 s, after the cold start of the CLI. *Cost if wrong:* an ai_only turn waits 2 s longer before falling back.
5. **The guard also refuses prose that drops a number its lines carried** (silver, merit, days). Replacing the narrator's lines replaces their outcome lines too, and an outcome must not be lost. *Cost if wrong:* some good prose is refused.
6. **Prose wrapped in JSON a second time is unwrapped:** Haiku did so once in four measured calls. *Cost if wrong:* none.
7. **The MCP server's viewer is the save's player, fixed at start,** and its tools take names, not ids. A read the read-only world refuses (one that would write) is told as "That is not known." *Cost if wrong:* none.
8. **The fork guide's section is 16, not 13:** sections 12-15 are phase 5's. *Cost if wrong:* none.

## Files

| File | Responsibility |
|---|---|
| `ai/bridge.py`, `ai/fake.py` | `Job`, `Bridge.call`, `conforms`, the pause; `FakeClaude`. |
| `ai/pack.py` | `build_pack(game)`: HERE, LIMITS, CARRYING, LATELY, YOU. |
| `mcp_server/tools.py`, `mcp_server/server.py`, `ai/mcp_config.py` | The read-only tools, the stdio server, and the config `claude -p` is given. |
| `ai/guard.py`, `ai/narrate.py` | `refusal`; `Narration` (modes, the worker, the cache, the log). |

Existing files touched: `world/db.py` (`open_readonly`), `engine/actions.py` (`Turn.narrated`), `engine/game.py`, `app.py`, `main.py`, `config.py`, `requirements.txt`, `pytest.ini`, `docs/world-events.md`.

**How each task is laid out:**
1. The tests, as whole new files.
2. The red run.
3. The new modules, as whole files.
4. One patch script, `.patches/6a_taskN.py`, holding the task's edits to existing files. Each edit asserts that its anchor matches exactly once.
5. The green run, the full suite, and the commit.

---

### Task 1: The door to Claude: the bridge and FakeClaude

One `claude -p` call per request, stripped bare and with thinking off (ruling 2), its reply checked against the job's schema. Every failure returns None and is remembered; three in a row pause the door for five minutes. `FakeClaude` answers tests from a script through the same `call(job, prompt)`.

**Files:**
- Create: `ai/__init__.py`
- Create: `ai/bridge.py`
- Create: `ai/fake.py`
- Create: `tests/test_ai_bridge.py`

**Interfaces:**
- Consumes: Nothing of the engine: the `claude` CLI on PATH (looked up with `shutil.which`).
- Produces:
  - `ai.bridge`: `PAUSE_AFTER = 3`, `PAUSE_SECONDS = 300.0`, `KEPT = 20`, `FIND`; `Job(name, model, timeout, schema, system, tools=False, thinking=False)`; `Exchange(job, prompt, reply, error, seconds, at)`; `conforms(schema, value) -> bool`; `Bridge(cli=FIND, runner=subprocess.run, mcp_config=None, clock=time.monotonic)` with `available() -> (bool, str)`, `paused()`, `command(job) -> list[str]`, `env(job) -> dict`, `call(job, prompt) -> dict | None`, `exchanges`, `just_paused`, `failures`, `paused_until`.
  - `ai.fake.FakeClaude(*replies, available=True)` with `call`, `available`, `paused`, `add`, `calls`, `exchanges`, `just_paused`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_bridge.py`:
```python
import json
import subprocess

from ai.bridge import PAUSE_AFTER, PAUSE_SECONDS, Bridge, Job, conforms
from ai.fake import FakeClaude

PROSE = {"type": "object", "properties": {"prose": {"type": "string", "maxLength": 600}}, "required": ["prose"],
         "additionalProperties": False}
JOB = Job("narrate", "claude-haiku-4-5", 8.0, PROSE, "Write prose.")
TOOLED = Job("intent", "claude-sonnet-5", 30.0, PROSE, "Interpret.", tools=True)


class Runner:
    """Stands in for subprocess.run: answers `--version`, then each request from its script."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        if cmd[1:] == ["--version"]:
            return subprocess.CompletedProcess(cmd, 0, "2.1.286 (Claude Code)", "")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        code, out = outcome
        return subprocess.CompletedProcess(cmd, code, out, "boom" if code else "")


def ok(reply: dict) -> tuple[int, str]:
    return 0, json.dumps({"type": "result", "is_error": False, "result": json.dumps(reply), "structured_output": reply})


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_a_reply_that_fits_its_schema_comes_back():
    runner = Runner(ok({"prose": "Mist curls over the pass."}))
    bridge = Bridge(cli="claude", runner=runner)
    assert bridge.call(JOB, "a brief") == {"prose": "Mist curls over the pass."}
    cmd, kw = runner.calls[-1]
    assert kw["input"] == "a brief" and kw["timeout"] == 8.0 and kw["env"]["MAX_THINKING_TOKENS"] == "0"
    assert cmd[:4] == ["claude", "-p", "--model", "claude-haiku-4-5"]
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == PROSE


def test_the_call_is_stripped_bare_and_tools_only_when_asked(tmp_path):
    runner = Runner(ok({"prose": "a"}), ok({"prose": "b"}))
    config = tmp_path / "deepmurim.json"
    bridge = Bridge(cli="claude", runner=runner, mcp_config=config)
    bridge.call(JOB, "x")
    bridge.call(TOOLED, "y")
    plain, tooled = runner.calls[1][0], runner.calls[2][0]
    for cmd in (plain, tooled):
        for flag in ("--setting-sources", "--disable-slash-commands", "--no-session-persistence", "--strict-mcp-config"):
            assert flag in cmd, flag
        assert cmd[cmd.index("--tools") + 1] == "" and cmd[cmd.index("--effort") + 1] == "low"
    assert "--allowedTools" not in plain and json.loads(plain[plain.index("--mcp-config") + 1]) == {"mcpServers": {}}
    assert tooled[tooled.index("--mcp-config") + 1] == str(config)
    assert tooled[tooled.index("--allowedTools") + 1] == "mcp__deepmurim__*"


def test_every_failure_is_none_and_remembered():
    runner = Runner((1, ""), (0, "not json"), ok({"verse": "wrong shape"}), subprocess.TimeoutExpired("claude", 8),
                    (0, json.dumps({"is_error": True, "result": "rate limited"})))
    bridge = Bridge(cli="claude", runner=runner)
    results = []
    for _ in range(5):
        bridge.paused_until = 0.0  # the pause is tested on its own
        results.append(bridge.call(JOB, "x"))
    assert results == [None] * 5
    errors = [e.error for e in bridge.exchanges]
    assert errors == ["boom", "the reply was not JSON", "the reply did not fit its schema", "no reply within 8 s",
                      "rate limited"]


def test_no_cli_means_no_call():
    runner = Runner()
    bridge = Bridge(cli=None, runner=runner)
    assert bridge.available() == (False, "the claude command is not installed")
    assert bridge.call(JOB, "x") is None and runner.calls == []


def test_three_failures_in_a_row_pause_the_door_for_five_minutes():
    clock = Clock()
    runner = Runner(*([(1, "")] * PAUSE_AFTER), ok({"prose": "back"}))
    bridge = Bridge(cli="claude", runner=runner, clock=clock)
    for _ in range(PAUSE_AFTER):
        assert bridge.call(JOB, "x") is None
    assert bridge.paused() and bridge.just_paused
    assert bridge.call(JOB, "x") is None and len(runner.calls) == 1 + PAUSE_AFTER  # not even tried
    clock.now += PAUSE_SECONDS + 1
    assert bridge.call(JOB, "x") == {"prose": "back"} and bridge.failures == 0


def test_a_success_between_failures_resets_the_count():
    runner = Runner((1, ""), (1, ""), ok({"prose": "fine"}), (1, ""), (1, ""))
    bridge = Bridge(cli="claude", runner=runner)
    for _ in range(5):
        bridge.call(JOB, "x")
    assert not bridge.paused() and bridge.failures == 2


def test_thinking_is_off_unless_the_job_asks_for_it():
    thinking = Job("intent", "claude-sonnet-5", 30.0, PROSE, "Think.", thinking=True)
    assert Bridge.env(JOB)["MAX_THINKING_TOKENS"] == "0"
    assert "MAX_THINKING_TOKENS" not in Bridge.env(thinking) or Bridge.env(thinking)["MAX_THINKING_TOKENS"] != "0"


def test_the_schema_check():
    schema = {"type": "object", "properties": {"kind": {"type": "string", "enum": ["pay", "give"]},
                                               "amount": {"type": "integer"},
                                               "items": {"type": "array", "items": {"type": "string"}, "maxItems": 2}},
              "required": ["kind"], "additionalProperties": False}
    assert conforms(schema, {"kind": "pay", "amount": 3, "items": ["a"]})
    assert not conforms(schema, {"kind": "steal"})
    assert not conforms(schema, {"kind": "pay", "amount": True})
    assert not conforms(schema, {"kind": "pay", "items": ["a", "b", "c"]})
    assert not conforms(schema, {"kind": "pay", "extra": 1})
    assert not conforms(schema, {})
    assert not conforms(PROSE, {"prose": "x" * 601})


def test_fake_claude_scripts_replies_and_failures():
    fake = FakeClaude({"prose": "one"}, None, lambda job, prompt: {"prose": prompt.upper()}, {"wrong": 1})
    assert fake.call(JOB, "a") == {"prose": "one"}
    assert fake.call(JOB, "b") is None
    assert fake.call(JOB, "c") == {"prose": "C"}
    assert fake.call(JOB, "d") is None  # does not fit its schema
    assert fake.call(JOB, "e") is None  # the script ran out
    assert [c[1] for c in fake.calls] == ["a", "b", "c", "d", "e"]
    assert FakeClaude(available=False).available()[0] is False
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_bridge.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'ai'`.

- [ ] **Step 3: Write the new modules**

`ai/__init__.py`:
```python
"""The Claude layer (phase 6): Claude proposes and writes prose; the engine keeps every fact."""
```

`ai/bridge.py`:
```python
"""The one door to Claude (phase 6 spec 2, 8): `claude -p` run once per request, its reply checked against a schema.

Every failure (no CLI, logged out, offline, a timeout, bad JSON, a reply that does not fit) returns None, and the
caller keeps its procedural text. Three failures in a row pause the door for five minutes.

The CLI is run stripped bare (plan ruling 2): no settings, skills, hooks or MCP servers of the user's own, no
built-in tools, and low effort, so a prose call costs about a thousand tokens and a few seconds instead of the
whole of the user's setup.
"""

import json
import os
import shutil
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

PAUSE_AFTER, PAUSE_SECONDS = 3, 300.0
KEPT = 20  # exchanges remembered for the debug overlay and bug reports
FIND = "find"  # Bridge(cli=FIND): look the claude command up on PATH; cli=None: there is none


@dataclass(frozen=True)
class Job:
    """One kind of request: which model, how long to wait, what shape the reply must have."""
    name: str
    model: str
    timeout: float
    schema: dict
    system: str
    tools: bool = False  # the read-only DeepMurim MCP tools (phase 6 spec 5); never for prose
    thinking: bool = False  # extended thinking: off for prose (it made one sentence cost 10-30 s; plan ruling 2)


@dataclass
class Exchange:
    job: str
    prompt: str
    reply: dict | None
    error: str = ""
    seconds: float = 0.0
    at: float = field(default_factory=time.time)


def conforms(schema: dict, value) -> bool:
    """A small JSON Schema check: types, required keys, no extra keys where forbidden, enums, string length."""
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return False
        props = schema.get("properties", {})
        if any(key not in value for key in schema.get("required", ())):
            return False
        if schema.get("additionalProperties") is False and any(key not in props for key in value):
            return False
        return all(conforms(props[key], v) for key, v in value.items() if key in props)
    if kind == "array":
        return isinstance(value, list) and all(conforms(schema.get("items", {}), v) for v in value) \
            and len(value) <= schema.get("maxItems", len(value))
    if kind == "string":
        return isinstance(value, str) and len(value) <= schema.get("maxLength", len(value)) \
            and ("enum" not in schema or value in schema["enum"])
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    return True


class Bridge:
    def __init__(self, cli: str | None = FIND, runner=subprocess.run, mcp_config: Path | None = None,
                 clock=time.monotonic) -> None:
        self.cli = shutil.which("claude") if cli == FIND else cli
        self.runner = runner
        self.mcp_config = mcp_config  # written per save by ai.mcp_config (phase 6a Task 3)
        self.clock = clock
        self.failures = 0
        self.paused_until = 0.0
        self.just_paused = False  # set once when the pause begins: the log says so in one line
        self.exchanges: deque[Exchange] = deque(maxlen=KEPT)
        self._checked: tuple[bool, str] | None = None

    def available(self) -> tuple[bool, str]:
        """Whether the CLI answers at all (checked once): (yes, '') or (no, the reason)."""
        if self._checked is None:
            if not self.cli:
                self._checked = (False, "the claude command is not installed")
            else:
                try:
                    done = self.runner([self.cli, "--version"], capture_output=True, text=True, timeout=15)
                    ok = done.returncode == 0
                    self._checked = (ok, "" if ok else (done.stderr or "claude --version failed").strip()[:120])
                except (OSError, subprocess.SubprocessError) as exc:
                    self._checked = (False, f"claude did not start ({exc.__class__.__name__})")
        return self._checked

    def paused(self) -> bool:
        return self.clock() < self.paused_until

    def command(self, job: Job) -> list[str]:
        cmd = [self.cli or "claude", "-p", "--model", job.model, "--output-format", "json",
               "--json-schema", json.dumps(job.schema), "--system-prompt", job.system,
               "--no-session-persistence", "--setting-sources", "", "--disable-slash-commands",
               "--effort", "low", "--tools", "", "--strict-mcp-config"]
        if job.tools and self.mcp_config is not None:
            cmd += ["--mcp-config", str(self.mcp_config), "--allowedTools", "mcp__deepmurim__*"]
        else:
            cmd += ["--mcp-config", json.dumps({"mcpServers": {}})]
        return cmd

    @staticmethod
    def env(job: Job) -> dict:
        return {**os.environ, "MAX_THINKING_TOKENS": "0"} if not job.thinking else dict(os.environ)

    def call(self, job: Job, prompt: str) -> dict | None:
        """Claude's reply to this prompt, fitted to the job's schema; or None, and the caller carries on."""
        if self.paused() or not self.available()[0]:
            return None
        start = self.clock()
        reply, error = None, ""
        try:
            done = self.runner(self.command(job), input=prompt, capture_output=True, text=True, encoding="utf-8",
                               timeout=job.timeout, env=self.env(job))
            reply, error = self._parse(job, done)
        except subprocess.TimeoutExpired:
            error = f"no reply within {job.timeout:.0f} s"
        except (OSError, subprocess.SubprocessError) as exc:
            error = f"claude did not run ({exc.__class__.__name__})"
        self.exchanges.append(Exchange(job.name, prompt, reply, error, round(self.clock() - start, 2)))
        self._count(reply is not None)
        return reply

    @staticmethod
    def _parse(job: Job, done) -> tuple[dict | None, str]:
        if done.returncode != 0:
            return None, (done.stderr or f"exit {done.returncode}").strip()[:200]
        try:
            outer = json.loads(done.stdout)
        except ValueError:
            return None, "the reply was not JSON"
        if not isinstance(outer, dict) or outer.get("is_error"):
            return None, str(outer.get("result", "an error") if isinstance(outer, dict) else "an odd reply")[:200]
        reply = outer.get("structured_output")
        if reply is None:
            try:
                reply = json.loads(outer.get("result") or "")
            except ValueError:
                return None, "no structured reply"
        if not conforms(job.schema, reply):
            return None, "the reply did not fit its schema"
        return reply, ""

    def _count(self, ok: bool) -> None:
        if ok:
            self.failures = 0
            return
        self.failures += 1
        if self.failures >= PAUSE_AFTER:
            self.failures = 0
            self.paused_until = self.clock() + PAUSE_SECONDS
            self.just_paused = True
```

`ai/fake.py`:
```python
"""FakeClaude (phase 6 spec 11): the bridge's interface, answering from a script, so tests need no network."""

from collections import deque

from ai.bridge import Exchange, Job, conforms


class FakeClaude:
    """Each call takes the next scripted reply: a dict (checked against the job's schema like a real reply),
    None (a failure), or a callable of (job, prompt) returning either. With the script empty it fails."""

    def __init__(self, *replies, available: bool = True) -> None:
        self.script = deque(replies)
        self.calls: list[tuple[str, str]] = []
        self.exchanges: deque[Exchange] = deque(maxlen=20)
        self._available = available
        self.just_paused = False

    def available(self) -> tuple[bool, str]:
        return (True, "") if self._available else (False, "the claude command is not installed")

    def paused(self) -> bool:
        return False

    def add(self, *replies) -> None:
        self.script.extend(replies)

    def call(self, job: Job, prompt: str) -> dict | None:
        self.calls.append((job.name, prompt))
        if not self._available:
            return None
        reply = self.script.popleft() if self.script else None
        if callable(reply):
            reply = reply(job, prompt)
        if reply is not None and not conforms(job.schema, reply):
            reply = None
        self.exchanges.append(Exchange(job.name, prompt, reply, "" if reply is not None else "scripted failure"))
        return reply
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6a_task1.py`:
```python
"""Phase 6a, Task 1: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


print("task 1 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6a_task1.py`
Expected: `task 1 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_bridge.py`
Expected: `9 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the door to Claude - claude -p called bare, replies fitted to a schema, a pause after three failures, and FakeClaude

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: The state pack

What Claude is told of the player on every call (spec 4): HERE (the scene's own presence lines), LIMITS (what the realm forbids, the silver carried), CARRYING, LATELY (the journal) and YOU (the felt poisons and the sheet, last, so that it is the sheet that a size cut shortens). Built only from what the player can read; no ids; under 2,500 characters and 15 ms.

**Files:**
- Create: `ai/pack.py`
- Create: `tests/test_ai_pack.py`

**Interfaces:**
- Consumes: `engine.sheet.sheet_lines`, `engine.journal.summarize`, `engine.alchemy_page.poison_words`, `narrate.brief._place`, `Game._presence`.
- Produces:
  - `ai.pack`: `MAX_PACK = 2500`, `LIMITS` (one line per realm), `build_pack(game) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_pack.py`:
```python
import gc
import re
import time

import pytest

import systems.encounters as encounters
import systems.toxins as X
from ai.pack import LIMITS, MAX_PACK, build_pack
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def test_the_pack_tells_where_you_are_what_you_may_do_and_what_you_carry(game):
    pack = build_pack(game)
    for section in ("HERE:", "LIMITS:", "CARRYING:", "LATELY:", "YOU:"):
        assert section in pack, section
    assert game.place.name in pack and LIMITS[0] in pack
    assert f"you carry {game.world.entity(game.player.id).data['silver']} silver" in pack
    here = next(p for p in game.world.sources(game.place.id, "located_in") if p != game.player.id)
    assert game.world.entity(here).name in pack  # those here are named, as the scene names them
    assert len(pack) <= MAX_PACK


def test_the_pack_carries_no_ids_and_no_stranger_from_elsewhere(game):
    world = game.world
    far = world.add_entity("person", "Gu Faraway", {"occupation": "monk", "traits": ["kind"], "realm": "mortal",
                                                    "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:pack:far")
    pack = build_pack(game)
    assert "Gu Faraway" not in pack
    assert not re.search(r"#\d", pack)


def test_the_pack_follows_what_you_do(game):
    game.perform(Action("rest", 1))
    assert "rest" in build_pack(game).split("LATELY:")[1].lower()


def test_a_poison_unnamed_is_not_given_away(game):
    X.poison(game.world, game.player.id, 3, 12, "a hidden needle")
    pack = build_pack(game)
    assert "grade unknown" in pack and "grade 3" not in pack


def test_the_pack_is_quick(game):
    build_pack(game)
    gc.collect()
    start = time.perf_counter()
    for _ in range(20):
        build_pack(game)
    assert (time.perf_counter() - start) / 20 < 0.015
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_pack.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'ai.pack'`.

- [ ] **Step 3: Write the new modules**

`ai/pack.py`:
```python
"""The state pack (phase 6 spec 4): what the player knows of themselves and their surroundings, for every call.

Built from the pages the player can already read (the sheet, the scene's presence line, the journal), so it shows
nothing they could not see: no ids, no hidden truths, no one they have not heard of. Plain text, bounded in size.
"""

from engine.alchemy_page import poison_words
from engine.journal import summarize
from engine.sheet import sheet_lines
from narrate.brief import _place
from systems.bodies import load_body

MAX_PACK = 2500
MAX_CARRIED = 12
LATELY = 6
QUIET = frozenset({"exchange", "player_aged", "delve_moved", "delve_rested"})
SKIPPED = ("Meridians:", "Lung ", "Governing ")  # the sheet's meridian chart says nothing a writer can use
LIMITS = (
    "a mortal: no qi to speak of; cannot leap rooftops, walk on water or stand against a trained fighter",
    "third-rate: a little qi; can best mortals and leap a wall, not a master",
    "second-rate: real qi; can run along a roof, still no match for a first-rate master",
    "first-rate: a master of the martial world; still cannot fly or face a peak master",
    "peak: among the strongest of the land; the transcendent are beyond you",
    "transcendent: few in the land can stand against you",
    "profound: a legend; only a handful are your equal",
    "life-and-death: at the summit of the martial world",
)


def _sheet(world, player: int) -> list[str]:
    out = []
    for text, key in sheet_lines(world, player):
        text = text.strip()
        if not text or key == "heading" or text == "none" or text.startswith(SKIPPED) or "●" in text or "·" in text:
            continue
        out.append(text)
    return out


def _carried(world, player: int) -> str:
    names = sorted(world.entity(i).name for i in world.targets(player, "owns")
                   if world.entity(i) is not None and not world.entity(i).data.get("used"))
    if not names:
        return "nothing of note"
    shown = ", ".join(names[:MAX_CARRIED])
    return shown + (f", and {len(names) - MAX_CARRIED} more" if len(names) > MAX_CARRIED else "")


def _lately(world, player: int) -> list[str]:
    entries = [e for e in reversed(world.chronicle_about(player, limit=60)) if e.kind not in QUIET]
    return [summarize(world, e) for e in entries[-LATELY:]]


def build_pack(game) -> str:
    """The pack for this moment of this game (the player's view, never the world's truth)."""
    world, me = game.world, game.player.id
    place = _place(world, game.place.id)
    body = load_body(world, me)
    silver = int(world.entity(me).data.get("silver", 0))
    sections = [  # the sheet last: if the pack must be cut, it is the sheet that loses its tail
        ("HERE", [f"{place.name} ({place.kind}) in {place.region}; {place.terrain}; {place.season}, {place.watch}"]
         + [text for text, _ in game._presence()]),
        ("LIMITS", [LIMITS[min(body.realm, len(LIMITS) - 1)], f"you carry {silver} silver"]),
        ("CARRYING", [_carried(world, me)]),
        ("LATELY", _lately(world, me) or ["nothing yet"]),
        ("YOU", [f"{game.player.name}, age {int(game.player.data.get('age', 18))}"] + poison_words(body)
         + _sheet(world, me)),
    ]
    text = "\n".join(f"{name}:\n" + "\n".join(f"- {line}" for line in lines) for name, lines in sections)
    return text if len(text) <= MAX_PACK else text[:MAX_PACK - 1] + "…"
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6a_task2.py`:
```python
"""Phase 6a, Task 2: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


print("task 2 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6a_task2.py`
Expected: `task 2 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_pack.py`
Expected: `5 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the state pack - what the player knows of here, their limits, what they carry and lately did

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: The read-only MCP server

`World.open_readonly` opens a save so that any write fails. `mcp_server/tools.py` answers as the save's player knows the world (ruling 7): the sheet, the people known, one person, their memories of you, their beliefs (with opaque handles for 6b), rumours, the chronicle, factions, the place. `mcp_server/server.py` serves them over stdio with the `mcp` SDK 2.x; `ai/mcp_config.py` writes the config `claude -p` is given. `mcp>=2.2` joins `requirements.txt` (install it: `.venv/Scripts/python.exe -m pip install mcp`).

**Files:**
- Create: `ai/mcp_config.py`
- Create: `mcp_server/__init__.py`
- Create: `mcp_server/server.py`
- Create: `mcp_server/tools.py`
- Create: `tests/test_mcp_server.py`
- Modify (by `.patches/6a_task3.py`): `requirements.txt`, `world/db.py`

**Interfaces:**
- Consumes: Task 1 (the bridge passes `mcp_config` to tooled jobs); `systems.beliefs.known_people`, `systems.attitude.attitude`, `narrate.gossip_text.rumour_text`, `engine.standing_page.standing_lines`.
- Produces:
  - `world.db.World.open_readonly(path) -> World`.
  - `mcp_server.tools`: `View(world)` (`known()`, `find(name)`, `handle(holder, fact_id)`), `UNKNOWN`, `_safe`, `sheet`, `known_people`, `person(name)`, `memories_of(name)`, `beliefs_of(name, topic='')`, `rumours(topic='')`, `chronicle(query='', limit=10)`, `factions`, `place`, `TOOLS`.
  - `mcp_server.server`: `build(save) -> MCPServer`, `main(argv)`; `ai.mcp_config`: `SERVER`, `config(save)`, `write_config(save, folder) -> Path`.

- [ ] **Step 1: Write the failing tests**

`tests/test_mcp_server.py`:
```python
import gc
import hashlib
import json
import re
import sys
import time

import anyio
import pytest

import systems.encounters as encounters
from ai.mcp_config import SERVER, config, write_config
from engine.actions import Action
from engine.game import Game
from mcp_server import tools as T
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.db import World
from world.gen.materialize import people_at


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def view_of(game) -> T.View:
    return T.View(World.open_readonly(game.world.path))


def someone_far(game, tag="far"):
    return game.world.add_entity("person", f"Gu {tag.title()}", {"occupation": "monk", "traits": ["kind"],
                                                                 "realm": "second-rate", "age": 40,
                                                                 "portrait": {"hair": 0, "face": 0, "robe": 0}},
                                 f"test:mcp:{tag}")


def heard(game, subject, predicate="killed", target=None):
    world = game.world
    variant = make_variant(predicate, subject, target, place="Somewhere")
    fact = record_fact(world, subject, predicate, target, place=None, variant=variant, spread=False)
    believe(world, game.player.id, fact, variant, None, 0.9, 1, "test")
    return fact


def test_the_sheet_and_the_place_are_the_players_own(game):
    view = view_of(game)
    assert "Realm: Mortal" in T.sheet(view)
    place = T.place(view)
    assert place.startswith(game.place.name) and "Here:" in place


def test_people_are_those_here_and_those_heard_of_never_a_stranger(game):
    view = view_of(game)
    here = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    assert f"{here.name}, {here.data['occupation']}, here" in T.known_people(view)
    far = someone_far(game)
    assert T.person(view_of(game), "Gu Far") == T.UNKNOWN  # never heard of: no lookup of the truth
    heard(game, far)
    view = view_of(game)
    assert "Gu Far, monk, elsewhere" in T.known_people(view)
    assert T.person(view, "gu far").startswith("Gu Far: monk; kind; second-rate")
    assert "said of them:" in T.person(view, "Gu Far")


def test_memories_and_beliefs_are_theirs_with_opaque_handles(game):
    here = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    game.perform(Action("talk", here.id))
    view = view_of(game)
    assert T.memories_of(view, here.name).startswith("curious: ") and "Met " in T.memories_of(view, here.name)
    far = someone_far(game, "story")
    fact = heard(game, far)
    variant = game.world.facts("killed", subject=far)[0].data["variant"]
    believe(game.world, here.id, fact, variant, None, 0.8, 1, "test")
    beliefs = T.beliefs_of(view_of(game), here.name, "killed")
    handle = "b" + hashlib.sha256(f"{game.world.world_seed}:{here.id}:{fact}".encode()).hexdigest()[:10]
    assert beliefs.startswith(f"[{handle}]") and "Gu Story" in beliefs
    assert T.beliefs_of(view_of(game), here.name, "dragons") == "They hold nothing on that."
    assert T.memories_of(view_of(game), "Nobody At All") == T.UNKNOWN


def test_rumours_chronicle_and_factions(game):
    heard(game, someone_far(game, "rumour"))
    game.perform(Action("rest", 1))
    view = view_of(game)
    assert "Gu Rumour" in T.rumours(view, "gu")
    assert "rest" in T.chronicle(view, "rest").lower()
    assert T.chronicle(view, "zzz") == "Nothing of the kind."
    assert isinstance(T.factions(view), str)


def test_no_answer_carries_an_id_and_none_writes(game):
    heard(game, someone_far(game, "quiet"))
    path = game.world.path
    game.world._conn.execute("pragma wal_checkpoint(truncate)")
    before = path.read_bytes()
    view = view_of(game)
    name = people_at(game.world, game.place.id, exclude=game.player.id)[0].name
    answers = [T.sheet(view), T.known_people(view), T.person(view, name), T.memories_of(view, name),
               T.beliefs_of(view, name, ""), T.rumours(view, ""), T.chronicle(view, "", 10), T.factions(view),
               T.place(view)]
    for answer in answers:
        assert not re.search(r"#\d", answer), answer[:80]
    view.world.close()
    assert path.read_bytes() == before


def test_a_read_that_would_write_is_told_not_known(game):
    view = view_of(game)

    def writes(v):
        v.world.set_meta("touched", 1)
    assert T._safe(writes)(view) == "That is not known."


def test_each_tool_is_quick(game):
    for n in range(200):
        heard(game, someone_far(game, f"crowd{n}"))
    view = view_of(game)
    name = people_at(game.world, game.place.id, exclude=game.player.id)[0].name
    calls = [lambda: T.sheet(view), lambda: T.known_people(view), lambda: T.person(view, "Gu Crowd7"),
             lambda: T.memories_of(view, name), lambda: T.beliefs_of(view, name, ""), lambda: T.rumours(view, "gu"),
             lambda: T.chronicle(view, "", 10), lambda: T.factions(view), lambda: T.place(view)]
    for call in calls:
        call()
        gc.collect()
        start = time.perf_counter()
        for _ in range(5):
            call()
        assert (time.perf_counter() - start) / 5 < 0.03, call


def test_the_config_runs_this_python_on_this_save(game, tmp_path):
    path = write_config(game.world.path, tmp_path / "session")
    data = json.loads(path.read_text(encoding="utf-8"))
    server = data["mcpServers"]["deepmurim"]
    assert server["command"] == sys.executable and server["args"] == [str(SERVER), str(game.world.path.resolve())]
    assert config(game.world.path) == data


def test_the_server_answers_over_stdio(game):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    game.world._conn.execute("pragma wal_checkpoint(truncate)")
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER), str(game.world.path)])

    async def session():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                names = sorted(t.name for t in (await client.list_tools()).tools)
                answer = await client.call_tool("place", {})
                return names, answer.content[0].text
    names, text = anyio.run(session)
    assert names == sorted(t.__name__ for t in T.TOOLS)
    assert text.startswith(game.place.name)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_mcp_server.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'ai.mcp_config'`.

- [ ] **Step 3: Write the new modules**

`ai/mcp_config.py`:
```python
"""The MCP config `claude -p` is given (phase 6 spec 2): one server, DeepMurim's, over the current save."""

import json
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent / "mcp_server" / "server.py"


def config(save: Path) -> dict:
    return {"mcpServers": {"deepmurim": {"command": sys.executable, "args": [str(SERVER), str(Path(save).resolve())]}}}


def write_config(save: Path, folder: Path) -> Path:
    """Write the config beside the session's other files; the bridge passes its path to every tooled call."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "deepmurim-mcp.json"
    target.write_text(json.dumps(config(save), indent=2), encoding="utf-8")
    return target
```

`mcp_server/__init__.py`:
```python
"""The DeepMurim MCP server (phase 6): read-only tools over a save, as its player knows it."""
```

`mcp_server/server.py`:
```python
"""The DeepMurim MCP server (phase 6 spec 5): `python mcp_server/server.py <save>` serves the read-only tools over
stdio to one `claude -p` call. The viewer is the save's player, fixed at start: no tool asks as anyone else."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run as a script by `claude -p`

from mcp.server.mcpserver import MCPServer  # noqa: E402

from mcp_server import tools as T  # noqa: E402
from world.db import World  # noqa: E402

INSTRUCTIONS = ("Read-only views of a DeepMurim world, as the player knows it. Name people as the player knows "
                "them. Nothing here changes the world.")


def build(save) -> MCPServer:
    view = T.View(World.open_readonly(save))
    server = MCPServer("deepmurim", instructions=INSTRUCTIONS)

    def sheet() -> str:
        return T.sheet(view)

    def known_people() -> str:
        return T.known_people(view)

    def person(name: str) -> str:
        return T.person(view, name)

    def memories_of(name: str) -> str:
        return T.memories_of(view, name)

    def beliefs_of(name: str, topic: str = "") -> str:
        return T.beliefs_of(view, name, topic)

    def rumours(topic: str = "") -> str:
        return T.rumours(view, topic)

    def chronicle(query: str = "", limit: int = 10) -> str:
        return T.chronicle(view, query, limit)

    def factions() -> str:
        return T.factions(view)

    def place() -> str:
        return T.place(view)

    for fn, tool in zip((sheet, known_people, person, memories_of, beliefs_of, rumours, chronicle, factions, place),
                        T.TOOLS):
        server.add_tool(fn, name=tool.__name__, description=tool.__doc__)
    return server


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: server.py <save.world>", file=sys.stderr)
        return 2
    build(argv[1]).run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

`mcp_server/tools.py`:
```python
"""The MCP tools (phase 6 spec 5): plain functions over a read-only world, each answering as the viewer knows.

Every answer is plain text with no entity ids. People are named as the viewer knows them; a name the viewer does
not know (or that fits two people) is an answer of its own, never a lookup of the truth. A belief comes with an
opaque handle (for 6b's `tell`), a hash of the seed, the holder and the fact, never an id.
"""

import hashlib
import sqlite3

from engine.game import Game
from engine.journal import summarize
from engine.sheet import sheet_lines
from engine.standing_page import standing_lines
from narrate.gossip_text import rumour_text
from systems.attitude import attitude
from systems.beliefs import known_people as heard_of
from world.gen.materialize import people_at

QUIET = frozenset({"exchange", "player_aged", "delve_moved", "delve_rested"})
MAX_PEOPLE, MAX_LINES = 40, 20
UNKNOWN = "No one you know by that name."


class View:
    """The world as one viewer may read it."""

    def __init__(self, world) -> None:
        self.world = world
        self.game = Game(world)
        self.viewer = world.get_meta("player_id")

    def known(self) -> list[int]:
        here = [p.id for p in people_at(self.world, self.game.place.id, exclude=self.viewer)]
        return list(dict.fromkeys(here + heard_of(self.world, self.viewer)))

    def find(self, name: str) -> int | None:
        wanted = name.strip().lower()
        hits = [p for p in self.known() if self.world.entity(p).name.lower() == wanted]
        return hits[0] if len(hits) == 1 else None

    def handle(self, holder: int, fact_id: int) -> str:
        raw = f"{self.world.world_seed}:{holder}:{fact_id}".encode()
        return "b" + hashlib.sha256(raw).hexdigest()[:10]


def _safe(fn):
    """A read the read-only world refuses (it would have written) is told as not known, never a crash."""
    def run(*args):
        try:
            return fn(*args)
        except sqlite3.OperationalError:
            return "That is not known."
    run.__name__, run.__doc__ = fn.__name__, fn.__doc__
    return run


@_safe
def sheet(view: View) -> str:
    """Your own sheet: realm, body, arts, standing (as the sheet page shows it)."""
    return "\n".join(text for text, _ in sheet_lines(view.world, view.viewer) if text.strip())


@_safe
def known_people(view: View) -> str:
    """Everyone you have met or heard of: name, role, whether they are here, how they feel toward you."""
    world, here = view.world, {p.id for p in people_at(view.world, view.game.place.id)}
    lines = []
    for pid in view.known()[:MAX_PEOPLE]:
        person = world.entity(pid)
        where = "here" if pid in here else "elsewhere"
        feeling = attitude(world, pid, view.viewer).word if person.kind == "person" else "unknown"
        lines.append(f"{person.name}, {person.data.get('occupation', 'stranger')}, {where}, {feeling}")
    return "\n".join(lines) or "You know no one yet."


@_safe
def person(view: View, name: str) -> str:
    """One person as you know them: role, traits, realm, and what is said of them."""
    pid = view.find(name)
    if pid is None:
        return UNKNOWN
    world, entity = view.world, view.world.entity(pid)
    d = entity.data
    lines = [f"{entity.name}: {d.get('occupation', 'stranger')}; {', '.join(d.get('traits', ())) or 'unremarkable'}; "
             f"{d.get('realm', 'mortal')}; toward you: {attitude(world, pid, view.viewer).word}"]
    said = [rumour_text(world, b.variant, view.viewer)
            for b, _ in world.known_facts_about([view.viewer], actors=[pid])][-MAX_LINES:]
    return "\n".join(lines + [f"said of them: {s}" for s in said])


@_safe
def memories_of(view: View, name: str) -> str:
    """What that person remembers of you, and how they feel about it."""
    pid = view.find(name)
    if pid is None:
        return UNKNOWN
    world = view.world
    found = world.memories(pid, about=view.viewer)[-MAX_LINES:]
    return "\n".join(f"{m.feeling}: {summarize(world, m.event)}" for m in found) or "They remember nothing of you."


@_safe
def beliefs_of(view: View, name: str, topic: str = "") -> str:
    """What that person holds to be so on a topic (empty: anything), each with a handle to tell it by."""
    pid = view.find(name)
    if pid is None:
        return UNKNOWN
    world, wanted = view.world, topic.strip().lower()
    out = []
    for belief, fact in world.known_facts(pid):
        text = rumour_text(world, belief.variant, view.viewer)
        if not wanted or wanted in text.lower():
            out.append(f"[{view.handle(pid, fact.id)}] {text}")
    return "\n".join(out[-MAX_LINES:]) or "They hold nothing on that."


@_safe
def rumours(view: View, topic: str = "") -> str:
    """What you have heard on a topic (empty: the latest)."""
    world, wanted = view.world, topic.strip().lower()
    texts = [rumour_text(world, b.variant, view.viewer) for b, _ in world.known_facts(view.viewer)]
    return "\n".join([t for t in texts if not wanted or wanted in t.lower()][-MAX_LINES:]) or "You have heard nothing."


@_safe
def chronicle(view: View, query: str = "", limit: int = 10) -> str:
    """Your own past, as your journal tells it, newest last (query: words to look for)."""
    world, wanted = view.world, query.strip().lower()
    entries = [e for e in reversed(world.chronicle_about(view.viewer, limit=300)) if e.kind not in QUIET]
    lines = [summarize(world, e) for e in entries]
    lines = [line for line in lines if not wanted or wanted in line.lower()]
    return "\n".join(lines[-max(1, min(int(limit), MAX_LINES)):]) or "Nothing of the kind."


@_safe
def factions(view: View) -> str:
    """Your standing with the factions you know, and your ranks."""
    return "\n".join(t for t, _ in standing_lines(view.world, view.viewer, view.game.place.id) if t.strip())


@_safe
def place(view: View) -> str:
    """Where you are: the place, who is here, what is here."""
    head = f"{view.game.place.name}"
    return "\n".join([head] + [t for t, _ in view.game._presence()])


TOOLS = (sheet, known_people, person, memories_of, beliefs_of, rumours, chronicle, factions, place)
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6a_task3.py`:
```python
"""Phase 6a, Task 3: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('requirements.txt', r'''pytest>=8
''', r'''pytest>=8
mcp>=2.2
''')
edit('world/db.py', r'''                conn.execute(statement)
        return world

''', r'''                conn.execute(statement)
        return world

    @classmethod
    def open_readonly(cls, path) -> "World":
        """A save opened for reading only (phase 6: the MCP server). Any write raises sqlite3.OperationalError,
        so a read that would quietly create something (a seeded body, a recipe) fails loudly instead."""
        path = Path(path)
        if not path.is_file():
            raise SaveError(f"No save at {path}")
        # The MCP server answers in a worker thread; a read-only connection is safe to hand between threads.
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, isolation_level=None,
                               check_same_thread=False)
        row = conn.execute("select value from meta where key = 'schema_version'").fetchone()
        if row is None or json.loads(row[0]) != SCHEMA_VERSION:
            conn.close()
            raise SaveError(f"{path.name} is not a save this game reads")
        return cls(conn, path)

''')
print("task 3 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6a_task3.py`
Expected: `task 3 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_mcp_server.py`
Expected: `9 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the read-only MCP server - the world as its player knows it, over stdio, never written

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: Claude's prose in the game

`Game` marks the lines its narrator wrote (`Turn.narrated`). `Narration` asks Haiku once per turn (ruling 3) in a worker thread, with the turn's briefs and the pack; `App` settles the turn before, starts the new one, and polls every frame (`main.py`). A reply passes `ai/guard.py` (no stranger, no thing or number the turn did not carry, no number it carried dropped: ruling 5), then replaces the narrated lines (assist) or the waiting mark (ai_only). F1 cycles off, assist, ai_only (ruling 1), saved as `ai_mode`; without Claude it says why and stays off.

**Files:**
- Create: `ai/guard.py`
- Create: `ai/narrate.py`
- Create: `tests/test_ai_narration.py`
- Modify (by `.patches/6a_task4.py`): `app.py`, `config.py`, `engine/actions.py`, `engine/game.py`, `main.py`

**Interfaces:**
- Consumes: Tasks 1-2: `Bridge`/`FakeClaude`, `Job`, `build_pack`; `Game.last_briefs`, `Brief.to_prompt`.
- Produces:
  - `engine.actions.Turn.narrated: list[int]`; `Game._narrated`.
  - `ai.guard`: `THINGS`, `allowed_people(world, player, place)`, `refusal(world, prose, player, place, given, needed='') -> str | None`.
  - `ai.narrate`: `MODES`, `MODE_WORDS`, `MODEL`, `TIMEOUT = 10.0`, `WAITING`, `PROSE_SCHEMA`, `SYSTEM`, `narrate_job(model, timeout) -> Job`, `turn_prompt(briefs, pack, recent) -> str`, `unwrap(prose)`, `Pending`, `Narration(bridge=None, mode='off')` with `cycle`, `unavailable`, `start(log, start, turn, game)`, `poll(log, game) -> list`, `settle(log)`, `close`, `cache`, `pending`, `refused`.
  - `App(..., bridge=None)`: `narration`, `poll()`, `_cycle_ai()`; `Config.ai_mode`; the palette's `prose`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_narration.py`:
```python
import json
import time

from ai.fake import FakeClaude
from ai.guard import refusal
from ai.narrate import WAITING
from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice

MIST = {"prose": "Mist hangs over the reeds, and the town wakes slowly around you."}


def make_app(tmp_path, *replies, mode="assist", available=True):
    fake = FakeClaude(*replies, available=available)
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", bridge=fake)
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    return app, fake


def wait(app):
    for _ in range(300):
        pending = app.narration.pending
        if pending is None or pending.future.done():
            app.poll()
            return
        time.sleep(0.01)
    raise AssertionError("no reply came")


def turn_texts(app, turn_start):
    return [text for text, _ in app.log[turn_start:]]


def test_a_turn_marks_the_lines_its_narrator_wrote(tmp_path):
    fresh = Game.new(tmp_path / "f.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    turn = fresh.start()
    assert turn.narrated and turn.lines[turn.narrated[0]][0].startswith("Crimson Town stands on stilts")
    assert any(line[0].startswith("Here:") for i, line in enumerate(turn.lines) if i not in turn.narrated)
    rest = fresh.perform(Action("rest"))
    assert rest.narrated == list(range(len(rest.lines)))  # a rest is all the narrator's
    fresh.close()


def test_off_asks_nothing(tmp_path):
    app, fake = make_app(tmp_path, MIST, mode="off")
    app.submit("look")
    app.poll()
    assert fake.calls == [] and not any(key == "prose" for _, key in app.log)
    app.shutdown()


def test_assist_shows_procedural_text_then_claudes_prose_in_its_place(tmp_path):
    app, fake = make_app(tmp_path, MIST)
    turn = app.last_turn  # the opening turn
    assert app.log[:len(turn.lines)] == turn.lines  # procedural first
    wait(app)
    narrated = [turn.lines[i] for i in turn.narrated]
    kept = [line for i, line in enumerate(turn.lines) if i not in turn.narrated]
    at = turn.narrated[0]
    assert app.log[:len(kept) + 1] == kept[:at] + [(MIST["prose"], "prose")] + kept[at:]  # in its place
    assert not any(line in app.log for line in narrated)
    assert "STATE:" in fake.calls[-1][1] and "EVENT:" in fake.calls[-1][1]
    app.shutdown()


def test_ai_only_hides_the_text_until_the_prose_comes_and_restores_it_on_failure(tmp_path):
    app, fake = make_app(tmp_path, MIST, None, mode="ai_only")
    assert WAITING in app.log
    wait(app)
    assert WAITING not in app.log and (MIST["prose"], "prose") in app.log
    app.submit("rest")
    turn = app.last_turn
    assert WAITING in app.log and not any(turn.lines[i] in app.log for i in turn.narrated)
    wait(app)  # the scripted failure
    assert WAITING not in app.log and all(turn.lines[i] in app.log for i in turn.narrated)
    app.shutdown()


def test_acting_before_the_prose_comes_puts_the_text_back(tmp_path):
    slow = lambda job, prompt: (time.sleep(0.3), MIST)[1]  # noqa: E731
    app, fake = make_app(tmp_path, slow, slow, mode="ai_only")
    first = app.last_turn
    app.submit("rest")  # the opening turn's prose has not come
    assert all(first.lines[i] in app.log for i in first.narrated)
    wait(app)
    assert app.log.count((MIST["prose"], "prose")) == 1  # only the turn still waiting got it
    app.shutdown()


def test_prose_that_brings_in_a_stranger_or_a_number_is_refused(tmp_path):
    stranger = {"prose": "Gu Nobody watches you from the reeds."}
    app, fake = make_app(tmp_path, stranger)
    app.game.world.add_entity("person", "Gu Nobody", {"occupation": "monk", "traits": [], "realm": "mortal",
                                                      "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:ai:gu")
    wait(app)
    assert ("Gu Nobody watches you from the reeds.", "prose") not in app.log
    assert "Gu Nobody" in app.narration.refused
    world, me, here = app.game.world, app.game.player.id, app.game.place.id
    assert refusal(world, "You pay 40 silver.", me, here, "OUTCOME: you pay 30 silver") == \
        "it states 40, which the turn did not"
    assert refusal(world, "You pay the man.", me, here, "you pay 30 silver", "You pay 30 silver.") == \
        "it leaves out the 30 the turn told"
    assert refusal(world, "You pay 30 silver.", me, here, "you pay 30 silver", "You pay 30 silver.") is None
    app.shutdown()


def test_prose_wrapped_twice_is_unwrapped():
    from ai.narrate import unwrap
    assert unwrap('{"prose": "You cast your gaze about."}') == "You cast your gaze about."
    assert unwrap("  Plain words.  ") == "Plain words."
    assert unwrap("{not json") == "{not json"


def test_the_same_turn_is_not_asked_twice(tmp_path):
    app, fake = make_app(tmp_path, MIST)
    wait(app)
    calls = len(fake.calls)
    turn = app.last_turn
    app.log.extend(turn.lines)
    app.narration.start(app.log, len(app.log) - len(turn.lines), turn, app.game)
    assert len(fake.calls) == calls and app.log[-len(turn.lines):].count((MIST["prose"], "prose")) == 1
    app.shutdown()


def test_f1_cycles_the_mode_and_remembers_it(tmp_path):
    app, fake = make_app(tmp_path, mode="off")
    app.handle_key("f1", "")
    assert app.narration.mode == "assist" and app.log[-1] == ("AI prose: procedural first, then Claude's.", "system")
    app.handle_key("f1", "")
    app.handle_key("f1", "")
    assert app.narration.mode == "off"
    app.handle_key("f1", "")
    assert json.loads((tmp_path / "settings.json").read_text())["ai_mode"] == "assist"
    app.shutdown()


def test_without_claude_the_modes_stay_off_and_say_why(tmp_path):
    app, fake = make_app(tmp_path, mode="off", available=False)
    app.handle_key("f1", "")
    assert app.narration.mode == "off"
    assert app.log[-1] == ("Claude's prose cannot be used: the claude command is not installed.", "system")
    app.shutdown()


def test_a_pause_is_told_once(tmp_path):
    app, fake = make_app(tmp_path, MIST)
    wait(app)
    fake.just_paused = True
    app.poll()
    app.poll()
    assert sum("rests for five minutes" in text for text, _ in app.log) == 1
    app.shutdown()
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_narration.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'ai.guard'`.

- [ ] **Step 3: Write the new modules**

`ai/guard.py`:
```python
"""The prose guard (phase 6 spec 6): Claude's prose is shown only if it adds no one and nothing.

Refused when it names a person the player has not heard of (`check_people`'s rule), names a thing of the world
(an item, a pill, a herb, a manual) that the turn did not, or states a number the turn did not carry. The guard
reads the world's names only; it never decides what is true, only what the prose may not bring in.
"""

import re

from systems.beliefs import known_people
from world.gen.materialize import people_at

THINGS = ("gear", "pill", "herb", "treasure", "scroll", "manual", "furnace", "recipe")
NUMBER = re.compile(r"\b\d+\b")


def _names(world, kinds) -> set[str]:
    marks = ",".join("?" * len(kinds))
    return {row[0] for row in world._conn.execute(f"select distinct name from entities where kind in ({marks})",
                                                  tuple(kinds))}


def allowed_people(world, player: int, place: int) -> set[str]:
    ids = set(known_people(world, player)) | {p.id for p in people_at(world, place)} | {player}
    return {world.entity(i).name for i in ids if world.entity(i) is not None}


def refusal(world, prose: str, player: int, place: int, given: str, needed: str = "") -> str | None:
    """Why this prose may not be shown (None: it may). `given` is all the turn told Claude (briefs and pack);
    `needed` is the text it replaces: every number there (silver, merit, days) must be kept."""
    allowed = allowed_people(world, player, place)
    for name in _names(world, ("person", "persona")):
        if name in prose and name not in allowed:
            return f"it names {name}, whom you have not heard of"
    for name in _names(world, THINGS):
        if len(name) > 3 and name in prose and name not in given:
            return f"it names {name}, which the turn did not"
    numbers = set(NUMBER.findall(given))
    stated = set(NUMBER.findall(prose))
    for number in stated:
        if number not in numbers:
            return f"it states {number}, which the turn did not"
    for number in NUMBER.findall(needed):
        if number not in stated:
            return f"it leaves out the {number} the turn told"
    return None
```

`ai/narrate.py`:
```python
"""Claude's prose for each turn (phase 6 spec 3, 6): asked for in a worker thread, shown when it comes.

One request per turn, over all of the turn's briefs (plan ruling 3): a turn reads as one passage, and a turn costs
one call. The prompt is built on the main thread (the world's connection belongs to it); only `claude -p` runs in
the worker. A reply is guarded, then replaces the turn's procedural lines in the log (assist) or its "…"
(ai_only). Anything that goes wrong leaves the procedural text where it is.
"""

import json
from concurrent.futures import Future, ThreadPoolExecutor
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
    "exactly as given, and keep every number an OUTCOME line states. Do not address the player as 'the player'. "
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


class Narration:
    def __init__(self, bridge: Bridge | None = None, mode: str = "off") -> None:
        self._bridge = bridge
        self.mode = mode if mode in MODES else "off"
        self.job = narrate_job()
        self.cache: dict[tuple, str] = {}
        self.pending: Pending | None = None
        self.refused: str | None = None  # why the last reply was not shown (the debug overlay)
        self.recent: list[str] = []
        self._pool: ThreadPoolExecutor | None = None

    @property
    def bridge(self) -> Bridge:
        if self._bridge is None:
            self._bridge = Bridge()
        return self._bridge

    def cycle(self) -> str:
        self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
        return self.mode

    def unavailable(self) -> str | None:
        """Why the AI modes cannot be used (None: they can)."""
        ok, why = self.bridge.available()
        return None if ok else why

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None

    # --- a turn ------------------------------------------------------------------------------------------------
    def start(self, log: list, start: int, turn, game) -> None:
        """A turn has just been put in the log at `start`: ask for its prose (and in ai_only, hide its lines).
        The caller settles the turn before (`settle`) before it puts this one in the log, so `start` holds."""
        narrated = list(getattr(turn, "narrated", []))
        if self.mode == "off" or not narrated or not game.last_briefs or self.unavailable():
            return
        lines = list(turn.lines)
        pack = build_pack(game)
        prompt = turn_prompt(game.last_briefs, pack, self.recent)
        given = prompt + "\n" + "\n".join(t for t, _ in lines)
        key = tuple((b.seed, b.salt, b.kind) for b in game.last_briefs)
        pending = Pending(start, lines, narrated, key, given, None, lines)
        if key in self.cache:
            _put(log, pending, _without(pending), prose=self.cache[key])
            return
        if self.mode == "ai_only":
            _put(log, pending, _without(pending, WAITING))
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="claude")
        pending.future = self._pool.submit(self.bridge.call, self.job, prompt)
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
        reply = pending.future.result()
        prose = unwrap(reply.get("prose", "")) if reply else ""
        needed = "\n".join(pending.lines[i][0] for i in pending.narrated)
        why = refusal(game.world, prose, game.player.id, game.place.id, pending.given, needed) if prose else "no prose"
        if why is None:
            self.cache[pending.key] = prose
            _put(log, pending, _without(pending), prose=prose)
            self.recent = (self.recent + [prose])[-RECENT:]
        else:
            _put(log, pending, pending.lines)  # the procedural text stands
        self.refused = why
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
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6a_task4.py`:
```python
"""Phase 6a, Task 4: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('app.py', r'''
from config import PALETTE, Config
''', r'''
from ai.narrate import MODE_WORDS, Narration
from config import PALETTE, Config
''')
edit('app.py', r'''    def __init__(self, config: Config, saves_dir: Path, settings_path: Path, logs_dir: Path | None = None) -> None:
''', r'''    def __init__(self, config: Config, saves_dir: Path, settings_path: Path, logs_dir: Path | None = None,
                 bridge=None) -> None:
''')
edit('app.py', r'''        self._recent_narration: deque[str] = deque(maxlen=4)
''', r'''        self._recent_narration: deque[str] = deque(maxlen=4)
        self.narration = Narration(bridge, config.ai_mode)  # phase 6: Claude's prose, F1
''')
edit('app.py', r'''        if key == "f2":
''', r'''        if key == "f1":
            self._cycle_ai()
        elif key == "f2":
''')
edit('app.py', r'''    def _show(self, turn: Turn) -> None:
        if self.log:
            self.log.append(("", "default"))
        self.log.extend(turn.lines)
''', r'''    def _cycle_ai(self) -> None:
        mode = self.narration.cycle()
        why = self.narration.unavailable() if mode != "off" else None
        if why is not None:
            self.narration.mode = mode = "off"
            self.log.append((f"Claude's prose cannot be used: {why}.", "system"))
        else:
            self.log.append((MODE_WORDS[mode] + ".", "system"))
        self.config.ai_mode = mode
        self._save_settings()

    def poll(self) -> None:
        """Every frame: Claude's prose for the last turn, if it has come (phase 6)."""
        if self.game is None or self.narration.pending is None and not getattr(self.narration.bridge, "just_paused", False):
            return
        waiting = self.narration.pending
        self.log.extend(self.narration.poll(self.log, self.game))
        if waiting is not None and self.narration.pending is None:
            self._record("ai", job="narrate", refused=self.narration.refused)

    def _show(self, turn: Turn) -> None:
        self.narration.settle(self.log)  # a turn left before its prose came keeps its own text
        if self.log:
            self.log.append(("", "default"))
        self.log.extend(turn.lines)
        start = len(self.log) - len(turn.lines)
''')
edit('app.py', r'''        del self.log[:-MAX_LOG]
''', r'''        before = len(self.log)
        del self.log[:-MAX_LOG]
        if self.game is not None:
            self.narration.start(self.log, start - (before - len(self.log)), turn, self.game)
''')
edit('app.py', r'''    def _close_game(self) -> None:
''', r'''    def _close_game(self) -> None:
        self.narration.pending = None
''')
edit('app.py', r'''        save_values({"art_side": self.config.art_side, "show_art": self.config.show_art}, self.settings_path)

    def shutdown(self) -> None:
        self._close_game()
''', r'''        save_values({"art_side": self.config.art_side, "show_art": self.config.show_art,
                     "ai_mode": self.config.ai_mode}, self.settings_path)

    def shutdown(self) -> None:
        self._close_game()
        self.narration.close()
''')
edit('config.py', r'''    "heading": (225, 185, 85),  # UI headings: gold, but never counted as prose
''', r'''    "heading": (225, 185, 85),  # UI headings: gold, but never counted as prose
    "prose": (215, 205, 175),  # Claude's prose (phase 6): a soft parchment, apart from the engine's own lines
''')
edit('config.py', r'''    show_art: bool = True
''', r'''    show_art: bool = True
    ai_mode: str = "off"  # phase 6: off | assist | ai_only (F1)
''')
edit('config.py', r'''        config.show_art = values["show_art"]
''', r'''        config.show_art = values["show_art"]
    if values.get("ai_mode") in ("off", "assist", "ai_only"):
        config.ai_mode = values["ai_mode"]
''')
edit('engine/actions.py', r'''    extra: list[Choice] = field(default_factory=list)  # valid now but folded off-screen
''', r'''    extra: list[Choice] = field(default_factory=list)  # valid now but folded off-screen
    narrated: list[int] = field(default_factory=list)  # which lines the narrator wrote (phase 6: Claude may rewrite them)
''')
edit('engine/game.py', r'''        self.last_briefs: list = []  # what the narrator was given this turn (debug overlay, invariants)
''', r'''        self.last_briefs: list = []  # what the narrator was given this turn (debug overlay, invariants)
        self._narrated: list = []  # the lines the narrator wrote this turn (phase 6)
''')
edit('engine/game.py', r'''    def look(self) -> Turn:
        self.last_briefs = []
''', r'''    def look(self) -> Turn:
        self.last_briefs, self._narrated = [], []
''')
edit('engine/game.py', r'''        self.last_briefs = []
''', r'''        self.last_briefs, self._narrated = [], []
''')
edit('engine/game.py', r'''            lines += self.narrator.narrate(brief)
''', r'''            told = self.narrator.narrate(brief)
            self._narrated += told
            lines += told
''')
edit('engine/game.py', r'''        return self.narrator.narrate(brief)
''', r'''        told = self.narrator.narrate(brief)
        self._narrated += told
        return told
''')
edit('engine/game.py', r'''        return Turn(lines, shown, self._art(), self._status(), extra)
''', r'''        told = {id(line) for line in self._narrated}
        return Turn(lines, shown, self._art(), self._status(), extra, [i for i, line in enumerate(lines) if id(line) in told])
''')
edit('main.py', r'''                        app.handle_key(key, event.unicode, repeat=repeat)
''', r'''                        app.handle_key(key, event.unicode, repeat=repeat)
            app.poll()  # Claude's prose, when it comes (phase 6)
''')
print("task 4 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6a_task4.py`
Expected: `task 4 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_narration.py tests/test_app.py`
Expected: `16 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: Claude's prose in the game - asked each turn, guarded, shown in place of the engine's own, F1 to choose

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: Seeing Claude at work, and the live round trip

The F12 overlay tells the mode, the last exchange and why prose was refused; the session log (and so every bug report) keeps each exchange; help names F1; the fork guide's section 16 (ruling 8); the `live` marker, and one real round trip that runs only with `DEEPMURIM_LIVE=1`.

**Files:**
- Create: `tests/test_ai_debug.py`
- Create: `tests/test_ai_live.py`
- Modify (by `.patches/6a_task5.py`): `app.py`, `docs/world-events.md`, `engine/game.py`, `pytest.ini`

**Interfaces:**
- Consumes: Tasks 1-4: `Narration`, `Bridge.exchanges`, `App._record`.
- Produces:
  - `App._claude_lines()`; `pytest.ini`'s `live` marker; `docs/world-events.md` section 16; `tests/test_ai_live.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_debug.py`:
```python
import json
import time

from ai.fake import FakeClaude
from app import App
from config import Config
from systems.creation import CreationChoice

MIST = {"prose": "Mist hangs over the reeds, and the town wakes slowly around you."}


def make_app(tmp_path, *replies, mode="assist"):
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=FakeClaude(*replies))
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    return app


def wait(app):
    for _ in range(300):
        pending = app.narration.pending
        if pending is None or pending.future.done():
            app.poll()
            return
        time.sleep(0.01)
    raise AssertionError("no reply came")


def test_the_overlay_tells_the_mode_and_the_last_exchange(tmp_path):
    app = make_app(tmp_path, MIST)
    wait(app)
    text = "\n".join(t for t, _ in app.debug_lines())
    assert "Claude: assist" in text and "last: narrate" in text and "Mist hangs" in text
    app.shutdown()


def test_the_overlay_tells_why_prose_was_refused(tmp_path):
    app = make_app(tmp_path, {"prose": "You count 999 frogs."})
    wait(app)
    assert any("prose refused: it states 999" in t for t, _ in app.debug_lines())
    app.shutdown()


def test_the_session_log_keeps_each_exchange_for_bug_reports(tmp_path):
    app = make_app(tmp_path, MIST)
    wait(app)
    folder = app.bug_report()
    records = [json.loads(line) for line in (folder / "session.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(r.get("kind") == "ai" and r.get("job") == "narrate" for r in records)
    app.shutdown()


def test_help_names_f1(tmp_path):
    app = make_app(tmp_path, mode="off")
    app.submit("help")
    assert any("F1 Claude's prose" in t for t, _ in app.log)
    app.shutdown()


def test_the_fork_guide_covers_the_claude_layer():
    from pathlib import Path
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("ai/bridge.py", "FakeClaude", "ai/pack.py", "open_readonly", "_safe", "Turn.narrated", "refusal",
                 "DEEPMURIM_LIVE"):
        assert word in guide, word
```

`tests/test_ai_live.py`:
```python
"""One real round trip through `claude -p` (phase 6 spec 11). Marked `live` and needs DEEPMURIM_LIVE=1."""
import os

import pytest

from ai.bridge import Bridge
from ai.narrate import narrate_job

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("DEEPMURIM_LIVE") != "1", reason="set DEEPMURIM_LIVE=1 to call Claude")]


def test_claude_writes_a_line_of_prose():
    bridge = Bridge()
    if not bridge.available()[0]:
        pytest.skip(bridge.available()[1])
    reply = bridge.call(narrate_job(), "STATE:\n- a misty marsh town at dawn\n\nTHIS TURN:\nEVENT: look\nOUTCOME:\n- You look around.")
    assert reply is not None and 0 < len(reply["prose"]) <= 900, list(bridge.exchanges)[-1].error
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_debug.py tests/test_ai_live.py`
Expected: `4 failed, 1 passed, 1 skipped`: no Claude in the overlay (`assert ('Claude: assist' in ...`), no fork guide section (`AssertionError: ai/bridge.py`), no F1 in help; the session log already keeps each exchange (Task 4), and the live test skips without `DEEPMURIM_LIVE=1`.

- [ ] **Step 3: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6a_task5.py`:
```python
"""Phase 6a, Task 5: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('app.py', r'''        lines.append(("Recent violations:", "gold"))
        lines += [(f"  {v}", "red") for v in self.violations[-8:]] or [("  none", "dim")]
''', r'''        lines += self._claude_lines()
        lines.append(("Recent violations:", "gold"))
        lines += [(f"  {v}", "red") for v in self.violations[-8:]] or [("  none", "dim")]
        return lines

    def _claude_lines(self) -> list:
        """The overlay's account of Claude this turn (phase 6): the mode, the last exchange, why prose was refused."""
        n = self.narration
        lines = [(f"Claude: {n.mode}" + (" (waiting for prose)" if n.pending is not None else ""), "gold")]
        why = n.unavailable() if n.mode != "off" else None
        if why:
            lines.append((f"  unavailable: {why}", "red"))
        exchanges = list(getattr(n.bridge, "exchanges", [])) if n.mode != "off" or n._bridge is not None else []
        if exchanges:
            last = exchanges[-1]
            lines.append((f"  last: {last.job}, {last.seconds:.1f} s, " + (f"failed: {last.error}" if last.error
                          else f"replied: {str(last.reply)[:120]}"), "default"))
        if n.refused:
            lines.append((f"  prose refused: {n.refused}", "red"))
        lines.append(("", "default"))
''')
edit('docs/world-events.md', r'''its wave kinds and a strength of at least 1.
''', r'''its wave kinds and a strength of at least 1.

## 16. The Claude layer (phase 6a)

**The rule:** Claude never writes the world. In 6a it only writes prose; from 6b it proposes, and `ai/validate.py`
turns what passes into ordinary events. Every failure leaves the procedural text standing.

**The door** is `ai/bridge.py`: one `claude -p` call per request, stripped bare (no settings, skills, hooks or MCP
servers of the user's own; no built-in tools; low effort), its reply checked against the `Job`'s schema by
`conforms`. Three failures in a row pause it for five minutes. Tests use `ai/fake.py`'s `FakeClaude`, which answers
from a script through the same `call(job, prompt)`.

**What Claude is told** is the state pack (`ai/pack.py`: HERE, LIMITS, CARRYING, LATELY, YOU, built from the pages
the player can read) and, for prose, the turn's briefs (`Brief.to_prompt`). A new system that wants Claude to know
something puts it on a page or in a brief, never straight into a prompt.

**Adding an MCP tool:** a function in `mcp_server/tools.py` taking the `View` (the world opened with
`World.open_readonly`, as its player knows it) and returning plain text with no ids, wrapped in `_safe`; then a
wrapper of the same name in `mcp_server/server.py`'s `build` and an entry in `TOOLS`. A read that would write (a
seeded body, say) fails on the read-only world and is told as not known.

**Prose** (`ai/narrate.py`): `Narration` asks once per turn, in a worker thread, over the lines the narrator wrote
(`Turn.narrated`); `ai/guard.py`'s `refusal` turns away prose that names someone unheard of or a thing the turn did
not, states a number it did not, or drops one it did. The modes are `off`, `assist` and `ai_only` (F1, saved as
`ai_mode`).

**Tests that call the real CLI** are marked `live` and also need `DEEPMURIM_LIVE=1`; no ordinary run makes one.
''')
edit('engine/game.py', r'''    ("  F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu", "system"),
''', r'''    ("  F1 Claude's prose | F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu",
     "system"),
''')
edit('pytest.ini', r'''addopts = -m "not slow"
''', r'''    live: real calls to the claude CLI (phase 6); run with -m live
addopts = -m "not slow and not live"
''')
print("task 5 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6a_task5.py`
Expected: `task 5 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_debug.py tests/test_ai_live.py`
Expected: `5 passed, 1 deselected`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow soak is deselected).

- [ ] **Step 7: Run the 500-year soak**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: `1 passed`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: seeing Claude at work - the overlay, bug reports, help, the fork guide, and a live round trip

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Self-review

- **Spec coverage:**
  - §2 architecture: the bridge and its call (Task 1), the pack (Task 2), the MCP server (Task 3), the narrator and guard (Task 4);
  - §3 settings and modes (Task 4); §4 the state pack (Task 2); §5 the MCP server (Task 3); §6 narration (Task 4);
  - §8 failure and determinism (Tasks 1, 4); §10 speed (Tasks 2, 3); §11 testing (every task; the live test in Task 5);
  - the debug overlay and bug reports (Task 5); §7 and §9 belong to 6b.
- **Dry run:**
  - every task was applied in order to a copy of master; its tests failed as each Step 2 says, then passed;
  - the whole suite passed after every task, and the 500-year soak passed at the end;
  - the live round trip passed against the real CLI (about 4 s).
