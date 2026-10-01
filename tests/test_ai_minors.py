"""Phase 6a's deferred minors, each pinned by a test that failed first."""
import subprocess
import sys
import time

import pytest

import systems.encounters as encounters

from ai.fake import FakeClaude
from ai.guard import refusal
from ai.narrate import SYSTEM, WAITING
from app import App
from config import Config
from engine.game import Game
from mcp_server import tools as T
from systems.creation import CreationChoice
from world.db import World

MIST = {"prose": "Mist hangs over the reeds, and the town wakes slowly around you."}


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def make_app(tmp_path, *replies, mode="assist", available=True):
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=FakeClaude(*replies, available=available))
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


def test_a_name_claude_made_up_is_refused(tmp_path):
    g = Game.new(tmp_path / "g.world", "Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    me, here = g.player.id, g.place.id
    given = f"WHERE: {g.place.name}; Mo Rin"
    assert refusal(g.world, "Old Li Wei the ferryman waves.", me, here, given) == \
        "it names Li Wei, which the turn did not"
    assert refusal(g.world, f"The mist lies over {g.place.name}. You wait.", me, here, given) is None
    g.close()


def test_claude_is_asked_for_digits():
    assert "as digits" in SYSTEM


def test_a_new_game_forgets_the_last_ones_prose(tmp_path):
    app = make_app(tmp_path, MIST, MIST)
    wait(app)
    assert app.narration.recent and app.narration.cache
    app.start_new("Ka Lun", world_seed=12, creation=CreationChoice("origin", "hunter"))
    assert app.narration.recent == [] and "Mist hangs" not in app.narration.pending.prompt


def test_turning_claude_off_takes_back_the_waiting_turn(tmp_path):
    slow = lambda job, prompt: (time.sleep(0.3), MIST)[1]  # noqa: E731
    app = make_app(tmp_path, slow, mode="ai_only")
    turn = app.last_turn
    assert WAITING in app.log
    cycle_mode(app)  # ai_only -> off
    assert app.narration.mode == "off" and WAITING not in app.log
    assert all(turn.lines[i] in app.log for i in turn.narrated)
    time.sleep(0.4)
    app.poll()
    assert (MIST["prose"], "prose") not in app.log


def test_the_worker_never_holds_the_game_open(tmp_path):
    slow = lambda job, prompt: (time.sleep(0.3), MIST)[1]  # noqa: E731
    app = make_app(tmp_path, slow)
    assert app.narration.worker is not None and app.narration.worker.daemon
    app.shutdown()


def test_a_timeout_kills_the_whole_tree():
    from ai.bridge import run_command
    child = ("import subprocess, sys, time; "
             "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
             "print(p.pid, flush=True); time.sleep(30)")
    start = time.perf_counter()
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        run_command([sys.executable, "-c", child], input="", capture_output=True, text=True, timeout=2)
    assert time.perf_counter() - start < 10
    pid = int((caught.value.stdout or "0").split()[0])
    alive = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
    assert str(pid) not in alive  # the grandchild went with it (an npm claude.cmd's node)


def test_reading_a_closed_save_leaves_nothing_beside_it(tmp_path):
    g = Game.new(tmp_path / "c.world", "Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.close()
    for side in ("-wal", "-shm"):
        (tmp_path / f"c.world{side}").unlink(missing_ok=True)
    world = World.open_readonly(tmp_path / "c.world")
    assert world.get_meta("player_id")
    world.close()
    assert not (tmp_path / "c.world-wal").exists() and not (tmp_path / "c.world-shm").exists()


def test_a_dead_players_save_is_told_not_known(tmp_path):
    g = Game.new(tmp_path / "d.world", "Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    me = g.player.id
    g.world.unrelate(me, "located_in")
    g.world.update_data(me, dead=True)
    g.world._conn.execute("pragma wal_checkpoint(truncate)")
    view = T.View(World.open_readonly(g.world.path))
    for tool in (T.known_people, T.place, T.factions):
        assert isinstance(tool(view), str)
    g.close()


def test_a_saved_mode_claude_cannot_serve_is_told_at_the_start(tmp_path):
    app = make_app(tmp_path, mode="assist", available=False)
    assert app.narration.mode == "off" and app.config.ai_mode == "off"
    assert any("Claude's prose cannot be used" in text for text, _ in app.log)
    app.shutdown()


def cycle_mode(app):
    """F1 opens the AI menu (phase 6b); its first line cycles the mode; Esc closes it."""
    app.handle_key("f1", "")
    app.handle_key("1", "1")
    app.handle_key("escape", "\x1b")
