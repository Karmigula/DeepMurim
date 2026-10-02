"""The two doors to a model (phase 6 spec 13.1): Claude Code through the Claude Agent SDK, and OpenCode.

Both answer `call(job, prompt) -> dict | None` with 6a's rules: any failure returns None (the caller keeps the
engine's words), every exchange is remembered, three failures in a row pause the door for five minutes.

- `ClaudeCode` runs Claude Code on the user's own login (their Pro/Max plan) through the Agent SDK, one client per
  job kept open for the game, each call a fresh session (no history grows). `ANTHROPIC_API_KEY` is set empty in
  its environment (the SDK merges the game's own under it, so leaving it out is not enough); a key would switch
  Claude Code to API billing.
- `OpenCode` keeps a hidden `opencode serve` warm and attaches each `opencode run` to it, with OpenCode's own agent
  (its free models answer no other). `opencode.exe` is run directly, never the npm `.cmd` shim.
"""

import asyncio
import contextlib
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
from ai.models import NO_WINDOW, OPENCODE_DEFAULT

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
        self.closed = False  # a closed door takes no more work (6b review): nothing it starts would be stopped
        self._lock = threading.Lock()

    def available(self) -> tuple[bool, str]:
        if self._checked is None:
            self._checked = self._check()
        return self._checked

    def _check(self) -> tuple[bool, str]:
        return True, ""

    def paused(self) -> bool:
        return self.clock() < self.paused_until

    def call(self, job: Job, prompt: str) -> dict | None:
        if self.closed or self.paused() or not self.available()[0]:
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

    def cancel(self, job_name: str) -> None:
        """Let an exchange still running for this job go (Esc): the next never waits behind it."""

    def close(self) -> None:
        self.closed = True


def bundled_cli() -> Path:
    """Where the Agent SDK keeps a Claude Code of its own, when its wheel carries one."""
    import claude_agent_sdk
    return Path(claude_agent_sdk.__file__).parent / "_bundled" / ("claude.exe" if os.name == "nt" else "claude")


def claude_cli() -> str | None:
    """The Claude Code the Agent SDK would run, found where it looks: its own, on PATH, or the native installer's."""
    for found in (bundled_cli(), shutil.which("claude"), Path.home() / ".local" / "bin" / "claude.exe"):
        if found and Path(found).is_file():
            return str(found)
    return None


# --- Claude Code, through the Agent SDK -------------------------------------------------------------------------

