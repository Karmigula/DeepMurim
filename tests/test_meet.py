import pytest

import systems.alchemy as A
import systems.encounters as encounters
import systems.gear as gear
import systems.meet as MT
from debug.invariants import check_crafts
from engine.game import Game
from systems.creation import CreationChoice
from systems.purse import silver_of
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


def opened(game):
    world = game.world
    commit(world, MT.open_events(world, 0))
    return MT.current(world)["town"]


def go(game, place):
    world, me = game.world, game.player.id
    world.unrelate(me, "located_in")
    world.relate(me, place, "located_in")


def test_the_meet_opens_each_spring_in_a_host_city_for_thirty_days(game):
    world = game.world
    assert MT.season_hook(world, 1) == []
    [opening] = MT.season_hook(world, 4)
    commit(world, [opening])
    m = MT.current(world)
    assert m["year"] == 2 and m["end"] - m["start"] == MT.DAYS * 4 and not m["decided"]
    assert check_crafts(world) == []


def test_seven_seeded_masters_stand_in_each_craft(game):
    world = game.world
    field = MT.masters(world, 1, "forging")
    assert len(field) == MT.FIELD and MT.masters(world, 1, "forging") == field
    assert all(MT.MASTER_SCORES[0] <= s <= MT.MASTER_SCORES[1] for _, s in field)


def test_only_ones_own_blade_or_pill_is_shown_once_a_craft(game):
    world, me = game.world, game.player.id
    town = opened(game)
    bought = gear.make_item(world, "weapon", "sword", 3, me, "bought")
    go(game, town)
    assert "own forging" in MT.enter_block(world, me, "forging", bought, town)
    blade = gear.make_item(world, "weapon", "sword", 4, me, "forged", maker=me, forged_by=me)
    world.update_data(me, forge_mastery={"sword": 0.9})
    assert MT.enter_block(world, me, "forging", blade, town) is None
    commit(world, MT.enter_events(world, me, "forging", blade, town))
    assert MT.current(world)["entries"]["forging"][str(me)] == 49.0
    assert "already" in MT.enter_block(world, me, "forging", blade, town)
    pill = A.make_pill(world, me, A.recipe_entity(world, "calming"), 2, 0.9)
    assert MT.enter_block(world, me, "refining", pill, town) is None


def test_the_best_of_each_craft_is_named_when_the_meet_closes(game):
    world, me = game.world, game.player.id
    town = opened(game)
    go(game, town)
    blade = gear.make_item(world, "weapon", "sword", 4, me, "forged", maker=me, forged_by=me)
    world.update_data(me, forge_mastery={"sword": 1.0}, silver=0)
    commit(world, MT.enter_events(world, me, "forging", blade, town))
    assert MT.decide_events(world) == []  # still open
    world.set_time(MT.current(world)["end"])
    commit(world, MT.decide_events(world))
    assert MT.current(world)["decided"]
    assert silver_of(world, me) == MT.PRIZE and any("anvil" in t for t in world.entity(me).data["titles"])
    facts = world.facts(predicate="meet_won")
    assert {f.variant["craft"] for f in facts} == set(MT.CRAFTS)
    assert MT.decide_events(world) == []  # decided once


def test_no_one_shows_a_piece_where_the_meet_is_not_held(game):
    world, me = game.world, game.player.id
    town = opened(game)
    blade = gear.make_item(world, "weapon", "sword", 4, me, "forged", maker=me, forged_by=me)
    elsewhere = game.place.id if game.place.id != town else None
    if elsewhere is not None:
        assert "not held here" in MT.enter_block(world, me, "forging", blade, elsewhere)
    world.set_time(MT.current(world)["end"])
    assert "not held here" in MT.enter_block(world, me, "forging", blade, town)


def test_the_rules_catch_a_malformed_meet(game):
    world = game.world
    world.set_meta("meet", {"year": 1, "town": 999999, "start": 10, "end": 5, "entries": {}, "decided": False})
    assert "Meet" in " | ".join(check_crafts(world))
