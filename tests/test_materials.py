import pytest

import systems.encounters as encounters
import systems.materials as M
import systems.sect as sect_mod
from debug.invariants import check_crafts
from engine.game import Game
from systems import factions as F
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=5000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def a_beast(game, tag, realm="third-rate"):
    world = game.world
    beast = world.add_entity("person", "a grey wolf", {"beast": True, "occupation": "grey wolf", "realm": realm,
                                                       "traits": ["hot-tempered"]}, f"test:beast:{tag}")
    world.relate(beast, game.place.id, "located_in")
    commit(world, [Event("died", (game.player.id, beast), game.place.id, {"cause": "killed"})])
    return beast


def test_every_material_has_a_grade_and_a_way_to_be_had():
    for name, row in M.MATERIALS.items():
        assert 0 <= row["grade"] <= 4, name
        assert row["sold"] or row.get("source"), name


def test_the_smith_sells_iron_by_the_season_and_a_bought_ingot_is_gone_from_the_stock(game):
    world, me, town = game.world, game.player.id, game.place.id
    offers = M.stock(world, town)
    assert offers and M.stock(world, town) == offers
    kind = world.entity(town).data["kind"]
    assert all(kind in M.MATERIALS[o["material"]]["sold"] for o in offers)
    first = offers[0]
    assert M.buy_block(world, me, town, first["key"]) is None
    commit(world, M.buy_events(world, me, town, first["key"]))
    assert first["key"] not in [o["key"] for o in M.stock(world, town)]
    [item] = M.materials_of(world, me)
    assert M.material_info(item) == (first["material"], M.MATERIALS[first["material"]]["grade"])
    assert silver_of(world, me) == 5000 - M.price(world, town, first["material"])


def test_star_iron_is_a_material_of_the_third_grade_and_stays_a_treasure(game):
    world, me = game.world, game.player.id
    lump = world.add_entity("treasure", "a lump of star iron", {"kind": "star_iron", "value": 500, "used": False})
    world.relate(me, lump, "owns")
    assert M.material_info(world.entity(lump)) == ("star iron", 3)
    M.spend(world, me, [lump])
    assert M.material_info(world.entity(lump)) is None


def test_a_slain_beast_gives_its_bones_and_a_strong_one_its_core(game):
    world, me, here = game.world, game.player.id, game.place.id
    weak, strong = a_beast(game, "weak", "third-rate"), a_beast(game, "strong", "second-rate")
    assert "too weak" in M.parts_block(world, me, weak, "core", here)
    assert M.parts_block(world, me, weak, "bone", here) is None
    commit(world, M.parts_events(world, me, weak, "bone", here))
    assert "already" in M.parts_block(world, me, weak, "bone", here)
    commit(world, M.parts_events(world, me, strong, "core", here))
    assert sorted(M.material_info(m) for m in M.materials_of(world, me)) == [("beast bone", 1), ("beast core", 2)]


def test_a_living_beast_gives_nothing(game):
    world, me, here = game.world, game.player.id, game.place.id
    wolf = world.add_entity("person", "a grey wolf", {"beast": True, "realm": "second-rate"}, "test:beast:alive")
    world.relate(wolf, here, "located_in")
    assert M.parts_block(world, me, wolf, "bone", here) is not None


def test_a_forge_is_owned_rented_or_the_sects_own(game):
    world, me, town = game.world, game.player.id, game.place.id
    assert M.forge_block(world, me, town) is None and M.rent(world, me, town) == M.FORGE_RENT
    commit(world, M.buy_forge_events(world, me, town))
    assert M.forge_of(world, me) is not None and M.rent(world, me, town) == 0
    assert "forge" in sect_mod.BUILDINGS


def test_the_own_sects_forge_is_worked_for_nothing_at_its_seat(game):
    world, me, town = game.world, game.player.id, game.place.id
    sect = world.add_entity("faction", "Pine Cloud Hall", {
        "type": "player_sect", "tier": "minor", "home": [0, 0], "seat": town, "path": "righteous", "taboos": [],
        "trial": "spar", "ranks": list(F.LADDERS["orthodox_sect"]), "treasury": 2000, "power": 20, "wealth": 0,
        "buildings": {"forge": {"done_at": 0, "built": True}}, "last_tick": world.time, "founder": me,
        "dissolved": False, "chronicle": [], "arts": [], "forms": [], "branches": []})
    world.update_data(me, sect=sect)
    assert M.sect_forge(world, me, town) and M.rent(world, me, town) == 0


def test_the_rules_hold_materials_to_the_table(game):
    world, me = game.world, game.player.id
    M.make_material(world, "iron ingot", me)
    assert check_crafts(world) == []
    world.add_entity("material", "moon silver", {"material": "moon silver", "grade": 7})
    assert "material" in " | ".join(check_crafts(world))
