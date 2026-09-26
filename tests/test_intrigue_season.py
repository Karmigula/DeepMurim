import gc
import random
import time
from pathlib import Path

import pytest

import systems.encounters as encounters
import systems.legitimacy as L
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from tests.intrigue import still
from tests.test_crisis_contest import a_crisis
from tests.test_intrigue_play import a_murder
from world.events import commit


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
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(L, "MANUAL_CHANCE", 0.0)


def average(fn, n=10) -> float:
    """CPU time per call, averaged: Windows' CPU clock ticks in 15.6 ms steps (4e ruling 19)."""
    fn()
    gc.collect()
    start = time.process_time()
    for _ in range(n):
        fn()
    return (time.process_time() - start) / n


def test_the_fork_guide_covers_succession_intrigue():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("open_plots", "RED_HERRING", "ACCUSE_CLUES", "EXPOSE_HOOKS", "MURDER_CHANCE", "PUPPET_CHANCE",
                 "SPY_CHANCE", "FORGE_CHANCE", "RETURN_SEASONS", "ART_KNOWN", "TEST_BOUNDS", "ARBITER_CHANCE",
                 "check_plots", "still(monkeypatch)"):
        assert word in guide, word


def test_the_plot_hooks_stay_cheap_with_fifty_open_plots(game):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    cult = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "demonic_cult")
    kinds = ("murder", "spy", "forgery")  # the lasting kinds (a puppet lives only in its crisis, a frame in one)
    for i in range(50):  # every lasting type, as a long world gathers them
        kind = kinds[i % len(kinds)]
        commit(world, P.made_events(world, kind, f"speed:{i}", elder, sect, seat, target=leader,
                                    patron=cult if kind == "spy" else None,
                                    clues=[P.clue("body", elder), P.clue("motive", elder, at="quarters")]))
    assert len(P.open_plots(world)) == 50
    n = lives.current_season(world)
    assert average(lambda: P.season_events(world, n)) < 0.005


def test_a_turn_at_a_seat_with_plots_costs_little(game, monkeypatch):
    world = game.world
    sect, seat, proud, plot = a_murder(game, monkeypatch)
    assert average(lambda: game.perform(Action("look"))) < 0.05


def test_far_away_an_exposed_plotter_cannot_win_and_a_puppet_is_weighed_up(game, monkeypatch):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    elders = halls.staff_at(world, sect, seat, roles=("elder",))
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    commit(world, P.made_events(world, "forgery", "far:test", elders[0], sect, seat, target=sect,
                                clues=[P.clue("seal", elders[0])]))
    [plot] = P.plots_of(world, sect, ("forgery",))
    commit(world, P.exposed_events(world, plot, None, seat))
    assert P.exposed_plotters(world, sect) == {elders[0]}
    for _ in range(3):  # whatever the rolls, the stained never win
        standing = [{"person": elders[0], "kind": "elder"}, {"person": elders[1], "kind": "elder"}]
        commit(world, [SC.Event("crisis_summarised", (), seat, {"faction": sect, "season": random.randrange(10 ** 6),
                                                                 "cause": "close", "leader": leader,
                                                                 "claimants": standing})])
        assert C_role(world, elders[0], sect) != "leader"


def C_role(world, person, faction):
    import systems.claimants as C
    return C.role_in(world, person, faction)


def test_far_away_the_founders_hall_may_choose(game, monkeypatch):
    monkeypatch.setattr(L, "NPC_TRY", 1.0)
    monkeypatch.setattr(L, "test_chance", lambda world, person: 1.0)
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    elders = halls.staff_at(world, sect, seat, roles=("elder",))
    world.update_data(elders[1], traits=["proud"])
    world.update_data(elders[0], traits=["kind"])
    standing = [{"person": e, "kind": "elder"} for e in elders]
    assert L.far_founder(world, sect, standing, random.Random(1)) == elders[1]
