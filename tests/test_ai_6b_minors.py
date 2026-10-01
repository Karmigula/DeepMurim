"""Phase 6b's minors (its final review's M1-M8), each pinned by a test that failed first."""
import subprocess
import time
from types import SimpleNamespace

import pytest

import ai.backends as backends
import ai.menu as menu_module
import systems.encounters as encounters
from ai.backends import MAX_ARGUMENT, ClaudeCode, OpenCode
from ai.bridge import Job
from ai.fake import FakeClaude
from ai.menu import AiMenu
from ai.models import OpenCodeModels
from ai.narrate import Narration
from ai.prefetch import build_prefetch
from app import App
from config import Config
from systems.creation import CreationChoice

PROSE = {"type": "object", "properties": {"prose": {"type": "string"}}, "required": ["prose"],
         "additionalProperties": False}
NARRATE = Job("narrate", "claude-haiku-4-5", 10.0, PROSE, "Write prose.")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def make_app(tmp_path, mode="off", bridge=None):
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=bridge or FakeClaude())
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    return app


# --- M1: a server that never listened is not kept -----------------------------------------------------------------

def test_a_server_that_died_at_start_is_let_go_at_once(tmp_path, monkeypatch):
    class Dead:
        pid = 1

        def poll(self):
            return 1  # exited
    monkeypatch.setattr("socket.create_connection", lambda *a, **kw: (_ for _ in ()).throw(OSError("refused")))
    door = OpenCode(exe="opencode.exe", popen=lambda *a, **kw: Dead(), workdir=tmp_path)
    began = time.perf_counter()
    assert door.call(NARRATE, "p") is None
    assert time.perf_counter() - began < 2.0 and door.server is None
    assert "did not start" in door.exchanges[-1].error


# --- M2: a prompt too long is refused whole, never cut ------------------------------------------------------------

def test_a_prompt_too_long_for_the_command_line_is_refused_not_cut(tmp_path):
    ran = []
    door = OpenCode(exe="opencode.exe", runner=lambda *a, **kw: ran.append(a), popen=lambda *a, **kw: None,
                    workdir=tmp_path)
    door.server, door.url = SimpleNamespace(poll=lambda: None, pid=1), "http://127.0.0.1:1"
    assert door.call(NARRATE, "x" * MAX_ARGUMENT) is None
    assert ran == [] and "too long" in door.exchanges[-1].error


# --- M3: the Connect page looks for the programs once, not every frame --------------------------------------------

def test_the_connect_page_looks_for_the_programs_once(monkeypatch):
    looked = []
    monkeypatch.setattr(menu_module, "opencode_exe", lambda: looked.append(1))
    m = AiMenu(Config(), OpenCodeModels(None), mcp_url=None)
    m.pick(5)
    for _ in range(5):
        m.lines()
    assert len(looked) == 1


# --- M4: the notices name the backend in use ----------------------------------------------------------------------

def test_the_notices_name_the_backend_in_use(tmp_path):
    class Door(FakeClaude):
        name = "OpenCode"
    app = make_app(tmp_path, "assist", bridge=Door(available=False))
    assert any("OpenCode's prose cannot be used" in text for text, _ in app.log)
    app.shutdown()
    paused = Door()
    paused.just_paused = True
    notices = Narration(paused, "assist").poll([], None)
    assert notices and notices[0][0].startswith("OpenCode has failed three times")


# --- M5: a name is a whole word ----------------------------------------------------------------------------------

def test_a_short_name_is_not_found_inside_another_word(tmp_path, monkeypatch):
    from engine.game import Game
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    game.start()
    try:
        li = SimpleNamespace(id=-7, name="Li", data={"occupation": "porter"})
        monkeypatch.setattr("ai.prefetch.people_at", lambda *a, **kw: [li])
        assert "LI AS YOU KNOW THEM" not in build_prefetch(game, "I like this place.")
        assert "LI AS YOU KNOW THEM" in build_prefetch(game, "I ask Li about the road.")
    finally:
        game.close()


# --- M6: F1 over the character sheet shows the menu ---------------------------------------------------------------

def test_f1_over_the_character_sheet_shows_the_menu(tmp_path):
    app = make_app(tmp_path)
    app.handle_key("f4", "")
    assert app.sheet_visible
    app.handle_key("f1", "")
    grid_text = "\n".join("".join(cell[0] if cell else " " for cell in row) for row in app.grid(120, 40))
    assert not app.sheet_visible and "THE AI (F1 closes)" in grid_text
    app.shutdown()


# --- M7: the Agent SDK's own Claude Code counts as installed ------------------------------------------------------

def test_claude_code_bundled_with_the_sdk_counts_as_installed(tmp_path, monkeypatch):
    bundled = tmp_path / "claude.exe"
    bundled.write_text("")
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(backends, "bundled_cli", lambda: bundled)
    assert ClaudeCode().available() == (True, "")
    monkeypatch.setattr(backends, "bundled_cli", lambda: tmp_path / "missing.exe")
    monkeypatch.setattr(backends.Path, "home", lambda: tmp_path)
    assert ClaudeCode().available() == (False, "Claude Code is not installed")


# --- M8: OpenCode's own commands open no window -------------------------------------------------------------------

def test_opencodes_commands_open_no_window(tmp_path, monkeypatch):
    seen = []

    def runner(cmd, **kw):
        seen.append(kw.get("creationflags"))
        return subprocess.CompletedProcess(cmd, 0, "", "")
    OpenCodeModels("opencode.exe", runner).free()
    door = OpenCode(exe="opencode.exe", runner=runner, popen=lambda *a, **kw: None, workdir=tmp_path)
    door.server, door.url = SimpleNamespace(poll=lambda: None, pid=1), "http://127.0.0.1:1"
    door.call(NARRATE, "p")
    assert seen == [NO_WINDOW, NO_WINDOW]
