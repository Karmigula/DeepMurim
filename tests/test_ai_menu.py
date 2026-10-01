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
