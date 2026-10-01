# Phase 6b: Two Backends, the AI Menu, One MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The game's prose can come from Claude Code (through the Agent SDK, on the player's own plan) or from OpenCode (free models only). The player chooses on an F1 menu, sees on a Connect page how everything is reached, and one long-lived MCP server serves the world to both. Prefetched lookups and paragraph-length prose are ready for 6c.

**Architecture:**
- **`ai/backends.py`:** a `Backend` base with 6a's rules (failures return None, a pause after three), and two doors:
  - `ClaudeCode`: one Agent SDK client per job, kept open on a background event loop; each call is a fresh session.
  - `OpenCode`: a hidden `opencode serve`, with each `opencode run --attach` going through it.
- **`ai/models.py`:** the model lists, including OpenCode's free ones.
- **`ai/menu.py`:** the menu's state, the backend factory, and the Connect page.
- **`mcp_server/live.py`:** `LiveServer` runs `build(save, fresh=True)` over streamable HTTP in a thread of the game.
- **`ai/prefetch.py`:** the lookups a model would ask for, made in advance.
- **`App`:** opens the menu, applies its changes, and runs the server while the AI is on.

**Tech Stack:** Python 3.14, the Claude Agent SDK (`claude-agent-sdk`), OpenCode 1.18 (`opencode.exe`), the `mcp` SDK 2.x with uvicorn, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-phase6-claude-layer-design.md`, section 13 (the amendment after 6a).

## Global Constraints

- **The player's plan, never the API:**
  - Claude Code runs on the player's own login through the Agent SDK.
  - `ANTHROPIC_API_KEY` is removed from its environment.
  - DeepMurim never takes a subscription login itself, nor reuses Claude Code's token.
- **OpenCode: free models only.** They come from its own `opencode` provider at a cost of 0, and use OpenCode's own agent, the only one the free tier answers.
- **Every failure leaves the engine's words.** No test calls a real model except `tests/test_ai_live.py`, which is marked `live` and needs `DEEPMURIM_LIVE=1`.
- **Off costs nothing:** with the AI off there is no server, no backend, and no subprocess.
- **The MCP server never writes,** and reads the save anew for every request.
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Switching backend or model while a reply is pending:** the turn keeps its own words, and the old backend is closed. Task 2 pins it with `test_f1_opens_the_menu_and_its_changes_reach_the_game`.
2. **Claude Code logged out, or OpenCode's free tier refusing:** the reason is remembered, and the menu and the Connect page say why. Task 1 pins it with `test_claude_code_failures_are_none_and_a_logged_out_one_closes_the_door` and `test_opencodes_errors_are_none_and_remembered`.
3. **The game writing while the server is read:** the server sees the new state and never changes the save. Task 3 pins it with `test_the_live_server_answers_over_http_and_reads_the_save_anew` and `test_the_server_never_writes_the_save`.
4. **A price of 0 that isn't free** (a preset, a router, a coding plan): never offered. Task 2 pins it with `test_only_the_free_and_living_models_are_offered`.
5. **Closing the game or turning the AI off:** the server stops and the port is freed. Task 3 pins it with `test_the_server_runs_while_the_ai_is_on` and `test_the_server_stops_with_the_game_and_is_not_started_while_off`.

## Plan-time rulings (found while building, argued)

1. **OpenCode's free tier answers only OpenCode's own agent** ("OpenCode's free tier can only be used from within OpenCode"), so the lean agent the amendment first named is out. Each call carries OpenCode's own prompt, and a warm `opencode serve` brings a paragraph to about 8 s (15 s cold, 18 s without the server). *Cost if wrong:* slower OpenCode prose.
2. **`opencode.exe` is run directly, never the npm `.cmd` shim:** `cmd.exe` read the prompt's `<` and `>` as redirections ("The system cannot find the file specified"). *Cost if wrong:* none.
3. **OpenCode runs in the game's own folder (`logs/opencode`), never under the system's Temp directory,** where it silently answered nothing. *Cost if wrong:* none.
4. **"Free" means OpenCode's own `opencode` provider at a cost of 0.** A cost of 0 alone also matched a DeepSeek preset, OpenRouter's routers and a z.ai coding plan, which are billed elsewhere. *Cost if wrong:* a free model of another provider is not offered.
5. **OpenCode's prose prompt says "Use no tools."** The warm server's config offers the MCP tools to every call, and the model reached for them even for prose. *Cost if wrong:* none.
6. **The Agent SDK keeps one client per job, and each call opens a fresh session** (`query(..., session_id=...)`). That is about 3.5 s a paragraph after a 1 s connect, with no history growing. *Cost if wrong:* none measured.
7. **F1 opens a menu; picking "Mode" cycles it by 6a's rules.** The 6a tests that pressed F1 now open the menu, pick the first line, and close it. *Cost if wrong:* none.
8. **Prefetch is built and tested in 6b but first used in 6c,** whose jobs (typed actions, talk) it serves. *Cost if wrong:* none.
9. **The live tests also cover `claude -p` (6a's door), still used where no backend is chosen.** *Cost if wrong:* none.
10. **The long-lived server lives in `mcp_server/live.py`, not `http.py`.** `claude -p` runs `mcp_server/server.py` as a script, which puts `mcp_server/` first on the import path, and a module named `http` there shadowed the standard library's (6a's stdio server then died at start). *Cost if wrong:* none.

## Files

| File | Responsibility |
|---|---|
| `ai/backends.py` | `Backend`, `ClaudeCode` (the Agent SDK), `OpenCode` (a warm `opencode serve`), `opencode_exe`, `last_json`. |
| `ai/models.py` | Claude Code's models; OpenCode's free ones (`parse_verbose`, `free`, `OpenCodeModels`). |
| `ai/menu.py` | `AiMenu`, `make_backend`, `chosen`, `connect_lines`. |
| `mcp_server/live.py` | `LiveServer`: the MCP server over HTTP, in a thread of the game. |
| `ai/prefetch.py` | `build_prefetch(game, typed, focus)`. |

Existing files touched: `requirements.txt`, `config.py`, `app.py`, `ai/narrate.py`, `mcp_server/server.py`, `engine/game.py`, `docs/world-events.md`, and the tests `test_ai_narration.py`, `test_ai_minors.py`, `test_ai_review.py`, `test_ai_debug.py`, `test_ai_live.py`.

**Before Task 1:** install the new dependency with `.venv/Scripts/python.exe -m pip install "claude-agent-sdk>=0.2"`.

**How each task is laid out:**
1. The tests, as whole new files.
2. The red run.
3. The new modules, as whole files.
4. One patch script, `.patches/6b_taskN.py`, holding the task's edits to existing files. Each edit asserts that its anchor matches exactly once.
5. The green run, the full suite, and the commit.

---

### Task 1: Two backends: Claude Code through the Agent SDK, and OpenCode

A `Backend` base keeps 6a's rules (every failure is None and remembered; three in a row pause it; a logged-out reply closes it with the reason). `ClaudeCode` keeps one Agent SDK client per job open on a background event loop, each call a fresh session, `ANTHROPIC_API_KEY` taken out of its environment (ruling 6). `OpenCode` keeps a hidden `opencode serve` warm and attaches each `opencode run` to it, with OpenCode's own agent (ruling 1), calling `opencode.exe` itself (ruling 2) from the game's own folder (ruling 3), the job's JSON shape in the message, and "Use no tools." for prose (ruling 5). `claude-agent-sdk` joins `requirements.txt`.

**Files:**
- Create: `ai/backends.py`
- Create: `tests/test_ai_backends.py`
- Modify (by `.patches/6b_task1.py`): `requirements.txt`

**Interfaces:**
- Consumes: 6a's `ai.bridge` (`Job`, `Exchange`, `conforms`, `run_command`, `KEPT`, `LOGGED_OUT`, `PAUSE_AFTER`, `PAUSE_SECONDS`); the Agent SDK's `ClaudeSDKClient`, `ClaudeAgentOptions`, `ThinkingConfigDisabled`.
- Produces:
  - `ai.backends`: `MAX_ARGUMENT`; `Backend` (`available()`, `paused()`, `call(job, prompt)`, `_ask(job, prompt) -> (reply, error)`, `close()`, `exchanges`, `just_paused`, `mcp_url`); `ClaudeCode(models=None, client_factory=None)` (`options(job)`); `opencode_exe() -> str | None`; `free_port()`; `last_json(events) -> (reply, error)`; `OpenCode(models=None, exe=None, runner, popen, workdir=None)` (`warm() -> url`, `config()`, `prompt(job, prompt)`, `model(job)`).

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_backends.py`:
```python
import json
import subprocess

from ai.backends import ClaudeCode, OpenCode, free_port, last_json, opencode_exe
from ai.bridge import PAUSE_AFTER, Job

PROSE = {"type": "object", "properties": {"prose": {"type": "string", "maxLength": 1500}}, "required": ["prose"],
         "additionalProperties": False}
NARRATE = Job("narrate", "claude-haiku-4-5", 10.0, PROSE, "Write prose.")
TALK = Job("intent", "claude-sonnet-5", 30.0, PROSE, "Interpret.", tools=True)


# --- Claude Code through the Agent SDK ------------------------------------------------------------------------------

class ResultMessage:
    def __init__(self, structured_output=None, result="", is_error=False, errors=None):
        self.structured_output, self.result, self.is_error, self.errors = structured_output, result, is_error, errors


class FakeClient:
    """Stands in for the SDK's ClaudeSDKClient: answers each query from a script."""
    made: list = []

    def __init__(self, options, script=None):
        self.options, self.script, self.sessions = options, list(script or []), []
        FakeClient.made.append(self)

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def query(self, prompt, session_id="default"):
        self.sessions.append((session_id, prompt))

    async def receive_response(self):
        yield object()  # an assistant message first, as the SDK sends
        yield self.script.pop(0)


def claude(script, **kw):
    FakeClient.made = []
    return ClaudeCode(client_factory=lambda options: FakeClient(options, script), **kw)


def test_claude_code_answers_with_the_structured_reply_each_in_a_fresh_session():
    door = claude([ResultMessage({"prose": "Mist."}), ResultMessage({"prose": "Rain."})])
    assert door.call(NARRATE, "first") == {"prose": "Mist."}
    assert door.call(NARRATE, "second") == {"prose": "Rain."}
    [client] = FakeClient.made  # one client for the job, kept open
    assert [s for s, _ in client.sessions] == ["dm-1", "dm-2"]
    door.close()


def test_claude_code_runs_on_the_plan_never_an_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    door = claude([ResultMessage({"prose": "x"})], models={"narrate": "claude-sonnet-5"})
    door.call(NARRATE, "p")
    options = FakeClient.made[0].options
    assert "ANTHROPIC_API_KEY" not in options.env and options.model == "claude-sonnet-5"
    assert options.setting_sources == [] and options.tools == [] and options.mcp_servers == {}
    assert options.output_format == {"type": "json_schema", "schema": PROSE}
    door.close()


def test_claude_code_gives_tools_only_to_a_tooled_job_with_a_server():
    door = claude([ResultMessage({"prose": "x"}), ResultMessage({"prose": "y"})])
    door.mcp_url = "http://127.0.0.1:5000/mcp"
    door.call(NARRATE, "p")
    door.call(TALK, "q")
    prose, talk = FakeClient.made
    assert prose.options.mcp_servers == {} and prose.options.allowed_tools == []
    assert talk.options.mcp_servers == {"deepmurim": {"type": "http", "url": "http://127.0.0.1:5000/mcp"}}
    assert talk.options.allowed_tools == ["mcp__deepmurim__*"]
    door.close()


def test_claude_code_failures_are_none_and_a_logged_out_one_closes_the_door():
    door = claude([ResultMessage(is_error=True, result="Invalid API key · Please run /login"),
                   ResultMessage({"verse": "wrong shape"})])
    assert door.call(NARRATE, "p") is None
    assert door.available()[0] is False and "not logged in" in door.available()[1]
    door._checked = None
    assert door.call(NARRATE, "p") is None and door.exchanges[-1].error == "the reply did not fit its schema"
    door.close()


def test_claude_code_pauses_after_three_failures():
    door = claude([ResultMessage(is_error=True, result="overloaded")] * PAUSE_AFTER)
    for _ in range(PAUSE_AFTER):
        door.call(NARRATE, "p")
    assert door.paused() and door.just_paused
    door.close()


# --- OpenCode ---------------------------------------------------------------------------------------------------

EVENTS = [
    {"type": "step_start", "part": {}},
    {"type": "text", "part": {"type": "text", "text": "Here you go:\n```json\n{\"prose\": \"You climb the pass.\"}\n```"}},
    {"type": "step_finish", "part": {"tokens": {"input": 100669, "output": 168}, "cost": 0}},
]


