import gc
import random
import time
from pathlib import Path

import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.crisis_page import succession_lines
from engine.game import Game
from systems.creation import CreationChoice
from tests.test_crisis_play import crisis_at_seat
from tests.intrigue import still


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    still(monkeypatch)  # 4h's intrigue stilled: these test 4g's crises
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)


def average(fn, n=10) -> float:
    """CPU time per call, averaged: Windows' CPU clock ticks in 15.6 ms steps (4e ruling 19)."""
    fn()
    gc.collect()
    start = time.process_time()
    for _ in range(n):
        fn()
    return (time.process_time() - start) / n


def test_the_fork_guide_covers_succession_crises():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("succession_crisis", "doubt", "leaderless_events", "MAX_CLAIMANTS", "PROOF_LEAN", "WILL_STATES",
                 "sect_token", "TRANSMIT_CHANCE", "EMERGE_CHANCE", "MAX_BREAKAWAYS", "ABSENCE", "check_crises",
                 "regency_for", "secluded"):
        assert word in guide, word


def test_a_crisis_costs_little_on_a_turn_and_a_page(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert average(lambda: C.camps(world, crisis)) < 0.01  # the camps, settled at a stage or on the page
    assert average(lambda: succession_lines(world, me)) < 0.03  # the Succession block
    assert average(lambda: game.perform(Action("look"))) < 0.05  # a turn at the seat
    assert average(lambda: SC.leaderless_events(world, sect, 99)) < 0.005  # the clock's question, crisis live


def test_a_guard_dutys_raider_is_no_tournament_raid(game):
    """The realm heir's fuzz found 4e reading a 3b duty's raid as a tournament's (plan ruling 11)."""
    from systems import founding
    from world.events import Event, commit
    world, me, town = game.world, game.player.id, game.place.id
    raider = founding.make_person(world, "test:raider", town, occupation="bandit", age=30)
    [duel] = commit(world, [Event("raid", (me, raider), town, {"duty": town})])
    game._after_duel({"duel": duel, "mode": "duel", "result": "won", "verdict": None, "purpose": {"raid": town}})  # no KeyError: it is no occurrence
