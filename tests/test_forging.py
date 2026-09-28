import pytest

import systems.encounters as encounters
import systems.famous as FW
import systems.forging as FG
import systems.gear as gear
import systems.materials as M
from debug.invariants import check_crafts
from engine.game import Game
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit


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


def mats(game, *names):
    return [M.make_material(game.world, n, game.player.id) for n in names]


def test_the_grade_is_the_mean_of_the_materials_and_a_master_adds_one(game):
    world, me = game.world, game.player.id
    assert FG.grade_of(world, me, "sword", mats(game, "iron ingot", "black steel", "spirit iron")) == 1
    assert FG.grade_of(world, me, "sword", mats(game, "spirit iron", "star iron")) == 2
    world.update_data(me, forge_mastery={"sword": 0.8})
    assert FG.grade_of(world, me, "sword", mats(game, "spirit iron", "star iron")) == 3
    assert FG.grade_of(world, me, "sword", mats(game, "star iron", "star iron")) == 4


def test_a_forged_blade_is_made_by_the_smith_and_teaches_the_hand(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    monkeypatch.setattr(FG, "BOUNDS", (1.0, 1.0))
    items = mats(game, "black steel", "black steel")
    assert FG.forge_block(world, me, town, "weapon", "sword", items) is None
    start = world.time
    commit(world, FG.forge_events(world, me, town, "weapon", "sword", items))
    made = world.entity(world.entity(me).data["last_forged"])
    assert made.data["grade"] == 1 and made.data["form"] == "sword" and made.data["maker"] == me
    assert made.name == "a fine steel sword" and made.id in world.targets(me, "owns")
    assert FG.mastery(world, me, "sword") == pytest.approx(FG.FIRST_MASTERY + FG.MASTERY_STEP)
    assert world.entity(me).data["forge_xp"] == 2 and world.time == start + FG.WATCHES
    assert silver_of(world, me) == 5000 - M.FORGE_RENT and not M.materials_of(world, me)


def test_a_failed_forging_spends_the_materials_and_the_worst_burn(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    monkeypatch.setattr(FG, "BOUNDS", (0.0, 0.0))
    commit(world, FG.forge_events(world, me, town, "armour", "mail", mats(game, "iron ingot")))
    assert not gear.gear_items(world, me) or all(i.data.get("forged_by") is None for i in gear.gear_items(world, me))
    assert not M.materials_of(world, me)
    monkeypatch.setattr(FG, "BURN_SHARE", 1.0)
    commit(world, FG.forge_events(world, me, town, "armour", "mail", mats(game, "iron ingot")))
    assert any(i.cause == "a forge's fire" for i in load_body(world, me).injuries)


def test_nothing_of_no_shape_is_forged_and_the_anvil_takes_one_to_three(game):
    world, me, town = game.world, game.player.id, game.place.id
    assert "shape" in FG.forge_block(world, me, town, "weapon", "mail", mats(game, "iron ingot"))
    assert "1 to 3" in FG.forge_block(world, me, town, "weapon", "sword", mats(game, *["iron ingot"] * 4))


def test_the_forging_level_grows_with_what_is_forged(game):
    world, me = game.world, game.player.id
    assert FG.level(world, me) == 0
    world.update_data(me, forge_xp=40)
    assert FG.level(world, me) == 2


def test_refining_lifts_a_held_piece_a_grade_with_a_finer_material(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    sword = gear.make_item(world, "weapon", "sword", 0, me, "bought")
    [steel] = mats(game, "black steel")
    [ingot] = mats(game, "iron ingot")
    assert "finer" in FG.refine_block(world, me, town, sword, ingot)
    monkeypatch.setattr(FG, "BOUNDS", (1.0, 1.0))
    monkeypatch.setattr(FG, "REFINE_PENALTY", 0.0)
    assert FG.refine_block(world, me, town, sword, steel) is None
    commit(world, FG.refine_events(world, me, town, sword, steel))
    assert world.entity(sword).data["grade"] == 1 and world.entity(sword).name == "a fine steel sword"


def test_a_failed_refining_now_and_then_cracks_the_piece(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    sword = gear.make_item(world, "weapon", "sword", 0, me, "bought")
    monkeypatch.setattr(FG, "BOUNDS", (0.0, 0.0))
    monkeypatch.setattr(FG, "REFINE_CRACK", 1.0)
    commit(world, FG.refine_events(world, me, town, sword, mats(game, "black steel")[0]))
    assert world.entity(sword).data["broken"] and world.entity(sword).data["grade"] == 0


def test_a_treasure_of_ones_own_forging_is_named_and_made_famous(game):
    world, me, town = game.world, game.player.id, game.place.id
    bought = gear.make_item(world, "weapon", "sword", 3, me, "bought")
    assert "own forging" in FG.masterwork_block(world, me, bought)
    blade = gear.make_item(world, "weapon", "saber", 3, me, "forged", maker=me, forged_by=me)
    low = gear.make_item(world, "weapon", "saber", 2, me, "forged", maker=me, forged_by=me)
    assert "treasure" in FG.masterwork_block(world, me, low)
    assert FG.masterwork_block(world, me, blade) is None
    names = FG.names_for(world, blade)
    assert len(names) == 3 and all(n.endswith("Saber") for n in names) and FG.names_for(world, blade) == names
    commit(world, FG.masterwork_events(world, me, blade, names[1], town))
    assert world.entity(blade).name == names[1] and world.entity(blade).data["famous"]
    assert blade in FW.famous_weapons(world)
    [fact] = [f for f in world.facts(predicate="blade_legend") if f.subject == blade]
    assert fact.variant["legend"] == f"forged by {world.entity(me).name}"
    assert "already" in FG.masterwork_block(world, me, blade)
    assert check_crafts(world) == []


def test_the_rules_hold_a_forging_mastery_to_0_1(game):
    world, me = game.world, game.player.id
    world.update_data(me, forge_mastery={"sword": 1.5})
    assert "mastery" in " | ".join(check_crafts(world))