def test_the_json_is_found_in_opencodes_last_text():
    assert last_json(EVENTS) == ({"prose": "You climb the pass."}, "")
    error = [{"type": "error", "error": {"name": "APIError", "data": {"message": "free tier only from OpenCode"}}}]
    assert last_json(error) == (None, "free tier only from OpenCode")
    assert last_json([{"type": "text", "part": {"text": "no braces"}}]) == (None, "no JSON in the reply")


def test_opencodes_exe_is_found_beside_its_shim_never_the_shim(tmp_path, monkeypatch):
    shim = tmp_path / "opencode.cmd"
    shim.write_text("@echo off")
    exe = tmp_path / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setattr("shutil.which", lambda name: str(shim) if name == "opencode.cmd" else None)
    assert opencode_exe() == str(exe)
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert opencode_exe() is None and OpenCode(exe=None).available() == (False, "OpenCode is not installed")


class Server:
    pid = 4321

    def __init__(self, *a, **kw):
        self.cmd, self.kw = a[0], kw

    def poll(self):
        return None


def test_opencode_warms_a_server_and_attaches_each_call(tmp_path, monkeypatch):
    calls = []

    def runner(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, "\n".join(json.dumps(e) for e in EVENTS), "")
    servers = []

    def popen(cmd, **kw):
        servers.append(Server(cmd, **kw))
        return servers[-1]
    monkeypatch.setattr("socket.create_connection", lambda *a, **kw: __import__("contextlib").nullcontext())
    door = OpenCode(models={"narrate": "opencode/big-pickle"}, exe="opencode.exe", runner=runner, popen=popen,
                    workdir=tmp_path)
    door.mcp_url = "http://127.0.0.1:5000/mcp"
    assert door.call(NARRATE, "a misty pass") == {"prose": "You climb the pass."}
    assert door.call(NARRATE, "again") == {"prose": "You climb the pass."}
    assert len(servers) == 1 and servers[0].cmd[:2] == ["opencode.exe", "serve"]
    cmd = calls[0][0]
    assert cmd[:4] == ["opencode.exe", "run", "--attach", door.url] and cmd[cmd.index("-m") + 1] == "opencode/big-pickle"
    assert '"prose"' in cmd[-1] and "a misty pass" in cmd[-1]  # the schema rides in the message
    assert "Use no tools." in cmd[-1]  # prose needs none, though the server offers them
    written = json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8"))
    assert written["mcp"]["deepmurim"] == {"type": "remote", "url": "http://127.0.0.1:5000/mcp", "enabled": True}


def test_opencodes_errors_are_none_and_remembered(tmp_path, monkeypatch):
    def runner(cmd, **kw):
        out = json.dumps({"type": "error", "error": {"data": {"message": "rate limited"}}})
        return subprocess.CompletedProcess(cmd, 1, out, "")
    monkeypatch.setattr("socket.create_connection", lambda *a, **kw: __import__("contextlib").nullcontext())
    door = OpenCode(exe="opencode.exe", runner=runner, popen=Server, workdir=tmp_path)
    assert door.call(NARRATE, "p") is None and door.exchanges[-1].error == "rate limited"


def test_a_free_port_is_a_port():
    assert 0 < free_port() < 65536
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_backends.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'ai.backends'`.

- [ ] **Step 3: Write the new modules**

`ai/backends.py`:
```python
"""The two doors to a model (phase 6 spec 13.1): Claude Code through the Claude Agent SDK, and OpenCode.

Both answer `call(job, prompt) -> dict | None` with 6a's rules: any failure returns None (the caller keeps the
engine's words), every exchange is remembered, three failures in a row pause the door for five minutes.

- `ClaudeCode` runs Claude Code on the user's own login (their Pro/Max plan) through the Agent SDK, one client per
  job kept open for the game, each call a fresh session (no history grows). `ANTHROPIC_API_KEY` is taken out of
  its environment, which would switch Claude Code to API billing.
- `OpenCode` keeps a hidden `opencode serve` warm and attaches each `opencode run` to it, with OpenCode's own agent
  (its free models answer no other). `opencode.exe` is run directly, never the npm `.cmd` shim.
"""

import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from ai.bridge import KEPT, LOGGED_OUT, PAUSE_AFTER, PAUSE_SECONDS, Exchange, Job, conforms, run_command

MAX_ARGUMENT = 24000  # Windows caps a command line near 32,000 characters; a prompt is far smaller


class Backend:
    """What every door shares: the pause, the remembered exchanges, the logged-out check."""

    name = "backend"

    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.failures = 0
        self.paused_until = 0.0
        self.just_paused = False
        self.exchanges: deque[Exchange] = deque(maxlen=KEPT)
        self.mcp_url: str | None = None  # the long-lived DeepMurim MCP server (phase 6b Task 3)
        self._checked: tuple[bool, str] | None = None

    def available(self) -> tuple[bool, str]:
        if self._checked is None:
            self._checked = self._check()
        return self._checked

    def _check(self) -> tuple[bool, str]:
        return True, ""

    def paused(self) -> bool:
        return self.clock() < self.paused_until

    def call(self, job: Job, prompt: str) -> dict | None:
        if self.paused() or not self.available()[0]:
            return None
        start = self.clock()
        try:
            reply, error = self._ask(job, prompt)
        except Exception as exc:  # a door never breaks the game: the engine's words stand
            reply, error = None, f"{self.name} failed ({exc.__class__.__name__}: {str(exc)[:120]})"
        if reply is not None and not conforms(job.schema, reply):
            reply, error = None, "the reply did not fit its schema"
        self.exchanges.append(Exchange(job.name, prompt, reply, error, round(self.clock() - start, 2)))
        self._count(reply is not None, error)
        return reply

    def _ask(self, job: Job, prompt: str) -> tuple[dict | None, str]:
        raise NotImplementedError

    def _count(self, ok: bool, error: str) -> None:
        if any(word in error.lower() for word in LOGGED_OUT):
            self._checked = (False, f"{self.name} is not logged in")
        if ok:
            self.failures = 0
            return
        self.failures += 1
        if self.failures >= PAUSE_AFTER:
            self.failures = 0
            self.paused_until = self.clock() + PAUSE_SECONDS
            self.just_paused = True

    def close(self) -> None:
        pass


# --- Claude Code, through the Agent SDK -------------------------------------------------------------------------

