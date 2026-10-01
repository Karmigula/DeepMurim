"""Phase 6a final review: each finding pinned by a test that failed first."""
import json
import random
import subprocess
import time

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.masks as masks
import systems.mortality as mortality
from ai.bridge import Bridge, Job
from ai.fake import FakeClaude
from ai.guard import refusal
from ai.narrate import WAITING
from app import App
from config import Config
from engine.actions import Action
from systems import founding
from systems.creation import CreationChoice
from world.gen.materialize import people_at

MIST = {"prose": "Mist hangs over the reeds, and the town wakes slowly around you."}


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def make_app(tmp_path, *replies, mode="assist", bridge=None):
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=bridge or FakeClaude(*replies))
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


def test_dying_with_claude_on_is_no_crash(tmp_path, monkeypatch):
    for k in mortality.KILL_CHANCE:
        monkeypatch.setitem(mortality.KILL_CHANCE, k, 1.0)
    app = make_app(tmp_path, *[{"prose": "Ash drifts."}] * 5, mode="ai_only")
    wait(app)
    g = app.game
    foe = founding.make_person(g.world, "test:review6a:foe", g.place.id, occupation="hunter", age=30,
                               traits=["cunning", "greedy"])
    g.world.add_memory(foe, g.world.chronicle_about(g.player.id, limit=1)[0].id, "hatred", 1.0, True)
    g.last_briefs, g._narrated = [], []
    g._start_duel(foe, "duel")
    ended = duel._end_event(g.world, g.combat, "lost", "broken", random.Random(1), g.combat.harm, 3)
    lines = g._commit([ended]) + g._finish_duel(ended.data)
    assert g.player.data.get("dying")
    app._show(g._turn(lines))
    wait(app)
    assert app.crash_count == 0 and WAITING not in app.log


def test_a_reply_that_breaks_the_worker_leaves_no_waiting_mark(tmp_path):
    def boom(job, prompt):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad byte")
    app = make_app(tmp_path, boom, mode="ai_only")
    wait(app)
    assert WAITING not in app.log and app.crash_count == 0
    turn = app.last_turn
    assert all(turn.lines[i] in app.log for i in turn.narrated)  # the procedural text stands


def test_the_players_own_mask_name_is_no_stranger(tmp_path):
    from engine.game import Game
    g = Game.new(tmp_path / "m.world", "Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    me = g.player.id
    mask = g.world.add_entity("mask", "plain mask", {"persona": None})
    g.world.relate(me, mask, "owns")
    g.perform(Action("wear_mask"))
    persona = g.world.entity(masks.worn_persona(g.world, me)).name
    assert refusal(g.world, f"You are {persona} now.", me, g.place.id, "", "") is None
    g.close()


def test_a_name_inside_a_longer_name_is_not_a_stranger(tmp_path):
    from engine.game import Game
    g = Game.new(tmp_path / "n.world", "Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    here = people_at(g.world, g.place.id, exclude=g.player.id)[0]
    shorter = here.name[:-1]  # "Jin Yunhyu": a name no one here bears, inside one who is here
    g.world.add_entity("person", shorter, {"occupation": "monk", "traits": [], "realm": "mortal",
                                           "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:review6a:short")
    assert refusal(g.world, f"{here.name} nods to you.", g.player.id, g.place.id, "", "") is None
    assert refusal(g.world, f"{shorter} nods to you.", g.player.id, g.place.id, "", "") is not None
    g.close()


def test_the_gone_line_is_the_engines_own(tmp_path):
    app = make_app(tmp_path, MIST, MIST)
    wait(app)
    g = app.game
    other = people_at(g.world, g.place.id, exclude=g.player.id)[0]
    g.focus = other.id
    g.world.update_data(other.id, dead=True)
    turn = g.perform(Action("rest", 1))
    gone = [i for i, line in enumerate(turn.lines) if "gone" in line[0].lower() or other.name in line[0]]
    assert gone and not any(i in turn.narrated for i in gone)
    assert any("rest" in turn.lines[i][0].lower() for i in turn.narrated)
    app.shutdown()


class AuthRunner:
    def __call__(self, cmd, **kw):
        if cmd[1:] == ["--version"]:
            return subprocess.CompletedProcess(cmd, 0, "2.1.286 (Claude Code)", "")
        return subprocess.CompletedProcess(cmd, 1, "", "Invalid API key · Please run /login")


def test_a_logged_out_claude_turns_the_prose_off_and_says_why(tmp_path):
    app = make_app(tmp_path, mode="assist", bridge=Bridge(cli="claude", runner=AuthRunner()))
    wait(app)
    assert app.narration.mode == "off" and app.config.ai_mode == "off"
    assert any("not logged in" in text for text, _ in app.log)
    app.handle_key("f1", "")
    assert app.narration.mode == "off"  # F1 now says why and stays off
    app.shutdown()


def test_the_session_log_keeps_what_claude_was_asked_and_answered(tmp_path):
    app = make_app(tmp_path, MIST)
    wait(app)
    records = [json.loads(line) for line in app.session.path.read_text(encoding="utf-8").splitlines()]
    ai = [r for r in records if r.get("kind") == "ai"][-1]
    assert "STATE:" in ai["prompt"] and ai["reply"] == MIST and ai["shown"] == MIST["prose"]
    assert "seconds" in ai and ai["error"] == ""
    app.shutdown()


@pytest.mark.slow
def test_the_pack_and_the_tools_stay_quick_in_a_world_of_two_centuries(tmp_path):
    """A newcomer in an old world: the pack and every tool within the spec's limits (spec 10; 6a review)."""
    import gc
    import shutil
    from tests import test_soak
    from ai.pack import build_pack
    from engine.game import Game
    from mcp_server import tools as T
    from world.db import World
    try:
        test_soak.history(tmp_path, 200)
    except AssertionError:
        pass  # the soak's own limits are its test's business; this one wants only the old world
    path = tmp_path / "soak.world"
    world = World.open(path)
    me = world.get_meta("player_id")
    if not world.targets(me, "located_in"):
        world.relate(me, world.entities("town")[0].id, "located_in")
    world.update_data(me, dying=None, dead=None, age=30)
    world.close()
    game = Game.load(path)
    game.start()

    def per_call(fn, n=5):
        fn()
        gc.collect()
        start = time.perf_counter()
        for _ in range(n):
            fn()
        return (time.perf_counter() - start) / n
    assert per_call(lambda: build_pack(game)) < 0.015
    game.world._conn.execute("pragma wal_checkpoint(truncate)")
    view = T.View(World.open_readonly(path))
    name = game.world.entity(view.known()[0]).name
    for tool in (lambda: T.sheet(view), lambda: T.known_people(view), lambda: T.person(view, name),
                 lambda: T.memories_of(view, name), lambda: T.beliefs_of(view, name, ""), lambda: T.rumours(view, ""),
                 lambda: T.chronicle(view, "", 10), lambda: T.factions(view), lambda: T.place(view)):
        assert per_call(tool, 3) < 0.03
    game.close()
