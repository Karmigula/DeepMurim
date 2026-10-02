"""The whole-project ultrareview's findings (2026-10-01), each pinned by a test that failed first."""
import time

import pytest

import debug.invariants as invariants
import systems.encounters as encounters
from ai.fake import FakeClaude
from ai.narrate import CACHE_MAX, Narration
from app import App
from config import Config
from debug.invariants import check_knowledge, check_world
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice
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


def make_app(tmp_path, mode="off", bridge=None):
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=bridge or FakeClaude(*[None] * 20))
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    return app


# --- F11 opens the tournaments, as help says; Alt+Enter is the full screen ------------------------------------------

class Screen:
    def __init__(self):
        self.toggled = 0

    def toggle_fullscreen(self):
        self.toggled += 1


class Keys:
    def __init__(self):
        self.got = []

    def handle_key(self, key, text, repeat=False):
        self.got.append(key)


def test_f11_reaches_the_game_and_alt_enter_toggles_the_full_screen():
    from main import route_key
    screen, app = Screen(), Keys()
    route_key(app, screen, "f11", "", alt=False, repeat=False)
    assert app.got == ["f11"] and screen.toggled == 0
    route_key(app, screen, "return", "\r", alt=True, repeat=False)
    assert app.got == ["f11"] and screen.toggled == 1
    route_key(app, screen, "return", "\r", alt=True, repeat=True)  # a held key toggles once
    assert screen.toggled == 1


# --- a belief made surer in place is checked again ------------------------------------------------------------------

def test_a_belief_updated_in_place_is_checked_again(game):
    from systems.beliefs import believe
    from systems.facts import make_variant, record_fact
    world = game.world
    person = people_at(world, game.place.id, exclude=game.player.id)[0]
    variant = make_variant("robbed", person.id, None, place="the marsh road")
    fact = record_fact(world, person.id, "robbed", None, place=None, variant=variant, spread=False)
    believe(world, game.player.id, fact, variant, person.id, 0.5, 1, "told")
    check_knowledge(world)  # the mark moves past every belief
    world.upsert_belief(game.player.id, fact, variant, None, 0.9, -1, "told")  # surer, so updated in place
    assert any("hops -1" in p for p in check_knowledge(world))


# --- a crash report that cannot be written never ends the game ------------------------------------------------------

def test_a_crash_report_that_cannot_be_written_is_told_not_raised(tmp_path, monkeypatch):
    app = make_app(tmp_path)

    def full(*a, **kw):
        raise OSError("the disk is full")
    monkeypatch.setattr("app.write_crash_report", full)
    assert app.record_crash(RuntimeError("boom"), "test") is None
    assert "could not be saved" in app.log[-1][0]
    app.shutdown()


# --- prose let go lets its backend go too ---------------------------------------------------------------------------

def test_prose_left_behind_lets_its_backend_exchange_go(game):
    class Door(FakeClaude):
        cancelled = []

        def cancel(self, job_name):
            self.cancelled.append(job_name)
    door = Door(lambda job, prompt: time.sleep(0.3) or {"prose": "Late."})
    n = Narration(door, "assist")
    turn = game.perform(Action("rest"))
    log = list(turn.lines)
    n.start(log, 0, turn, game)
    assert n.pending is not None
    n.settle(log)
    assert Door.cancelled == ["narrate"]


# --- the prose cache keeps the latest, not all ----------------------------------------------------------------------

def test_the_prose_cache_keeps_only_the_latest():
    n = Narration(FakeClaude(), "assist")
    for i in range(CACHE_MAX + 50):
        n.remember((i,), f"prose {i}")
    assert len(n.cache) == CACHE_MAX and (CACHE_MAX + 49,) in n.cache and (0,) not in n.cache


# --- the body check's memory belongs to its world -------------------------------------------------------------------

def test_the_body_checks_memory_dies_with_its_world(game):
    check_world(game.world)
    assert game.world._bodies_checked and not hasattr(invariants, "_BODIES_CHECKED")


# --- turning the AI off never waits for the server; the server's imports are warmed ---------------------------------

def test_turning_the_ai_off_never_waits_for_the_server_to_stop(tmp_path, monkeypatch):
    app = make_app(tmp_path, "ai_only")
    server = app.mcp
    assert server is not None
    real_stop, stopped = server.stop, []
    monkeypatch.setattr(server, "stop", lambda: time.sleep(0.5) or real_stop() or stopped.append(1))
    app.handle_key("f1", "")
    began = time.perf_counter()
    app.handle_key("1", "1")  # ai_only -> off
    assert time.perf_counter() - began < 0.3 and app.mcp is None
    deadline = time.monotonic() + 3
    while not stopped and time.monotonic() < deadline:
        time.sleep(0.02)
    assert stopped
    app.shutdown()


def test_with_the_ai_on_the_servers_imports_are_warmed_at_the_title(tmp_path):
    on = App(Config(ai_mode="assist"), tmp_path / "a", tmp_path / "a.json", logs_dir=tmp_path / "la",
             bridge=FakeClaude())
    off = App(Config(ai_mode="off"), tmp_path / "b", tmp_path / "b.json", logs_dir=tmp_path / "lb",
              bridge=FakeClaude())
    assert on._warming is not None and on._warming.daemon and off._warming is None
    on._warming.join(10)
    on.shutdown()
    off.shutdown()
