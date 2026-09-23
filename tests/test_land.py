import pytest

import systems.encounters as encounters
import systems.land as land
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.gen.materialize import ensure_region, ensure_town
from world.gen.region import region_spec


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


def go(game, town):
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")


def towns(game, radius=4):
    for x in range(-radius, radius + 1):
        for y in range(-radius, radius + 1):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                yield ensure_town(game.world, x, y, i)


def buyable_town(game):
    for town in towns(game):
        halls.settle_town(game.world, town)
        if land.magistrate_of(game.world, town) and land.buy_block(game.world, game.player.id, town) != "This land is not for sale.":
            return town
    raise AssertionError("no buyable town")


def test_buying_land_from_the_magistrate(game):
    town = buyable_town(game)
    go(game, town)
    price = land.land_price(game.world, town)
    game.world.update_data(game.player.id, silver=price + 5)
    magistrate = land.magistrate_of(game.world, town)
    game.perform(Action("talk", magistrate))
    turn = game.perform(Action("faction_menu"))
    assert Action("buy_land", town) in [c.action for c in turn.choices]
    game.perform(Action("buy_land", town))
    assert land.owner_of(game.world, town) == game.player.id and silver_of(game.world, game.player.id) == 5
    assert land.buy_block(game.world, game.player.id, town) == "This land is already yours."


def test_ruins_are_seeded_and_never_in_a_great_home(game):
    homes = {tuple(game.world.entity(f).data["home"]) for f in F.ensure_roster(game.world)}
    ruins = [t for t in towns(game) if land.is_ruin(game.world, t)]
    assert ruins
    for t in ruins:
        data = game.world.entity(t).data
        assert (data["x"], data["y"]) not in homes
    assert [t for t in towns(game) if land.is_ruin(game.world, t)] == ruins


def test_claiming_a_ruin_may_need_a_duel(game):
    ruin = next(t for t in towns(game) if land.is_ruin(game.world, t))
    go(game, ruin)
    turn = game.perform(Action("look"))
    assert any("abandoned hall" in text for text, _ in turn.lines)
    game.perform(Action("claim_land", ruin))
    if land.contester(game.world, ruin) is None:
        assert land.owner_of(game.world, ruin) == game.player.id
    else:
        assert game.combat is not None and game.combat.purpose == {"claim": ruin}
        game._finish_duel({"mode": "duel", "result": "won", "purpose": {"claim": ruin}})
        assert land.owner_of(game.world, ruin) == game.player.id


def test_seizing_a_minor_seat_scatters_its_people(game):
    fort = None
    for x in range(-4, 5):
        for y in range(-4, 5):
            for fid in F.minor_factions(game.world, game.world.entity(ensure_region(game.world, x, y))):
                fort = fort or fid
    seat = game.world.entity(fort).data["seat"]
    go(game, seat)
    leader = halls.staff_at(game.world, fort, seat, roles=("leader",))[0]
    staff = halls.staff_at(game.world, fort, seat)
    assert land.seizable(game.world, leader, seat) == fort
    game.perform(Action("talk", leader))
    game.perform(Action("seize_seat", fort))
    assert game.combat.purpose == {"seize": fort}
    game._finish_duel({"mode": "duel", "result": "won", "purpose": {"seize": fort}})
    assert land.owner_of(game.world, seat) == game.player.id
    assert game.world.entity(fort).data["dissolved"]
    assert fort not in halls.halls_here(game.world, seat)
    assert all(F.membership(game.world, p, fort)[1]["status"] == "expelled" for p in staff)
    assert any(m.feeling == "wronged" for m in game.world.memories(staff[1], about=game.player.id))
    assert game.world.facts(predicate="seized")[0].subject == game.player.id
