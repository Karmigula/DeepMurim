import gc
import time
from pathlib import Path

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.famous as FW
import systems.gear as gear
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
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


def average(fn, n=10) -> float:
    """CPU time per call, averaged: Windows' CPU clock ticks in 15.6 ms steps (4e ruling 19)."""
    fn()
    gc.collect()
    start = time.process_time()
    for _ in range(n):
        fn()
    return (time.process_time() - start) / n


def staffed(world):
    for fid in F.ensure_roster(world):
        seat = halls.seat_of(world, fid)
        if seat is not None:
            halls.staff_at(world, fid, seat)


def test_the_fork_guide_covers_items_with_history():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("famous_weapons", "gear.POWER", "materialize", "wields", "DEED_HOOKS", "BREAK_CHANCE",
                 "claimed_by", "check_gear", "weapons_ranked", "armoury"):
        assert word in guide, word


def test_reading_gear_adds_little_to_a_duel(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    art = duel.best_art(world, elder)
    technique = art.technique.id if art else None
    with_gear = average(lambda: duel.fighter_for(world, elder, technique), n=50)
    assert average(lambda: (gear.weapon_mult(world, elder, "sword"), gear.armour_share(world, elder)), n=50) < 0.001
    assert with_gear < 0.02


def test_the_chronicle_survey_stays_cheap(game):
    world = game.world
    staffed(world)
    FW.ensure_famous(world)
    assert FW.famous_weapons(world)
    assert average(lambda: FW.chronicle_events(world, 4)) < 0.02


def test_a_turn_with_a_known_blade_costs_little(game):
    world, me = game.world, game.player.id
    staffed(world)
    FW.ensure_famous(world)
    item = gear.make_item(world, "weapon", "sword", 3, me, "found")
    commit(world, gear.wield_events(world, me, item, game.place.id))
    assert average(lambda: game.perform(Action("look"))) < 0.05


def test_lazy_gear_makes_nothing_for_those_who_never_matter(game):
    world = game.world
    before = len(world.entities("gear"))
    staffed(world)
    for fid in F.ensure_roster(world):
        for person in halls.staff_at(world, fid, halls.seat_of(world, fid)) if halls.seat_of(world, fid) else []:
            gear.weapon_mult(world, person, "sword")
            gear.armour_share(world, person)
    assert len(world.entities("gear")) == before