class ClaudeCode(Backend):
    name = "Claude Code"

    def __init__(self, models: dict | None = None, client_factory=None, clock=time.monotonic) -> None:
        super().__init__(clock)
        self.models = dict(models or {})  # job name -> model; else the job's own
        self._factory = client_factory  # tests hand in a fake; the real one is the SDK's ClaudeSDKClient
        self._clients: dict[str, object] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._calls = 0

    def _check(self) -> tuple[bool, str]:
        if self._factory is None and shutil.which("claude") is None:  # the SDK runs the user's Claude Code
            return False, "Claude Code is not installed"
        return True, ""

    def options(self, job: Job):
        from claude_agent_sdk import ClaudeAgentOptions, ThinkingConfigDisabled
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}  # the user's plan, never the API's
        mcp = {"deepmurim": {"type": "http", "url": self.mcp_url}} if job.tools and self.mcp_url else {}
        return ClaudeAgentOptions(
            model=self.models.get(job.name, job.model), system_prompt=job.system, tools=[],
            allowed_tools=["mcp__deepmurim__*"] if mcp else [], mcp_servers=mcp, strict_mcp_config=True,
            setting_sources=[], effort="low", max_turns=8 if mcp else 3, env=env,
            thinking=None if job.thinking else ThinkingConfigDisabled(type="disabled"),
            output_format={"type": "json_schema", "schema": job.schema})

    def _run(self, coro, timeout: float):
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            threading.Thread(target=self._loop.run_forever, name="claude-code", daemon=True).start()
        return asyncio.run_coroutine_threadsafe(asyncio.wait_for(coro, timeout), self._loop).result(timeout + 5)

    async def _client(self, job: Job):
        key = f"{job.name}:{self.models.get(job.name, job.model)}"
        if key not in self._clients:
            if self._factory is None:
                from claude_agent_sdk import ClaudeSDKClient
                self._factory = ClaudeSDKClient
            client = self._factory(self.options(job))
            await client.connect()
            self._clients[key] = client
        return self._clients[key]

    async def _exchange(self, job: Job, prompt: str) -> tuple[dict | None, str]:
        client = await self._client(job)
        self._calls += 1
        await client.query(prompt, session_id=f"dm-{self._calls}")  # a fresh session: no history grows
        async for message in client.receive_response():
            if type(message).__name__ != "ResultMessage":
                continue
            if message.is_error:
                return None, str(message.result or message.errors or "an error")[:200]
            reply = message.structured_output
            if reply is None and message.result:
                try:
                    reply = json.loads(message.result)
                except ValueError:
                    return None, "no structured reply"
            return reply, ""
        return None, "no result"

    def _ask(self, job: Job, prompt: str) -> tuple[dict | None, str]:
        try:
            return self._run(self._exchange(job, prompt), job.timeout)
        except (TimeoutError, asyncio.TimeoutError):
            return None, f"no reply within {job.timeout:.0f} s"

    def close(self) -> None:
        loop, self._loop = self._loop, None
        if loop is None:
            return
        for client in self._clients.values():
            try:
                asyncio.run_coroutine_threadsafe(client.disconnect(), loop).result(5)
            except Exception:
                pass
        self._clients = {}
        loop.call_soon_threadsafe(loop.stop)


# --- OpenCode -----------------------------------------------------------------------------------------------------

def opencode_exe() -> str | None:
    """`opencode.exe` itself: beside an npm install's shim, or on PATH. Never the `.cmd` (cmd.exe would read the
    prompt's `<` and `>` as redirections)."""
    for found in (shutil.which("opencode.cmd"), shutil.which("opencode")):
        if found:
            exe = Path(found).parent / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
            if exe.is_file():
                return str(exe)
    found = shutil.which("opencode.exe")
    return found


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def last_json(events: list[dict]) -> tuple[dict | None, str]:
    """The job's JSON from `opencode run --format json` events: the last text part, fences and chatter around it
    stripped."""
    for event in events:
        if event.get("type") == "error":
            data = event.get("error", {}).get("data", {})
            return None, str(data.get("message") or event.get("error"))[:200]
    texts = [e["part"]["text"] for e in events if e.get("type") == "text" and e.get("part", {}).get("text")]
    if not texts:
        return None, "no reply"
    found = re.search(r"\{.*\}", texts[-1], re.S)
    if found is None:
        return None, "no JSON in the reply"
    try:
        return json.loads(found.group(0)), ""
    except ValueError:
        return None, "the reply was not JSON"


class OpenCode(Backend):
    name = "OpenCode"
    STARTUP = 30.0

    def __init__(self, models: dict | None = None, exe: str | None = None, runner=run_command, popen=subprocess.Popen,
                 workdir: Path | None = None, clock=time.monotonic) -> None:
        super().__init__(clock)
        self.models = dict(models or {})
        self.exe = exe if exe is not None else opencode_exe()
        self.runner, self.popen = runner, popen
        # Where opencode.json (the MCP entry) is written and the server runs: the game's own folder. Under the
        # system's Temp directory OpenCode silently answers nothing (plan ruling).
        self.workdir = Path(workdir) if workdir else None
        self.server = None
        self.url: str | None = None

    def _check(self) -> tuple[bool, str]:
        return (True, "") if self.exe else (False, "OpenCode is not installed")

    def model(self, job: Job) -> str:
        return self.models.get(job.name) or "opencode/big-pickle"

    def config(self) -> dict:
        """The opencode.json beside the warm server: the DeepMurim MCP server, when it runs."""
        mcp = {"deepmurim": {"type": "remote", "url": self.mcp_url, "enabled": True}} if self.mcp_url else {}
        return {"$schema": "https://opencode.ai/config.json", "mcp": mcp}

    def warm(self) -> str:
        """Start the hidden `opencode serve` (once) and return its address."""
        if self.server is not None and self.server.poll() is None:
            return self.url
        if self.workdir is not None:
            self.workdir.mkdir(parents=True, exist_ok=True)
            (self.workdir / "opencode.json").write_text(json.dumps(self.config(), indent=2), encoding="utf-8")
        port = free_port()
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.server = self.popen([self.exe, "serve", "--port", str(port), "--hostname", "127.0.0.1"],
                                 cwd=str(self.workdir) if self.workdir else None, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, creationflags=flags)
        self.url = f"http://127.0.0.1:{port}"
        deadline = self.clock() + self.STARTUP
        while self.clock() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    return self.url
            except OSError:
                time.sleep(0.2)
        raise TimeoutError("opencode serve did not start")

    def prompt(self, job: Job, prompt: str) -> str:
        """OpenCode has no schema flag: the job's instructions and its JSON shape go in the message."""
        tools = "" if job.tools else "Use no tools. "  # the warm server's config offers them to every call
        text = (f"{job.system}\n\n{tools}Reply with only one JSON object fitting this JSON Schema, and nothing "
                f"else:\n{json.dumps(job.schema)}\n\n{prompt}")
        return text[:MAX_ARGUMENT]

    def _ask(self, job: Job, prompt: str) -> tuple[dict | None, str]:
        url = self.warm()
        cmd = [self.exe, "run", "--attach", url, "--format", "json", "-m", self.model(job), self.prompt(job, prompt)]
        try:
            done = self.runner(cmd, capture_output=True, text=True, encoding="utf-8", timeout=job.timeout)
        except subprocess.TimeoutExpired:
            return None, f"no reply within {job.timeout:.0f} s"
        events = []
        for line in (done.stdout or "").splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
        reply, error = last_json(events)
        if reply is None and done.returncode and not error:
            error = (done.stderr or f"exit {done.returncode}").strip()[:200]
        return reply, error

    def close(self) -> None:
        server, self.server = self.server, None
        if server is not None and server.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(server.pid)], capture_output=True)
            else:
                server.kill()
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6b_task1.py`:
```python
"""Phase 6b, Task 1: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('requirements.txt', r'''mcp>=2.2
''', r'''mcp>=2.2
claude-agent-sdk>=0.2
''')
print("task 1 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6b_task1.py`
Expected: `task 1 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_backends.py tests/test_ai_bridge.py`
Expected: `19 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow and live ones are deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: two backends - Claude Code through the Agent SDK on the player's plan, and OpenCode kept warm

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: The AI menu, and OpenCode's free models

F1 opens a menu (ruling 7): the mode (cycled by 6a's rules), the backend, the model for prose and the model for typed actions and talk (6c). Claude Code offers Haiku 4.5, Sonnet 5 and Opus 5.5; OpenCode only its own free models, read once from `opencode models --verbose` (ruling 4). Choices are saved (`ai_backend`, `ai_models`); a change of backend or model settles the waiting turn and builds the backend anew. The 6a tests that pressed F1 now go through the menu.

**Files:**
- Create: `ai/menu.py`
- Create: `ai/models.py`
- Create: `tests/test_ai_menu.py`
- Modify (by `.patches/6b_task2.py`): `ai/narrate.py`, `app.py`, `config.py`, `tests/test_ai_minors.py`, `tests/test_ai_narration.py`, `tests/test_ai_review.py`

**Interfaces:**
- Consumes: Task 1's `ClaudeCode`, `OpenCode`, `opencode_exe`; 6a's `Narration`, `App._cycle_ai`.
- Produces:
  - `ai.models`: `CLAUDE_MODELS`, `CLAUDE_DEFAULTS`, `OPENCODE_DEFAULT`, `parse_verbose(text)`, `free(models)`, `OpenCodeModels(exe, runner)` (`free()`), `label(backend, model)`.
  - `ai.menu`: `BACKENDS`, `ROLES`, `chosen(config, backend=None)`, `make_backend(config, workdir=None)`, `connect_lines(mcp_url)`, `AiMenu(config, opencode_models=None, mcp_url=None)` (`choices()`, `lines()`, `pick(n) -> 'mode' | 'backend' | 'model' | 'close' | None`, `page`).
  - `Config.ai_backend`, `Config.ai_models`; `Narration(bridge, mode, factory)`, `Narration.set_backend`; `App.ai_menu`, `App._backend()`, `App._menu_key()`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_menu.py`:
```python
import json
import subprocess

from ai.backends import ClaudeCode, OpenCode
from ai.fake import FakeClaude
from ai.menu import AiMenu, chosen, connect_lines, make_backend
from ai.models import OpenCodeModels, free, parse_verbose
from app import App
from config import Config, config_from
from systems.creation import CreationChoice

VERBOSE = """opencode/big-pickle
{
  "id": "big-pickle",
  "status": "active",
  "cost": {
    "input": 0,
    "output": 0
  }
}
opencode/old-free
{
  "id": "old-free",
  "status": "deprecated",
  "cost": {"input": 0, "output": 0}
}
openrouter/~anthropic/claude-sonnet-latest
{
  "id": "claude-sonnet-latest",
  "cost": {
    "input": 3,
    "output": 15
  }
}
opencode/space-bunny-free
{
  "id": "space-bunny-free",
  "cost": {"input": 0, "output": 0}
}
zai-coding-plan/glm-5.3
{
  "id": "glm-5.3",
  "providerID": "zai-coding-plan",
  "cost": {"input": 0, "output": 0}
}
"""


def test_only_the_free_and_living_models_are_offered():
    models = parse_verbose(VERBOSE)
    assert set(models) == {"opencode/big-pickle", "opencode/old-free", "openrouter/~anthropic/claude-sonnet-latest",
                           "opencode/space-bunny-free", "zai-coding-plan/glm-5.3"}
    assert free(models) == ["opencode/big-pickle", "opencode/space-bunny-free"]  # a plan billed elsewhere is no gift


def test_opencode_is_asked_once_and_a_failure_offers_none():
    calls = []

    def runner(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, VERBOSE, "")
    found = OpenCodeModels("opencode.exe", runner)
    assert found.free() == found.free() == ["opencode/big-pickle", "opencode/space-bunny-free"]
    assert calls == [["opencode.exe", "models", "--verbose"]]

    def broken(cmd, **kw):
        raise OSError("gone")
    assert OpenCodeModels("opencode.exe", broken).free() == [] and OpenCodeModels(None).free() == []


def menu(config=None, models=("opencode/big-pickle", "opencode/space-bunny-free")):
    found = OpenCodeModels(None)
    found._found = list(models)
    return AiMenu(config or Config(), found, mcp_url=lambda: "http://127.0.0.1:5000/mcp")


def test_the_menu_switches_the_backend_and_cycles_its_models():
    config = Config()
    m = menu(config)
    assert m.choices()[:4] == ["Mode: off", "Backend: Claude Code", "Prose model: Haiku 4.5",
                               "Typed actions and talk (6c): Sonnet 5"]
    assert m.pick(3) == "model" and chosen(config)["narrate"] == "claude-sonnet-5"
    assert m.pick(2) == "backend" and config.ai_backend == "opencode"
    assert m.choices()[2] == "Prose model: big-pickle"
    m.pick(3)
    assert chosen(config)["narrate"] == "opencode/space-bunny-free"
    assert chosen(config, "claude_code")["narrate"] == "claude-sonnet-5"  # each backend keeps its own
    assert any("Only OpenCode's free models" in t for t, _ in m.lines())
    assert m.pick(1) == "mode" and m.pick(6) == "close"


def test_the_connect_page_tells_how_to_reach_the_server(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    m = menu()
    assert m.pick(5) is None and m.page == "connect" and m.choices() == ["Back"]
    text = "\n".join(t for t, _ in m.lines())
    assert "claude mcp add --transport http deepmurim http://127.0.0.1:5000/mcp" in text
    assert '"type": "remote", "url": "http://127.0.0.1:5000/mcp"' in text
    assert "ANTHROPIC_API_KEY is set" in text
    m.pick(1)
    assert m.page == "main"
    assert any("Not running" in t for t, _ in connect_lines(None))


def test_the_backend_is_built_from_the_settings(tmp_path):
    config = Config(ai_backend="opencode", ai_models={"opencode": {"narrate": "opencode/space-bunny-free"}})
    door = make_backend(config, tmp_path)
    assert isinstance(door, OpenCode) and door.models["narrate"] == "opencode/space-bunny-free"
    assert door.models["intent"] == door.models["dialogue"] == "opencode/big-pickle"
    assert isinstance(make_backend(Config()), ClaudeCode)


def test_the_choice_of_backend_and_models_is_saved_and_read_back():
    stored = {"ai_backend": "opencode", "ai_models": {"opencode": {"narrate": "opencode/space-bunny-free"},
                                                       "nonsense": {"narrate": 3}}}
    config = config_from(stored)
    assert config.ai_backend == "opencode" and config.ai_models == {"opencode": {"narrate": "opencode/space-bunny-free"}}
    assert config_from({"ai_backend": "gpt"}).ai_backend == "claude_code"


def test_f1_opens_the_menu_and_its_changes_reach_the_game(tmp_path):
    fake = FakeClaude()
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs", bridge=fake)
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    app.handle_key("f1", "")
    assert app.ai_menu is not None
    grid_text = "\n".join("".join(cell[0] if cell else " " for cell in row) for row in app.grid(120, 40))
    assert "THE AI (F1 closes)" in grid_text and "Backend: Claude Code" in grid_text
    app.ai_menu.opencode._found = ["opencode/big-pickle"]
    app.handle_key("2", "2")  # the backend
    assert app.config.ai_backend == "opencode" and app.narration._bridge is None  # built anew when next asked
    assert json.loads((tmp_path / "settings.json").read_text())["ai_backend"] == "opencode"
    app.handle_key("1", "1")  # the mode
    assert app.config.ai_mode == "assist"
    app.handle_key("escape", "\x1b")
    assert app.ai_menu is None
    app.shutdown()
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_menu.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'ai.menu'`.

- [ ] **Step 3: Write the new modules**

`ai/menu.py`:
```python
"""The AI menu (phase 6 spec 13.2-13.3), opened with F1: the mode, the backend, the models, and the Connect page.

