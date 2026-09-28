"""Phase 5d review: every craft choice has a number to press, commissions say what they are, and the Meet is news."""

import pytest

import systems.craft_world as CW
import systems.encounters as encounters
import systems.formations as FM
import systems.gear as gear
import systems.materials as M
import systems.meet as MT
from engine.actions import Action
from engine.commands import parse
from engine.game import MAX_SHOWN, Game
from systems.creation import CreationChoice
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=20000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "mortal", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:creview:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def shown(turn):
    return [c.label for c in turn.choices]


def test_a_second_material_and_the_refining_are_on_screen_with_one_on_the_anvil(game):
    world, me = game.world, game.player.id
    for name in ("black steel", "iron ingot", "spirit iron"):
        M.make_material(world, name, me)
    gear.make_item(world, "weapon", "sword", 0, me, "bought")
    turn = game.perform(Action("anvil"))
    turn = game.perform(next(c.action for c in turn.choices if c.label == "Put black steel on the anvil"))
    labels = shown(turn)
    assert "Forge..." in labels and "Refine a piece..." in labels and "Put iron ingot on the anvil" in labels
    assert len(turn.choices) <= MAX_SHOWN
    forms = game.perform(Action("craft_menu", "forge_menu"))
    assert len([c for c in forms.choices if c.action.verb == "forge"]) == 7 and forms.choices[-1].label == "Back"
    assert forms.choices[-1].action == Action("anvil")


def test_forge_is_typed_from_the_anvil(game, monkeypatch):
    import systems.forging as FG
    world, me = game.world, game.player.id
    monkeypatch.setattr(FG, "BOUNDS", (1.0, 1.0))
    M.make_material(world, "black steel", me)
    turn = game.perform(Action("anvil"))
    turn = game.perform(next(c.action for c in turn.choices if c.action.verb == "add_material"))
    assert parse("forge sword", turn.choices, turn.extra) == Action("forge", ("weapon", "sword"))


def test_a_grandmasters_every_manual_and_lay_has_a_number(game):
    world, me = game.world, game.player.id
    master = someone(game, "master", occupation="fortune teller", craft_skill=5)
    game.perform(Action("talk", master))
    turn = game.perform(Action("craft_talk"))
    assert len(turn.choices) <= MAX_SHOWN
    manuals = game.perform(Action("craft_menu", "craft_manuals"))
    assert len([c for c in manuals.choices if c.action.verb == "buy_manual"]) == len(CW.teaches(world, master)) == 7
    game.perform(Action("craft_talk"))
    lays = game.perform(Action("craft_menu", "craft_lay"))
    assert {c.action.target[1] for c in lays.choices if c.action.verb == "commission_lay"} \
        == {k for k in CW.teaches(world, master) if FM.PATTERNS[k]["use"] != "defence"}
    assert lays.choices[-1].action == Action("craft_talk")


def test_a_commission_is_told_while_it_is_forged_and_armour_is_named_as_armour(game):
    world, me = game.world, game.player.id
    smith = someone(game, "smith", occupation="blacksmith", craft_skill=3)
    game.perform(Action("talk", smith))
    game.perform(Action("craft_talk"))
    turn = game.perform(Action("commission_forge", (smith, "armour", "inner_vest")))
    turn = game.perform(Action("craft_talk"))
    assert "Your spirit-steel silk inner vest will be ready in 10 day(s)." in [t for t, _ in turn.lines]
    world.set_time(world.time + CW.FORGE_DAYS * 4)
    turn = game.perform(Action("collect_commission", smith))
    assert any("hands over the spirit-steel silk inner vest" in t for t, _ in turn.lines)
    journal = " | ".join(t for t, _ in game.perform(Action("journal")).lines)
    assert "forge a spirit-steel silk inner vest" in journal and "Collected a spirit-steel silk inner vest" in journal


def test_the_crafts_page_tells_where_the_meet_is_held(game):
    world = game.world
    commit(world, MT.open_events(world, 0))
    page = [t for t, _ in game.perform(Action("crafts")).lines]
    town = world.entity(MT.current(world)["town"]).name
    assert f"The Meet of Hammer and Furnace is held in {town} for 30 more day(s)." in page
