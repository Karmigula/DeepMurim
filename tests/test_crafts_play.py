import pytest

import systems.encounters as encounters
import systems.formations as FM
import systems.gear as gear
import systems.materials as M
import systems.meet as MT
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.outcomes import SUMMARIES
from systems.creation import CreationChoice
from world.events import Event, commit


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


def labels(turn):
    return [c.label for c in turn.all_choices]


def pick(turn, verb):
    return next(c.action for c in turn.all_choices if c.action.verb == verb)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "mortal", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:cplay:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_materials_go_on_the_anvil_and_a_blade_is_forged(game, monkeypatch):
    import systems.forging as FG
    world, me = game.world, game.player.id
    monkeypatch.setattr(FG, "BOUNDS", (1.0, 1.0))
    for _ in range(2):
        M.make_material(world, "black steel", me)
    turn = game.perform(Action("anvil"))
    game.perform(pick(turn, "add_material"))
    turn = game.perform(Action("anvil"))
    forge = next(c for c in turn.all_choices if c.action.verb == "forge" and c.action.target == ("weapon", "sword"))
    assert forge.label == "Forge a fine steel sword"
    game.perform(forge.action)
    assert any(i.data.get("forged_by") == me for i in gear.gear_items(world, me))


def test_the_smith_sells_materials_and_a_forge(game):
    turn = game.perform(Action("smith"))
    assert any(label.startswith("Buy iron ingot") for label in labels(turn))
    assert f"Buy an anvil and a forge ({M.FORGE_PRICE} silver)" in labels(turn)
    game.perform(pick(turn, "buy_material"))
    assert M.materials_of(game.world, game.player.id)


def test_a_slain_beast_is_butchered_from_the_scene(game):
    world, me = game.world, game.player.id
    wolf = world.add_entity("person", "a grey wolf", {"beast": True, "occupation": "grey wolf",
                                                      "realm": "second-rate", "traits": ["hot-tempered"]}, "test:wolf")
    world.relate(wolf, game.place.id, "located_in")
    commit(world, [Event("died", (me, wolf), game.place.id, {"cause": "killed"})])
    game._slain_game = wolf
    turn = game.perform(Action("look"))
    assert "Take a grey wolf's bones" in labels(turn) and "Take a grey wolf's core" in labels(turn)
    game.perform(Action("take_parts", "core"))
    assert M.materials_of(world, me)


def test_a_manual_is_studied_and_its_pattern_laid_from_the_crafts_page(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(FM, "BOUNDS", (1.0, 1.0))
    FM.make_manual(world, me, "confusion", "bought")
    FM.add_flags(world, me, 5)
    turn = game.perform(Action("crafts"))
    game.perform(pick(turn, "study_formation"))
    turn = game.perform(Action("crafts"))
    game.perform(pick(turn, "lay_formation"))
    page = " | ".join(t for t, _ in game.perform(Action("crafts")).lines)
    assert "The Confusion array holds here, laid by you (1 day(s) left)." in page


def test_a_formation_master_sells_and_lays_in_conversation(game):
    world, me = game.world, game.player.id
    master = someone(game, "master", occupation="fortune teller", craft_skill=5)
    game.perform(Action("talk", master))
    turn = game.perform(Action("craft_talk"))
    assert any("grandmaster formation master" in t for t, _ in turn.lines)
    game.perform(pick(turn, "buy_flags"))
    assert FM.flags_of(world, me) == 5
    turn = game.perform(Action("craft_talk"))
    game.perform(pick(turn, "commission_lay"))
    assert FM.laid(world, game.place.id)


def test_a_smiths_commission_is_collected_in_conversation(game):
    world, me = game.world, game.player.id
    smith = someone(game, "smith", occupation="blacksmith", craft_skill=3)
    game.perform(Action("talk", smith))
    turn = game.perform(Action("craft_talk"))
    game.perform(pick(turn, "commission_forge"))
    world.set_time(world.time + 10 * 4)
    game.perform(Action("talk", smith))
    turn = game.perform(Action("craft_talk"))
    game.perform(pick(turn, "collect_commission"))
    assert any(i.data["owners"][0]["how"] == "commissioned" for i in gear.gear_items(world, me))


def test_a_masterwork_is_named_from_the_crafts_page(game):
    world, me = game.world, game.player.id
    blade = gear.make_item(world, "weapon", "sword", 3, me, "forged", maker=me, forged_by=me)
    turn = game.perform(Action("crafts"))
    turn = game.perform(pick(turn, "name_menu"))
    game.perform(pick(turn, "name_masterwork"))
    assert world.entity(blade).data["famous"]


def test_the_meet_is_entered_where_it_is_held(game):
    world, me = game.world, game.player.id
    commit(world, MT.open_events(world, 0))
    town = MT.current(world)["town"]
    world.unrelate(me, "located_in")
    world.relate(me, town, "located_in")
    gear.make_item(world, "weapon", "sword", 3, me, "forged", maker=me, forged_by=me)
    assert "The Meet of Hammer and Furnace" in labels(game.perform(Action("look")))
    turn = game.perform(Action("meet"))
    game.perform(pick(turn, "enter_meet"))
    assert str(me) in MT.current(world)["entries"]["forging"]


def test_the_sheet_shows_the_crafts(game):
    world, me = game.world, game.player.id
    FM.learn(world, me, "seclusion")
    assert any("the Seclusion ward" in t for t, _ in sheet_lines(world, me))


def test_typed_words_reach_the_crafts(game):
    turn = game.perform(Action("look"))
    for word, verb in (("crafts", "crafts"), ("anvil", "anvil"), ("forge", "anvil")):
        assert parse(word, turn.choices, turn.extra).verb == verb


def test_help_names_the_crafts(game):
    assert any("crafts | anvil | meet" in t for t, _ in game.perform(Action("help")).lines)


def test_every_craft_deed_has_a_journal_line():
    for kind in ("material_bought", "beast_parts_taken", "forge_bought", "forged", "gear_refined", "masterwork_named",
                 "formation_studied", "formation_laid", "manual_bought", "flags_bought", "formation_commissioned",
                 "forge_commissioned", "commission_collected", "meet_entered", "meet_decided"):
        assert kind in SUMMARIES, kind
