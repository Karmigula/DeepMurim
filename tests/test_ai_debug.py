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
