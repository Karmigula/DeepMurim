"""Phase 6b's final review: the fixes, each pinned by a test that failed first."""
import asyncio
import contextlib
import json
import os
import subprocess
import threading
import time

import anyio
import pytest

import systems.encounters as encounters
from ai.backends import ClaudeCode, OpenCode
from ai.bridge import Job
from ai.fake import FakeClaude
from ai.menu import AiMenu, chosen, connect_lines, make_backend
from ai.models import OPENCODE_DEFAULT, OpenCodeModels
from ai.narrate import Narration
from app import App
from config import Config
from mcp_server.live import LiveServer
from systems.creation import CreationChoice

PROSE = {"type": "object", "properties": {"prose": {"type": "string"}}, "required": ["prose"],
         "additionalProperties": False}
QUICK = Job("narrate", "claude-haiku-4-5", 0.3, PROSE, "Write prose.")
PATIENT = Job("narrate", "claude-haiku-4-5", 3.0, PROSE, "Write prose.")  # the same client, more time
FREE = ["opencode/big-pickle", "opencode/space-bunny-free"]


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


class ResultMessage:
    def __init__(self, prose):
        self.structured_output, self.result, self.is_error, self.errors = {"prose": prose}, "", False, None


class StreamClient:
    """Like the SDK's client: one stream of messages per client; a reply lands in it after the prompt's delay,
    whether or not anyone is still waiting for it."""
    made: list = []

    def __init__(self, options, delays):
        self.options, self.delays, self.queue = options, delays, None
        self.disconnected = False
        StreamClient.made.append(self)

    async def connect(self):
        self.queue = asyncio.Queue()
        await asyncio.sleep(0.05)

    async def disconnect(self):
        self.disconnected = True

    async def query(self, prompt, session_id="default"):
        async def land():
            await asyncio.sleep(self.delays.get(prompt, 0))
            await self.queue.put(ResultMessage(prompt))
        asyncio.ensure_future(land())

    async def receive_response(self):
        yield object()
        yield await self.queue.get()


def streamed(delays):
    StreamClient.made = []
    return ClaudeCode(client_factory=lambda options: StreamClient(options, delays))


# --- C1: the key is overridden, not merely left out ---------------------------------------------------------------

def test_claude_codes_environment_overrides_an_inherited_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    options = ClaudeCode(client_factory=object).options(QUICK)
    merged = {**os.environ, **options.env}  # the SDK merges the inherited environment under options.env
    assert merged["ANTHROPIC_API_KEY"] == ""


# --- C2: a late reply is never the next turn's ---------------------------------------------------------------------

def test_a_reply_that_came_too_late_is_never_the_next_turns():
    door = streamed({"first": 0.6, "second": 0.6})
    assert door.call(PATIENT, "warm") == {"prose": "warm"}  # the client is open: the timeout below is the reply's
    assert door.call(QUICK, "first") is None  # 0.3 s timeout; its reply lands at 0.6 s
    assert door.call(PATIENT, "second") == {"prose": "second"}  # the late 'first' lands before it
    assert StreamClient.made[0].disconnected  # the client the late reply belonged to is let go
    door.close()


def test_two_calls_at_once_share_one_client_and_each_gets_its_own_reply():
    door = streamed({"a": 0.05, "b": 0.05})
    replies = {}
    threads = [threading.Thread(target=lambda p=p: replies.__setitem__(p, door.call(QUICK, p))) for p in "ab"]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    assert replies == {"a": {"prose": "a"}, "b": {"prose": "b"}}
    assert len(StreamClient.made) == 1
    door.close()


# --- I6: closing never blocks the game, and a closed door takes no work ---------------------------------------------

def test_a_closed_claude_code_takes_no_work():
    door = streamed({})
    door.close()
    assert door.call(QUICK, "late") is None and StreamClient.made == []


