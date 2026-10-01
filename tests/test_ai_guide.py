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
