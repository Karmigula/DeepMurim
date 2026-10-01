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