def test_a_closed_opencode_starts_no_server(tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr("socket.create_connection", lambda *a, **kw: contextlib.nullcontext())
    door = OpenCode(exe="opencode.exe", popen=lambda *a, **kw: started.append(a), workdir=tmp_path,
                    runner=lambda *a, **kw: subprocess.CompletedProcess(a, 0, "", ""))
    door.close()
    assert door.call(QUICK, "p") is None and started == []


def test_changing_the_backend_never_waits_for_the_old_one_to_close():
    closed = threading.Event()

    class Slow(FakeClaude):
        def close(self):
            time.sleep(1.0)
            closed.set()
    n = Narration(Slow(), "assist")
    began = time.perf_counter()
    n.set_backend(None)
    assert time.perf_counter() - began < 0.5
    assert closed.wait(3)


# --- I4: a hand-edited settings file never reaches a model the menu would not offer -------------------------------

def test_only_offered_models_are_chosen():
    config = Config(ai_backend="claude_code", ai_models={"claude_code": {"narrate": "claude-mythos"},
                                                         "opencode": {"narrate": "openrouter/anthropic/claude-x"}})
    assert chosen(config)["narrate"] == "claude-haiku-4-5"
    assert chosen(config, "opencode")["narrate"] == OPENCODE_DEFAULT


def test_opencode_never_runs_a_model_that_is_not_free(tmp_path):
    found = OpenCodeModels(None)
    found._found = list(FREE)
    config = Config(ai_backend="opencode", ai_models={"opencode": {"narrate": "opencode/claude-opus-paid"}})
    door = make_backend(config, tmp_path, found)
    assert door.model(QUICK) == OPENCODE_DEFAULT
    found._found = FREE + ["opencode/claude-opus-paid"]
    assert door.model(QUICK) == "opencode/claude-opus-paid"


# --- I3: OpenCode's models are read once a session, never on the game's thread ------------------------------------

def test_the_menu_never_waits_for_opencodes_model_list():
    def slow(cmd, **kw):
        time.sleep(1.0)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    menu = AiMenu(Config(ai_backend="opencode"), OpenCodeModels("opencode.exe", slow), mcp_url=None)
    began = time.perf_counter()
    menu.pick(3)
    menu.lines()
    assert time.perf_counter() - began < 0.5


def make_app(tmp_path, mode="off", bridge=None):
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=bridge or FakeClaude(*[{"prose": "Mist hangs over the reeds."}] * 5))
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    return app


def test_the_list_of_free_models_is_kept_for_the_session(tmp_path):
    app = make_app(tmp_path)
    app.handle_key("f1", "")
    first = app.ai_menu.opencode
    app.handle_key("escape", "\x1b")
    app.handle_key("f1", "")
    assert app.ai_menu.opencode is first
    app.shutdown()


# --- I2: the menu says why the AI cannot be used ------------------------------------------------------------------

def test_the_menu_and_the_connect_page_say_why_the_ai_cannot_be_used():
    menu = AiMenu(Config(), OpenCodeModels(None), mcp_url=None, why=lambda: "Claude Code is not logged in")
    assert any("Claude Code is not logged in" in t for t, _ in menu.lines())
    assert any("Claude Code is not logged in" in t for t, _ in connect_lines(None, "Claude Code is not logged in"))


def test_switching_to_a_backend_that_cannot_answer_turns_the_ai_off_and_says_why(tmp_path):
    app = make_app(tmp_path, "assist")
    app.narration._factory = lambda: FakeClaude(available=False)  # the backend switched to cannot be used
    app.handle_key("f1", "")
    app.handle_key("2", "2")
    assert app.config.ai_mode == "off" and app.narration.mode == "off"
    assert any("cannot be used" in text for text, _ in app.log[-3:])
    app.shutdown()


# --- I1: off costs nothing ----------------------------------------------------------------------------------------

def test_turning_the_ai_off_closes_the_backend(tmp_path):
    closed = []

    class Door(FakeClaude):
        def close(self):
            closed.append(self)
    door = Door()
    app = make_app(tmp_path, "ai_only", bridge=door)
    app.narration.bridge  # in use
    closed.clear()  # opening the game closed the one before it
    app.handle_key("f1", "")
    app.handle_key("1", "1")  # ai_only -> off
    assert app.config.ai_mode == "off" and app.mcp is None
    deadline = time.monotonic() + 3
    while not closed and time.monotonic() < deadline:
        time.sleep(0.02)
    assert closed == [door] and app.narration._bridge is None
    app.shutdown()


# --- I5: a connected client never holds the game when the server stops --------------------------------------------

def test_the_server_stops_promptly_while_a_client_is_connected(tmp_path):
    from engine.game import Game
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    game.start()
    server = LiveServer(game.world.path)
    url = server.start()
    connected, release = threading.Event(), threading.Event()

    def hold():
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        async def go():
            with contextlib.suppress(Exception):
                async with streamable_http_client(url) as streams:
                    async with ClientSession(streams[0], streams[1]) as client:
                        await client.initialize()
                        connected.set()
                        while not release.is_set():
                            await anyio.sleep(0.05)
        with contextlib.suppress(BaseException):
            anyio.run(go)
    holder = threading.Thread(target=hold, daemon=True)
    holder.start()
    try:
        assert connected.wait(10)
        time.sleep(0.3)  # its standing stream is open
        began = time.perf_counter()
        server.stop()
        assert time.perf_counter() - began < 3.0
    finally:
        release.set()
        game.close()