Pure state: it reads and changes the settings (`Config.ai_mode`, `ai_backend`, `ai_models`) and says what changed;
the App applies it (a new backend, the mode's own rules) and saves.
"""

import os
import shutil

from ai.backends import ClaudeCode, OpenCode, opencode_exe
from ai.models import CLAUDE_DEFAULTS, CLAUDE_MODELS, OPENCODE_DEFAULT, OpenCodeModels, label

BACKENDS = (("claude_code", "Claude Code"), ("opencode", "OpenCode"))
MODES = ("off", "assist", "ai_only")
MODE_NAMES = {"off": "off", "assist": "assist (the engine's words first, then the model's)",
              "ai_only": "AI only (only the model's words)"}
ROLES = (("narrate", "Prose model"), ("talk", "Typed actions and talk (6c)"))


def chosen(config, backend: str | None = None) -> dict:
    """The models chosen for a backend: {'narrate': ..., 'talk': ...}, defaults filled in."""
    backend = backend or config.ai_backend
    picked = dict((config.ai_models or {}).get(backend, {}))
    if backend == "opencode":
        return {"narrate": picked.get("narrate", OPENCODE_DEFAULT), "talk": picked.get("talk", OPENCODE_DEFAULT)}
    return {"narrate": picked.get("narrate", CLAUDE_DEFAULTS["narrate"]),
            "talk": picked.get("talk", CLAUDE_DEFAULTS["talk"])}


def make_backend(config, workdir=None):
    """The backend the settings name, with its models per job."""
    models = chosen(config)
    per_job = {"narrate": models["narrate"], "intent": models["talk"], "dialogue": models["talk"]}
    if config.ai_backend == "opencode":
        return OpenCode(models=per_job, workdir=workdir)
    return ClaudeCode(models=per_job)


def connect_lines(mcp_url: str | None) -> list:
    """How to reach the models, and how to reach DeepMurim from them (spec 13.3)."""
    claude, exe = shutil.which("claude"), opencode_exe()
    lines = [("Connect", "heading"),
             (f"  Claude Code: {'installed' if claude else 'not installed (claude.com/claude-code)'}", "default")]
    if claude:
        lines.append(("    Uses your own Claude login (your Pro/Max plan). Sign in once by running `claude` and "
                      "typing /login.", "dim"))
    if os.environ.get("ANTHROPIC_API_KEY"):
        lines.append(("    Warning: ANTHROPIC_API_KEY is set on this machine. DeepMurim leaves it out, so your plan "
                      "is used, but other Claude Code sessions will bill the API.", "red"))
    lines.append((f"  OpenCode: {'installed' if exe else 'not installed (opencode.ai)'}", "default"))
    if exe:
        lines.append(("    DeepMurim lists only OpenCode's free models. Sign in with `opencode auth login` if a "
                      "model asks for it.", "dim"))
    lines += [("", "default"), ("DeepMurim's MCP server (the world as you know it, read-only)", "heading")]
    if mcp_url:
        lines += [(f"  Running at {mcp_url}", "default"),
                  ("  To use it from your own Claude Code session:", "dim"),
                  (f"    claude mcp add --transport http deepmurim {mcp_url}", "default"),
                  ("  From OpenCode, add to opencode.json:", "dim"),
                  (f'    "mcp": {{"deepmurim": {{"type": "remote", "url": "{mcp_url}"}}}}', "default")]
    else:
        lines.append(("  Not running: it starts when the AI is on (mode assist or AI only).", "dim"))
    return lines


class AiMenu:
    def __init__(self, config, opencode_models: OpenCodeModels | None = None, mcp_url=None) -> None:
        self.config = config
        self.page = "main"
        self.opencode = opencode_models or OpenCodeModels(opencode_exe())
        self.mcp_url = mcp_url  # a callable: the server's address now, or None

    def models(self, backend: str) -> list[str]:
        if backend == "opencode":
            return self.opencode.free() or [OPENCODE_DEFAULT]
        return [m for m, _ in CLAUDE_MODELS]

    def choices(self) -> list[str]:
        if self.page == "connect":
            return ["Back"]
        c, backend = self.config, self.config.ai_backend
        models = chosen(c)
        return [f"Mode: {c.ai_mode}", f"Backend: {dict(BACKENDS)[backend]}"] + \
            [f"{name}: {label(backend, models[role])}" for role, name in ROLES] + ["Connect...", "Close"]

    def lines(self) -> list:
        if self.page == "connect":
            return connect_lines(self.mcp_url() if callable(self.mcp_url) else self.mcp_url)
        c = self.config
        lines = [("The AI (F1 closes)", "heading"),
                 (f"  Mode: {MODE_NAMES[c.ai_mode]}", "default"),
                 (f"  Backend: {dict(BACKENDS)[c.ai_backend]}", "default")]
        models = chosen(c)
        lines += [(f"  {name}: {label(c.ai_backend, models[role])}", "default") for role, name in ROLES]
        if c.ai_backend == "opencode":
            lines.append(("  Only OpenCode's free models are offered.", "dim"))
        lines += [("", "default"), ("Pick a line to change it.", "dim")]
        return lines

    def pick(self, n: int) -> str | None:
        """What picking choice n did: 'mode', 'backend', 'model', 'close', or None."""
        if self.page == "connect":
            self.page = "main"
            return None
        c = self.config
        if n == 1:
            return "mode"  # the App cycles it, by the mode's own rules (6a)
        if n == 2:
            names = [b for b, _ in BACKENDS]
            c.ai_backend = names[(names.index(c.ai_backend) + 1) % len(names)]
            return "backend"
        if n in (3, 4):
            role = ROLES[n - 3][0]
            options = self.models(c.ai_backend)
            current = chosen(c)[role]
            following = options[(options.index(current) + 1) % len(options)] if current in options else options[0]
            c.ai_models = {**(c.ai_models or {}), c.ai_backend: {**chosen(c), role: following}}
            return "model"
        if n == 5:
            self.page = "connect"
            return None
        if n == 6:
            return "close"
        return None
```

`ai/models.py`:
```python
"""Which models each backend may use (phase 6 spec 13.2): Claude Code's three, and OpenCode's free ones only."""

import json
import subprocess

CLAUDE_MODELS = (("claude-haiku-4-5", "Haiku 4.5"), ("claude-sonnet-5", "Sonnet 5"), ("claude-opus-5-5", "Opus 5.5"))
CLAUDE_DEFAULTS = {"narrate": "claude-haiku-4-5", "talk": "claude-sonnet-5"}
OPENCODE_DEFAULT = "opencode/big-pickle"


def parse_verbose(text: str) -> dict[str, dict]:
    """`opencode models --verbose`: each model's name on a line, then its JSON. {name: its metadata}."""
    models, name, block = {}, None, []
    for line in text.splitlines():
        if block or line.startswith("{"):
            block.append(line)
            if line.startswith("}"):
                try:
                    models[name] = json.loads("\n".join(block))
                except (ValueError, TypeError):
                    pass
                block = []
        elif line.strip() and not line.startswith(" "):
            name = line.strip()
    return {k: v for k, v in models.items() if k}


def free(models: dict[str, dict]) -> list[str]:
    """OpenCode's own free models: of its `opencode` provider, costing nothing, not retired. A price of 0 alone is
    not enough: a preset, a router, or a coding plan billed elsewhere reports 0 too."""
    out = []
    for name, meta in models.items():
        cost = meta.get("cost") or {}
        own = meta.get("providerID", name.split("/", 1)[0]) == "opencode"
        if own and cost.get("input") == 0 and cost.get("output") == 0 and meta.get("status", "active") != "deprecated":
            out.append(name)
    return sorted(out)


class OpenCodeModels:
    """OpenCode's free models, asked of OpenCode once a session."""

    def __init__(self, exe: str | None, runner=subprocess.run) -> None:
        self.exe, self.runner = exe, runner
        self._found: list[str] | None = None

    def free(self) -> list[str]:
        if self._found is None:
            self._found = []
            if self.exe:
                try:
                    done = self.runner([self.exe, "models", "--verbose"], capture_output=True, text=True,
                                       encoding="utf-8", timeout=60)
                    self._found = free(parse_verbose(done.stdout or ""))
                except (OSError, subprocess.SubprocessError):
                    self._found = []
        return list(self._found)


def label(backend: str, model: str) -> str:
    if backend == "claude_code":
        return dict(CLAUDE_MODELS).get(model, model)
    return model.split("/", 1)[-1]
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6b_task2.py`:
```python
"""Phase 6b, Task 2: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('ai/narrate.py', r'''class Narration:
    def __init__(self, bridge: Bridge | None = None, mode: str = "off") -> None:
        self._bridge = bridge
''', r'''class Narration:
    def __init__(self, bridge: Bridge | None = None, mode: str = "off", factory=None) -> None:
        self._bridge = bridge
''')
edit('ai/narrate.py', r'''        self._bridge = bridge
        self.mode = mode if mode in MODES else "off"
''', r'''        self._bridge = bridge
        self._factory = factory  # makes the backend the settings name (phase 6b); a plain Bridge without one
        self.mode = mode if mode in MODES else "off"
''')
edit('ai/narrate.py', r'''        if self._bridge is None:
            self._bridge = Bridge()
        return self._bridge
''', r'''        if self._bridge is None:
            self._bridge = self._factory() if self._factory is not None else Bridge()
        return self._bridge
''')
edit('ai/narrate.py', r'''        return self._bridge

''', r'''        return self._bridge

    def set_backend(self, backend) -> None:
        """Another backend (phase 6b's menu): the old one is closed; None makes the next use build anew."""
        old, self._bridge = self._bridge, backend
        if old is not None and old is not backend and hasattr(old, "close"):
            old.close()

''')
edit('ai/narrate.py', r'''        self.pending = None

''', r'''        self.pending = None
        if self._bridge is not None and hasattr(self._bridge, "close"):
            self._bridge.close()  # a warm OpenCode server, an open Claude Code session

''')
edit('app.py', r'''
from ai.narrate import MODE_WORDS, Narration
''', r'''
from ai.menu import AiMenu, make_backend
from ai.narrate import MODE_WORDS, Narration
''')
edit('app.py', r'''        self._recent_narration: deque[str] = deque(maxlen=4)
        self.narration = Narration(bridge, config.ai_mode)  # phase 6: Claude's prose, F1

''', r'''        self._recent_narration: deque[str] = deque(maxlen=4)
        self.narration = Narration(bridge, config.ai_mode, factory=self._backend)  # phase 6: the model's prose
        self.ai_menu: AiMenu | None = None  # phase 6b: F1

''')
edit('app.py', r'''    def _game_key(self, key: str, text: str) -> None:
        if key == "f1":
            self._cycle_ai()
        elif key == "f2":
''', r'''    def _game_key(self, key: str, text: str) -> None:
        if self.ai_menu is not None:
            self._menu_key(key, text)
        elif key == "f1":
            self.ai_menu = AiMenu(self.config)
        elif key == "f2":
''')
edit('app.py', r'''            self.state, self.name, self.message = "name", "", ""

''', r'''            self.state, self.name, self.message = "name", "", ""

    def _backend(self):
        """The backend the settings name (phase 6b): Claude Code or OpenCode, with the chosen models."""
        return make_backend(self.config, self.logs_dir / "opencode")

    def _menu_key(self, key: str, text: str) -> None:
        if key in ("escape", "f1"):
            self.ai_menu = None
            return
        if len(text) == 1 and text.isdigit():
            done = self.ai_menu.pick(int(text))
            if done == "mode":
                self._cycle_ai()
            elif done in ("backend", "model"):
                self.narration.settle(self.log)
                self.narration.set_backend(None)  # built anew from the settings when next asked
                self._save_settings()
            elif done == "close":
                self.ai_menu = None

''')
edit('app.py', r'''        save_values({"art_side": self.config.art_side, "show_art": self.config.show_art,
                     "ai_mode": self.config.ai_mode}, self.settings_path)

''', r'''        save_values({"art_side": self.config.art_side, "show_art": self.config.show_art,
                     "ai_mode": self.config.ai_mode, "ai_backend": self.config.ai_backend,
                     "ai_models": self.config.ai_models}, self.settings_path)

''')
edit('app.py', r'''            log = self.debug_lines()
        if self.sheet_visible and self.game is not None:
''', r'''            log = self.debug_lines()
        choices = [c.label for c in self.choices]
        if self.ai_menu is not None:
            status, log, choices = "THE AI (F1 closes)", self.ai_menu.lines(), self.ai_menu.choices()
        if self.sheet_visible and self.game is not None:
''')
edit('app.py', r'''            status=status, log=log, art=art,
            choices=[c.label for c in self.choices], command=command,
            art_side=self.config.art_side, show_art=self.config.show_art,
''', r'''            status=status, log=log, art=art,
            choices=choices, command=command,
            art_side=self.config.art_side, show_art=self.config.show_art,
''')
edit('config.py', r'''
from dataclasses import dataclass

''', r'''
from dataclasses import dataclass, field

''')
edit('config.py', r'''    ai_mode: str = "off"  # phase 6: off | assist | ai_only (F1)

''', r'''    ai_mode: str = "off"  # phase 6: off | assist | ai_only (F1)
    ai_backend: str = "claude_code"  # phase 6b: claude_code | opencode
    ai_models: dict = field(default_factory=dict)  # phase 6b: {backend: {"narrate": model, "talk": model}}

''')
edit('config.py', r'''        config.ai_mode = values["ai_mode"]
    return config
''', r'''        config.ai_mode = values["ai_mode"]
    if values.get("ai_backend") in ("claude_code", "opencode"):
        config.ai_backend = values["ai_backend"]
    models = values.get("ai_models")
    if isinstance(models, dict):
        config.ai_models = {b: {r: m for r, m in v.items() if isinstance(m, str)} for b, v in models.items()
                            if b in ("claude_code", "opencode") and isinstance(v, dict)}
    return config
''')
edit('tests/test_ai_minors.py', r'''    assert WAITING in app.log
    app.handle_key("f1", "")  # ai_only -> off
    assert app.narration.mode == "off" and WAITING not in app.log
''', r'''    assert WAITING in app.log
    cycle_mode(app)  # ai_only -> off
    assert app.narration.mode == "off" and WAITING not in app.log
''')
edit('tests/test_ai_minors.py', r'''    assert any("Claude's prose cannot be used" in text for text, _ in app.log)
    app.shutdown()
''', r'''    assert any("Claude's prose cannot be used" in text for text, _ in app.log)
    app.shutdown()


def cycle_mode(app):
    """F1 opens the AI menu (phase 6b); its first line cycles the mode; Esc closes it."""
    app.handle_key("f1", "")
    app.handle_key("1", "1")
    app.handle_key("escape", "\x1b")
''')
edit('tests/test_ai_narration.py', r'''    app, fake = make_app(tmp_path, mode="off")
    app.handle_key("f1", "")
    assert app.narration.mode == "assist" and app.log[-1] == ("AI prose: procedural first, then Claude's.", "system")
''', r'''    app, fake = make_app(tmp_path, mode="off")
    cycle_mode(app)
    assert app.narration.mode == "assist" and app.log[-1] == ("AI prose: procedural first, then Claude's.", "system")
''')
edit('tests/test_ai_narration.py', r'''    assert app.narration.mode == "assist" and app.log[-1] == ("AI prose: procedural first, then Claude's.", "system")
    app.handle_key("f1", "")
    app.handle_key("f1", "")
    assert app.narration.mode == "off"
''', r'''    assert app.narration.mode == "assist" and app.log[-1] == ("AI prose: procedural first, then Claude's.", "system")
    cycle_mode(app)
    cycle_mode(app)
    assert app.narration.mode == "off"
''')
edit('tests/test_ai_narration.py', r'''    assert app.narration.mode == "off"
    app.handle_key("f1", "")
    assert json.loads((tmp_path / "settings.json").read_text())["ai_mode"] == "assist"
''', r'''    assert app.narration.mode == "off"
    cycle_mode(app)
    assert json.loads((tmp_path / "settings.json").read_text())["ai_mode"] == "assist"
''')
edit('tests/test_ai_narration.py', r'''    app, fake = make_app(tmp_path, mode="off", available=False)
    app.handle_key("f1", "")
    assert app.narration.mode == "off"
''', r'''    app, fake = make_app(tmp_path, mode="off", available=False)
    cycle_mode(app)
    assert app.narration.mode == "off"
''')
edit('tests/test_ai_narration.py', r'''    assert sum("rests for five minutes" in text for text, _ in app.log) == 1
    app.shutdown()
''', r'''    assert sum("rests for five minutes" in text for text, _ in app.log) == 1
    app.shutdown()


def cycle_mode(app):
    """F1 opens the AI menu (phase 6b); its first line cycles the mode; Esc closes it."""
    app.handle_key("f1", "")
    app.handle_key("1", "1")
    app.handle_key("escape", "\x1b")
''')
edit('tests/test_ai_review.py', r'''    assert any("not logged in" in text for text, _ in app.log)
    app.handle_key("f1", "")
    assert app.narration.mode == "off"  # F1 now says why and stays off
''', r'''    assert any("not logged in" in text for text, _ in app.log)
    cycle_mode(app)
    assert app.narration.mode == "off"  # F1 now says why and stays off
''')
edit('tests/test_ai_review.py', r'''    game.close()
''', r'''    game.close()


def cycle_mode(app):
    """F1 opens the AI menu (phase 6b); its first line cycles the mode; Esc closes it."""
    app.handle_key("f1", "")
    app.handle_key("1", "1")
    app.handle_key("escape", "\x1b")
''')
print("task 2 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6b_task2.py`
Expected: `task 2 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_menu.py tests/test_ai_narration.py tests/test_ai_minors.py tests/test_ai_review.py tests/test_app.py`
Expected: `39 passed, 1 deselected`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow and live ones are deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: the AI menu - the mode, Claude Code or OpenCode, the models, and only OpenCode's free ones

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: One long-lived MCP server, and the Connect page

While the AI is on and a game is open, `LiveServer` runs the DeepMurim MCP server over streamable HTTP on 127.0.0.1 in a thread of the game; `build(save, fresh=True)` opens the save anew on every request (the game writes meanwhile). Each backend is given its address; the Connect page shows it with the copy-paste setup for Claude Code and OpenCode. The server stops when the AI is turned off or the game closes.

**Files:**
- Create: `mcp_server/live.py`
- Create: `tests/test_ai_server.py`
- Modify (by `.patches/6b_task3.py`): `app.py`, `mcp_server/server.py`

**Interfaces:**
- Consumes: 6a's `mcp_server.server.build`, `World.open_readonly`; Tasks 1-2's backends and `AiMenu`.
- Produces:
  - `mcp_server.live`: `STARTUP`, `free_port()`, `LiveServer(save)` (`start() -> url`, `stop()`, `running`, `url`).
  - `mcp_server.server.build(save, fresh=False)`; `App.mcp`, `App._ai_server()`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_server.py`:
```python
import socket

import anyio
import pytest

import systems.encounters as encounters
from ai.fake import FakeClaude
from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from mcp_server import tools as T
from mcp_server.live import LiveServer
from systems.creation import CreationChoice


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def ask(url: str, tool: str, args: dict | None = None):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def go():
        async with streamable_http_client(url) as streams:
            async with ClientSession(streams[0], streams[1]) as client:
                await client.initialize()
                names = sorted(t.name for t in (await client.list_tools()).tools)
                answer = await client.call_tool(tool, args or {})
                return names, answer.content[0].text
    return anyio.run(go)


def test_the_live_server_answers_over_http_and_reads_the_save_anew(game):
    server = LiveServer(game.world.path)
    url = server.start()
    try:
        assert url.startswith("http://127.0.0.1:") and url.endswith("/mcp")
        names, text = ask(url, "place")
        assert names == sorted(t.__name__ for t in T.TOOLS) and text.startswith(game.place.name)
        game.perform(Action("rest"))  # the game writes while the server runs
        _, text = ask(url, "chronicle", {"query": "rest"})
        assert "rest" in text.lower()  # the next request sees it
        assert server.start() == url  # once
    finally:
        server.stop()
    port = int(url.split(":")[2].split("/")[0])
    with socket.socket() as s:
        assert s.connect_ex(("127.0.0.1", port)) != 0  # stopped


def test_the_server_never_writes_the_save(game):
    game.world._conn.execute("pragma wal_checkpoint(truncate)")
    before = game.world.path.read_bytes()
    server = LiveServer(game.world.path)
    url = server.start()
    try:
        for tool in ("sheet", "known_people", "rumours", "factions", "place"):
            ask(url, tool)
    finally:
        server.stop()
    assert game.world.path.read_bytes() == before


def make_app(tmp_path, mode):
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=FakeClaude(*[{"prose": "Mist hangs over the reeds."}] * 5))
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    return app


def test_the_server_runs_while_the_ai_is_on(tmp_path):
    app = make_app(tmp_path, "assist")
    assert app.mcp is not None and app.mcp.running
    url = app.mcp.url
    app.handle_key("f1", "")
    app.handle_key("5", "5")  # the Connect page
    assert any(url in text for text, _ in app.ai_menu.lines())
    app.handle_key("1", "1")  # back
    app.handle_key("1", "1")  # assist -> ai_only: still on
    assert app.mcp is not None
    app.handle_key("1", "1")  # ai_only -> off
    assert app.mcp is None
    app.shutdown()


def test_the_server_stops_with_the_game_and_is_not_started_while_off(tmp_path):
    app = make_app(tmp_path, "off")
    assert app.mcp is None
    app.shutdown()
    app = make_app(tmp_path / "again", "assist")
    server = app.mcp
    app.shutdown()
    assert app.mcp is None and not server.running


def test_a_backend_built_while_the_server_runs_is_given_its_address(tmp_path):
    app = make_app(tmp_path, "assist")
    door = app._backend()  # what the menu builds after a change of backend or model
    assert app.mcp is not None and door.mcp_url == app.mcp.url
    app.shutdown()
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_server.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'mcp_server.live'`.

- [ ] **Step 3: Write the new modules**

`mcp_server/live.py`:
```python
"""The long-lived DeepMurim MCP server (phase 6 spec 13.4): one, over streamable HTTP on localhost, while the AI is on.

Both backends connect to it (and the player's own Claude Code or OpenCode sessions may: the Connect page says how).
It runs in a thread of the game itself, reading the save read-only and anew on every request.
"""

import logging
import socket
import threading
import time
from pathlib import Path

STARTUP = 10.0
for _noisy in ("mcp", "httpx", "httpx2", "uvicorn", "uvicorn.error", "uvicorn.access"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)  # every request would be told on the console


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LiveServer:
    def __init__(self, save: Path) -> None:
        self.save = Path(save)
        self.url: str | None = None
        self._server = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> str:
        """Start it (once) and return its address: http://127.0.0.1:<port>/mcp."""
        if self.running:
            return self.url
        import uvicorn
        from mcp_server.server import build
        port = free_port()
        app = build(self.save, fresh=True).streamable_http_app(host="127.0.0.1")
        self._server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                                     lifespan="on"))
        self._thread = threading.Thread(target=self._server.run, name="deepmurim-mcp", daemon=True)
        self._thread.start()
        deadline = time.monotonic() + STARTUP
        while not self._server.started:
            if time.monotonic() > deadline or not self._thread.is_alive():
                self.stop()
                raise RuntimeError("the MCP server did not start")
            time.sleep(0.05)
        self.url = f"http://127.0.0.1:{port}/mcp"
        return self.url

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(5)
        self._server, self._thread, self.url = None, None, None
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6b_task3.py`:
```python
"""Phase 6b, Task 3: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('app.py', r'''from ai.menu import AiMenu, make_backend
from ai.narrate import MODE_WORDS, Narration
''', r'''from ai.menu import AiMenu, make_backend
from mcp_server.live import LiveServer
from ai.narrate import MODE_WORDS, Narration
''')
edit('app.py', r'''        self.ai_menu: AiMenu | None = None  # phase 6b: F1

''', r'''        self.ai_menu: AiMenu | None = None  # phase 6b: F1
        self.mcp: LiveServer | None = None  # phase 6b: the long-lived MCP server, while the AI is on

''')
edit('app.py', r'''        elif key == "f1":
            self.ai_menu = AiMenu(self.config)
        elif key == "f2":
''', r'''        elif key == "f1":
            self.ai_menu = AiMenu(self.config, mcp_url=lambda: self.mcp.url if self.mcp else None)
        elif key == "f2":
''')
edit('app.py', r'''        """The backend the settings name (phase 6b): Claude Code or OpenCode, with the chosen models."""
        return make_backend(self.config, self.logs_dir / "opencode")

''', r'''        """The backend the settings name (phase 6b): Claude Code or OpenCode, with the chosen models."""
        door = make_backend(self.config, self.logs_dir / "opencode")
        door.mcp_url = self.mcp.url if self.mcp is not None else None
        return door

    def _ai_server(self) -> None:
        """The MCP server runs while the AI is on and a game is open (spec 13.4)."""
        wanted = self.game is not None and self.config.ai_mode != "off"
        if wanted and self.mcp is None:
            self.mcp = LiveServer(self.game.world.path)
            try:
                self.mcp.start()
            except Exception as exc:  # the models answer without the tools: their prose needs none
                self._record("ai_error", error=f"the MCP server did not start ({exc!r})")
                self.mcp = None
            door = self.narration._bridge
            if door is not None and hasattr(door, "mcp_url"):
                door.mcp_url = self.mcp.url if self.mcp else None
        elif not wanted and self.mcp is not None:
            self.mcp.stop()
            self.mcp = None

''')
edit('app.py', r'''        self.config.ai_mode = mode
        self._save_settings()

    def poll(self) -> None:
''', r'''        self.config.ai_mode = mode
        self._save_settings()
        self._ai_server()

    def poll(self) -> None:
''')
edit('app.py', r'''            return
        why = self.narration.unavailable()
''', r'''            return
        self._ai_server()
        why = self.narration.unavailable()
''')
edit('app.py', r'''            self.log.append((f"Claude's prose cannot be used: {why}.", "system"))
            self._save_settings()

    def _close_game(self) -> None:
''', r'''            self.log.append((f"Claude's prose cannot be used: {why}.", "system"))
            self._save_settings()
            self._ai_server()

    def _close_game(self) -> None:
''')
edit('app.py', r'''        self.narration.reset()
        if self.game is not None:
''', r'''        self.narration.reset()
        if self.mcp is not None:
            self.mcp.stop()
            self.mcp = None
        if self.game is not None:
''')
edit('mcp_server/server.py', r'''
def build(save) -> MCPServer:
    view = T.View(World.open_readonly(save))
    server = MCPServer("deepmurim", instructions=INSTRUCTIONS)
''', r'''
def build(save, fresh: bool = False) -> MCPServer:
    """The server over one save. `fresh`: every request opens the save anew (phase 6b's long-lived server, while
    the game writes); else one view for a single `claude -p` call."""
    held = None if fresh else T.View(World.open_readonly(save))

    def ask(tool, *args):
        if held is not None:
            return tool(held, *args)
        world = World.open_readonly(save)
        try:
            return tool(T.View(world), *args)
        finally:
            world.close()

    server = MCPServer("deepmurim", instructions=INSTRUCTIONS)
''')
edit('mcp_server/server.py', r'''    def sheet() -> str:
        return T.sheet(view)

''', r'''    def sheet() -> str:
        return ask(T.sheet)

''')
edit('mcp_server/server.py', r'''    def known_people() -> str:
        return T.known_people(view)

''', r'''    def known_people() -> str:
        return ask(T.known_people)

''')
edit('mcp_server/server.py', r'''    def person(name: str) -> str:
        return T.person(view, name)

''', r'''    def person(name: str) -> str:
        return ask(T.person, name)

''')
edit('mcp_server/server.py', r'''    def memories_of(name: str) -> str:
        return T.memories_of(view, name)

''', r'''    def memories_of(name: str) -> str:
        return ask(T.memories_of, name)

''')
edit('mcp_server/server.py', r'''    def beliefs_of(name: str, topic: str = "") -> str:
        return T.beliefs_of(view, name, topic)

''', r'''    def beliefs_of(name: str, topic: str = "") -> str:
        return ask(T.beliefs_of, name, topic)

''')
edit('mcp_server/server.py', r'''    def rumours(topic: str = "") -> str:
        return T.rumours(view, topic)

''', r'''    def rumours(topic: str = "") -> str:
        return ask(T.rumours, topic)

''')
edit('mcp_server/server.py', r'''    def chronicle(query: str = "", limit: int = 10) -> str:
        return T.chronicle(view, query, limit)

''', r'''    def chronicle(query: str = "", limit: int = 10) -> str:
        return ask(T.chronicle, query, limit)

''')
edit('mcp_server/server.py', r'''    def factions() -> str:
        return T.factions(view)

''', r'''    def factions() -> str:
        return ask(T.factions)

''')
edit('mcp_server/server.py', r'''    def place() -> str:
        return T.place(view)

''', r'''    def place() -> str:
        return ask(T.place)

''')
print("task 3 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6b_task3.py`
Expected: `task 3 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_server.py tests/test_mcp_server.py`
Expected: `14 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow and live ones are deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: one long-lived MCP server while the AI is on, and the Connect page that tells how to reach it

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: Prefetch, and a paragraph of prose

`build_prefetch` makes the lookups a model would ask for (the people here; what those named or in play are and remember of the player; what anyone here holds touching the words typed, with the `tell` handles), under 20 ms and with no ids, for 6c's jobs (ruling 8). Narration asks for one paragraph of about 3-6 sentences (spec 13.6); the prose schema allows 1,500 characters.

**Files:**
- Create: `ai/prefetch.py`
- Create: `tests/test_ai_prefetch.py`
- Modify (by `.patches/6b_task4.py`): `ai/narrate.py`, `tests/test_ai_live.py`

**Interfaces:**
- Consumes: 6a's `mcp_server.tools` (`View`, `person`, `memories_of`, `beliefs_of`) and `ai.narrate`.
- Produces:
  - `ai.prefetch`: `MAX_BELIEFS`, `words_of(text)`, `build_prefetch(game, typed, focus=None) -> str`.
  - `ai.narrate.SYSTEM` (a paragraph), `PROSE_SCHEMA` (1,500).

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_prefetch.py`:
```python
import gc
import re
import time

import pytest

import systems.encounters as encounters
from ai.narrate import PROSE_SCHEMA, SYSTEM
from ai.prefetch import build_prefetch, words_of
from engine.actions import Action
from engine.game import Game
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.gen.materialize import people_at


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def a_tale(game, holder, about="bandits"):
    world = game.world
    far = world.add_entity("person", "Gu Bandit", {"occupation": "bandit", "traits": ["cunning"], "realm": "mortal",
                                                   "portrait": {"hair": 0, "face": 0, "robe": 0}}, f"test:pre:{about}")
    variant = make_variant("robbed", far, None, place="the marsh road")
    fact = record_fact(world, far, "robbed", None, place=None, variant=variant, spread=False)
    believe(world, holder, fact, variant, None, 0.9, 1, "test")
    return fact


def test_the_people_here_are_always_told(game):
    text = build_prefetch(game, "I look around.")
    for person in people_at(game.world, game.place.id, exclude=game.player.id)[:15]:
        assert f"- {person.name}, {person.data['occupation']}" in text


def test_someone_named_brings_what_they_are_and_remember(game):
    here = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    game.perform(Action("talk", here.id))
    text = build_prefetch(game, f"I ask {here.name} about the road.")
    assert f"{here.name.upper()} AS YOU KNOW THEM:" in text and f"WHAT {here.name.upper()} REMEMBERS OF YOU:" in text
    assert "Met " in text


def test_beliefs_touching_the_words_come_with_their_handles(game):
    here = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    a_tale(game, here.id)
    text = build_prefetch(game, f"{here.name}, have you heard of anyone robbed on the roads?")
    assert "WHAT THOSE HERE HOLD ON YOUR WORDS" in text and re.search(r"\[b[0-9a-f]{10}\].*Gu Bandit robbed", text)
    assert "WHAT THOSE HERE HOLD" not in build_prefetch(game, f"{here.name}, what fine weather.")


def test_the_prefetch_carries_no_ids_and_is_quick(game):
    here = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    a_tale(game, here.id)
    typed = f"I ask {here.name} about anyone robbed."
    assert not re.search(r"#\d", build_prefetch(game, typed))
    gc.collect()
    start = time.perf_counter()
    for _ in range(10):
        build_prefetch(game, typed)
    assert (time.perf_counter() - start) / 10 < 0.02


def test_words_are_the_telling_ones():
    assert words_of("Tell me about the robbed merchant, would you?") == {"robbed", "merchant"}


def test_prose_is_asked_as_a_paragraph():
    assert "one paragraph of about 3-6" in SYSTEM and PROSE_SCHEMA["properties"]["prose"]["maxLength"] == 1500
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_prefetch.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'ai.prefetch'`.

- [ ] **Step 3: Write the new modules**

`ai/prefetch.py`:
```python
"""The lookups a model would likely ask for, done before it is asked (phase 6 spec 13.5).

A tool round trip costs the model seconds; the lookup itself costs the engine milliseconds. So for a typed action
or a line of talk (6c), the people here, what the ones in play remember of the player, and what anyone here holds
that touches the words typed go into the prompt; the tools remain for anything else.
"""

import re

from mcp_server import tools as T
from world.gen.materialize import people_at

MAX_BELIEFS = 6
WORD = re.compile(r"[a-z']{4,}")
COMMON = frozenset({"that", "this", "with", "what", "about", "your", "have", "from", "they", "them", "there", "their",
                    "would", "could", "should", "into", "where", "when", "which", "some", "will", "just", "tell"})


def words_of(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if w not in COMMON}


def build_prefetch(game, typed: str, focus: int | None = None) -> str:
    """What the engine already knows the model will want: a text block for the prompt, ids never shown."""
    view = T.View(game.world)
    here = people_at(game.world, game.place.id, exclude=game.player.id)
    wanted = words_of(typed)
    named = [p for p in here if p.id == focus or p.name.lower() in typed.lower()]
    lines = ["PEOPLE HERE:"] + [f"- {p.name}, {p.data.get('occupation', 'stranger')}" for p in here[:15]]
    for person in named[:3]:
        lines += [f"{person.name.upper()} AS YOU KNOW THEM:", "- " + T.person(view, person.name).replace("\n", "\n- "),
                  f"WHAT {person.name.upper()} REMEMBERS OF YOU:",
                  "- " + T.memories_of(view, person.name).replace("\n", "\n- ")]
    held = []
    for person in (named or here)[:6]:
        for line in T.beliefs_of(view, person.name, "").splitlines():
            if line.startswith("[") and wanted & words_of(line):
                held.append(f"- {person.name} holds: {line}")
    if held:
        lines += ["WHAT THOSE HERE HOLD ON YOUR WORDS (the [handle] tells it):"] + held[:MAX_BELIEFS]
    return "\n".join(lines)
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6b_task4.py`:
```python
"""Phase 6b, Task 4: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('ai/narrate.py', r'''RECENT = 3
PROSE_SCHEMA = {"type": "object", "properties": {"prose": {"type": "string", "maxLength": 900}},
                "required": ["prose"], "additionalProperties": False}
''', r'''RECENT = 3
PROSE_SCHEMA = {"type": "object", "properties": {"prose": {"type": "string", "maxLength": 1500}},
                "required": ["prose"], "additionalProperties": False}
''')
edit('ai/narrate.py', r'''SYSTEM = (
    "You are the narrator of DeepMurim, a wuxia text game. Rewrite the turn below as 1-4 sentences of vivid "
    "second-person prose in the register of a wuxia novel. Use only what the EVENT blocks and the STATE say: add no "
    "person, item, place, number or outcome they do not carry, and never contradict an OUTCOME line. Keep names "
    "exactly as given, and keep every number an OUTCOME line states, written as digits. Do not address the "
''', r'''SYSTEM = (
    "You are the narrator of DeepMurim, a wuxia text game. Rewrite the turn below as one paragraph of about 3-6 "
    "sentences of vivid second-person prose in the register of a wuxia novel. Use only what the EVENT blocks and "
    "the STATE say: add no person, item, place, number or outcome they do not carry, and never contradict an "
    "OUTCOME line. Keep names "
    "exactly as given, and keep every number an OUTCOME line states, written as digits. Do not address the "
''')
edit('tests/test_ai_live.py', r'''    reply = bridge.call(narrate_job(), "STATE:\n- a misty marsh town at dawn\n\nTHIS TURN:\nEVENT: look\nOUTCOME:\n- You look around.")
    assert reply is not None and 0 < len(reply["prose"]) <= 900, list(bridge.exchanges)[-1].error
''', r'''    reply = bridge.call(narrate_job(), "STATE:\n- a misty marsh town at dawn\n\nTHIS TURN:\nEVENT: look\nOUTCOME:\n- You look around.")
    assert reply is not None and 0 < len(reply["prose"]) <= 1500, list(bridge.exchanges)[-1].error
''')
print("task 4 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6b_task4.py`
Expected: `task 4 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_prefetch.py tests/test_ai_narration.py`
Expected: `17 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow and live ones are deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: prefetch for 6c's talk, and prose a paragraph long

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: Help, the fork guide, and live round trips

Help names "F1 the AI"; the fork guide's section 17 tells how the backends, the menu and the server fit; the live tests (marked `live`, `DEEPMURIM_LIVE=1`) add one Agent SDK round trip and one OpenCode round trip on a free model (ruling 9).

**Files:**
- Create: `tests/test_ai_guide.py`
- Modify (by `.patches/6b_task5.py`): `docs/world-events.md`, `engine/game.py`, `tests/test_ai_debug.py`, `tests/test_ai_live.py`

**Interfaces:**
- Consumes: Everything above.
- Produces:
  - `docs/world-events.md` section 17; `tests/test_ai_live.py`'s two new live tests.

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_guide.py`:
```python
"""Phase 6b's help and fork guide: F1 opens the AI menu; section 17 tells how the backends and the server fit."""
from pathlib import Path

from ai.fake import FakeClaude
from app import App
from config import Config
from systems.creation import CreationChoice


def test_help_names_f1_the_ai(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=FakeClaude())
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    app.submit("help")
    assert any("F1 the AI" in t for t, _ in app.log)
    app.shutdown()


def test_the_fork_guide_covers_two_backends_the_menu_and_the_server():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    assert "## 17. Two backends, the AI menu, one MCP server (phase 6b)" in guide
    for word in ("ai/backends.py", "ClaudeCode", "OpenCode", "_ask(job, prompt)", "ai/menu.py", "ai/models.py",
                 "free models", "LiveServer", "fresh=True", "ai/prefetch.py"):
        assert word in guide, word
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_guide.py`
Expected: `2 failed`: help still says "F1 Claude's prose", and the guide has no section 17.

- [ ] **Step 3: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6b_task5.py`:
```python
"""Phase 6b, Task 5: its edits to files that exist before it."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline=chr(10))


edit('docs/world-events.md', r'''**Tests that call the real CLI** are marked `live` and also need `DEEPMURIM_LIVE=1`; no ordinary run makes one.
''', r'''**Tests that call the real CLI** are marked `live` and also need `DEEPMURIM_LIVE=1`; no ordinary run makes one.

## 17. Two backends, the AI menu, one MCP server (phase 6b)

**Backends** (`ai/backends.py`): every job goes through `call(job, prompt) -> dict | None`, with 6a's rules (any
failure is None; three in a row pause it). `ClaudeCode` runs Claude Code through the Agent SDK on the player's own
login (their plan), one client per job kept open, each call a fresh session, `ANTHROPIC_API_KEY` taken out of its
environment. `OpenCode` keeps a hidden `opencode serve` warm and attaches each `opencode run` to it, with
OpenCode's own agent (its free models answer no other), calling `opencode.exe` directly, never the `.cmd` shim; the
job's JSON shape rides in the message, and the last text part is parsed. A new backend subclasses `Backend` and
implements `_ask(job, prompt) -> (reply, error)`.

**The AI menu** (`ai/menu.py`, F1): the mode, the backend, a model for prose and one for typed actions and talk
(6c). OpenCode lists only its free models (`ai/models.py` reads `opencode models --verbose` and keeps those of cost
0). The Connect page tells whether each backend is installed, warns of `ANTHROPIC_API_KEY`, and gives the
copy-paste setup for reaching DeepMurim's MCP server from one's own Claude Code or OpenCode.

**The MCP server** (`mcp_server/live.py`, `LiveServer`): one, over streamable HTTP on localhost, while the AI is on;
`build(save, fresh=True)` opens the save anew on every request (the game writes meanwhile).

**Prefetch** (`ai/prefetch.py`): for 6c's typed actions and talk, the people here, what those in play remember, and
what anyone here holds touching the words typed (with the `tell` handles), put in the prompt so the model rarely
needs a tool.

''')
edit('engine/game.py', r'''    ("  temple | alms | incense | fortune: karma, and heaven's patience", "system"),
    ("  F1 Claude's prose | F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu",
     "system"),
''', r'''    ("  temple | alms | incense | fortune: karma, and heaven's patience", "system"),
    ("  F1 the AI | F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu",
     "system"),
''')
edit('tests/test_ai_debug.py', r'''    app.submit("help")
    assert any("F1 Claude's prose" in t for t, _ in app.log)
    app.shutdown()
''', r'''    app.submit("help")
    assert any("F1 the AI" in t for t, _ in app.log)
    app.shutdown()
''')
edit('tests/test_ai_live.py', r'''import os

''', r'''import os
from pathlib import Path

''')
edit('tests/test_ai_live.py', r'''    assert reply is not None and 0 < len(reply["prose"]) <= 1500, list(bridge.exchanges)[-1].error
''', r'''    assert reply is not None and 0 < len(reply["prose"]) <= 1500, list(bridge.exchanges)[-1].error


PROMPT = "STATE:\n- a misty marsh town at dawn\n\nTHIS TURN:\nEVENT: look\nOUTCOME:\n- You look around."


def test_claude_code_writes_a_paragraph_through_the_agent_sdk():
    from ai.backends import ClaudeCode
    door = ClaudeCode()
    if not door.available()[0]:
        pytest.skip(door.available()[1])
    try:
        reply = door.call(narrate_job(), PROMPT)
    finally:
        door.close()
    assert reply is not None and 0 < len(reply["prose"]) <= 1500, list(door.exchanges)[-1].error


def test_opencode_writes_a_paragraph_with_a_free_model():
    from ai.backends import OpenCode, opencode_exe
    from ai.models import OpenCodeModels
    exe = opencode_exe()
    if exe is None:
        pytest.skip("OpenCode is not installed")
    free = OpenCodeModels(exe).free()
    if not free:
        pytest.skip("OpenCode offers no free model")
    door = OpenCode(models={"narrate": free[0]}, workdir=Path("logs") / "live-opencode")  # never under Temp
    try:
        reply = door.call(narrate_job(timeout=120.0), PROMPT)
    finally:
        door.close()
    assert reply is not None and 0 < len(reply["prose"]) <= 1500, list(door.exchanges)[-1].error
''')
print("task 5 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6b_task5.py`
Expected: `task 5 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_guide.py tests/test_ai_debug.py tests/test_ai_live.py`
Expected: `7 passed, 3 deselected`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow and live ones are deselected).

- [ ] **Step 7: Run the soak**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: `2 passed`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: help, the fork guide's section 17, and live round trips through both backends

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Self-review

- **Spec coverage (section 13):**
  - 13.1 the two backends (Task 1);
  - 13.2 the AI menu and the free models (Task 2);
  - 13.3 the Connect page (Tasks 2, 3);
  - 13.4 the long-lived MCP server (Task 3);
  - 13.5 prefetch and 13.6 a paragraph of prose (Task 4);
  - 13.7 testing (every task; live round trips in Task 5).
- **Dry run:**
  - every task was applied in order to a copy of master; its tests failed as each Step 2 says, then passed;
  - the whole suite passed after every task, and the soak at the end;
  - the live round trips passed through `claude -p`, the Agent SDK, and OpenCode on a free model.