class ClaudeCode(Backend):
    name = "Claude Code"

    def __init__(self, models: dict | None = None, client_factory=None, clock=time.monotonic) -> None:
        super().__init__(clock)
        self.models = dict(models or {})  # job name -> model; else the job's own
        self._factory = client_factory  # tests hand in a fake; the real one is the SDK's ClaudeSDKClient
        self._clients: dict[str, object] = {}
        self._locks: dict[str, asyncio.Lock] = {}  # one exchange at a time per client: its stream is shared
        self._running: dict = {}  # each exchange in flight -> its job's name (cancel)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._calls = 0

    def _check(self) -> tuple[bool, str]:
        if self._factory is None and claude_cli() is None:  # the SDK runs the user's Claude Code
            return False, "Claude Code is not installed"
        return True, ""

    def options(self, job: Job):
        from claude_agent_sdk import ClaudeAgentOptions, ThinkingConfigDisabled
        env = {"ANTHROPIC_API_KEY": ""}  # overrides the inherited one: the user's plan, never the API's
        mcp = {"deepmurim": {"type": "http", "url": self.mcp_url}} if job.tools and self.mcp_url else {}
        return ClaudeAgentOptions(
            model=self.models.get(job.name, job.model), system_prompt=job.system, tools=[],
            allowed_tools=["mcp__deepmurim__*"] if mcp else [], mcp_servers=mcp, strict_mcp_config=True,
            setting_sources=[], effort="low", max_turns=8 if mcp else 3, env=env,
            thinking=None if job.thinking else ThinkingConfigDisabled(type="disabled"),
            output_format={"type": "json_schema", "schema": job.schema})

    def _run(self, coro, timeout: float, name: str = ""):
        with self._lock:
            if self.closed:
                coro.close()
                raise RuntimeError("closed")
            if self._loop is None:
                self._loop = loop = asyncio.new_event_loop()

                def run() -> None:
                    loop.run_forever()
                    loop.close()
                threading.Thread(target=run, name="claude-code", daemon=True).start()
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            self._running[future] = name
        try:
            return future.result(timeout)
        except BaseException:
            future.cancel()  # the exchange lets its client go (below)
            raise
        finally:
            self._running.pop(future, None)

    def cancel(self, job_name: str) -> None:
        for future, name in list(self._running.items()):
            if name == job_name:
                future.cancel()  # its exchange drops the client a late reply would reach (6c minors)

    async def _client(self, key: str, job: Job):
        if key not in self._clients:
            if self._factory is None:
                from claude_agent_sdk import ClaudeSDKClient
                self._factory = ClaudeSDKClient
            client = self._factory(self.options(job))
            await client.connect()
            self._clients[key] = client
        return self._clients[key]

    async def _exchange(self, job: Job, prompt: str) -> tuple[dict | None, str]:
        key = f"{job.name}:{self.models.get(job.name, job.model)}"
        async with self._locks.setdefault(key, asyncio.Lock()):
            client = await self._client(key, job)
            try:
                if self.closed:
                    raise RuntimeError("closed")
                return await asyncio.wait_for(self._talk(client, prompt), job.timeout)
            except BaseException:
                # A reply still on its way would be the next call's first message: the client goes with it.
                self._clients.pop(key, None)
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(client.disconnect(), 5)
                raise

    async def _talk(self, client, prompt: str) -> tuple[dict | None, str]:
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
            # Room to wait behind another exchange on the same client (its own timeout bounds it).
            return self._run(self._exchange(job, prompt), 2 * job.timeout + 10, job.name)
        except (TimeoutError, asyncio.TimeoutError):
            return None, f"no reply within {job.timeout:.0f} s"

    async def _shutdown(self) -> None:
        clients, self._clients = list(self._clients.values()), {}
        for client in clients:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(client.disconnect(), 5)

    def close(self) -> None:
        with self._lock:
            self.closed = True
            loop, self._loop = self._loop, None
        if loop is None:
            return
        with contextlib.suppress(Exception):
            asyncio.run_coroutine_threadsafe(self._shutdown(), loop).result(10)
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
                 workdir: Path | None = None, clock=time.monotonic, free_models=None) -> None:
        super().__init__(clock)
        self.models = dict(models or {})
        self.free_models = free_models  # () -> OpenCode's free models: no other is ever run (6b review)
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
        model = self.models.get(job.name) or OPENCODE_DEFAULT
        if model != OPENCODE_DEFAULT and (self.free_models is None or model not in self.free_models()):
            return OPENCODE_DEFAULT
        return model

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
        with self._lock:  # a close meanwhile would never see a server started after it
            if self.closed:
                raise RuntimeError("closed")
            self.server = server = self.popen(
                [self.exe, "serve", "--port", str(port), "--hostname", "127.0.0.1"],
                cwd=str(self.workdir) if self.workdir else None, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        self.url = f"http://127.0.0.1:{port}"
        deadline = self.clock() + self.STARTUP
        while self.clock() < deadline and self.server is server and server.poll() is None:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    return self.url
            except OSError:
                time.sleep(0.2)
        with self._lock:  # one that never listened is not kept for the next call (6b minors)
            if self.server is server:
                self.server = None
        _kill(server)
        raise TimeoutError("opencode serve did not start")

    def prompt(self, job: Job, prompt: str) -> str:
        """OpenCode has no schema flag: the job's instructions and its JSON shape go in the message."""
        tools = "" if job.tools else "Use no tools. "  # the warm server's config offers them to every call
        text = (f"{job.system}\n\n{tools}Reply with only one JSON object fitting this JSON Schema, and nothing "
                f"else:\n{json.dumps(job.schema)}\n\n{prompt}")
        return text

    def _ask(self, job: Job, prompt: str) -> tuple[dict | None, str]:
        text = self.prompt(job, prompt)
        if len(text) > MAX_ARGUMENT:  # cut, it would lose the turn itself: the engine's words stand instead
            return None, f"the prompt is too long for OpenCode's command line ({len(text)} characters)"
        url = self.warm()
        cmd = [self.exe, "run", "--attach", url, "--format", "json", "-m", self.model(job), text]
        try:
            done = self.runner(cmd, capture_output=True, text=True, encoding="utf-8", timeout=job.timeout,
                               creationflags=NO_WINDOW)
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
        with self._lock:
            self.closed = True
            server, self.server = self.server, None
        _kill(server)


def _kill(server) -> None:
    """The warm server and all it started (taskkill /T on Windows)."""
    if server is not None and server.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(server.pid)], capture_output=True)
        else:
            server.kill()
