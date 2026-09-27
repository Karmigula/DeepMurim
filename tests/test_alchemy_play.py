import pytest

import systems.alchemy as A
import systems.encounters as encounters
import systems.herbs as H
import systems.poison_path as PP
import systems.toxins as X
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.outcomes import SUMMARIES
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import WATCHES_PER_DAY
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


def labels(turn):
    return [c.label for c in turn.all_choices]


def test_the_alchemy_page_shows_herbs_as_known(game):
    world, me = game.world, game.player.id
    H.make_herb(world, "willow bark", 0, me)
    turn = game.perform(Action("alchemy"))
    text = " | ".join(t for t, _ in turn.lines)
    assert "willow bark (a year): its nature unknown until tasted" in text
    game.perform(Action("taste", H.herbs_of(world, me)[0].id))
    H.make_herb(world, "willow bark", 0, me)
    text = " | ".join(t for t, _ in game.perform(Action("alchemy")).lines)
    assert "willow bark (a year): wood, yin, potency 1, toxicity 0" in text


def test_herbs_go_in_the_furnace_and_the_furnace_is_lit(game):
    world, me = game.world, game.player.id
    one, two = (H.make_herb(world, "frost lotus leaf", 0, me) for _ in range(2))
    game.perform(Action("alchemy"))
    game.perform(Action("add_herb", one))
    turn = game.perform(Action("add_herb", two))
    assert "Light the furnace (2 herbs)" in labels(turn)
    game.perform(Action("experiment"))
    assert A.known_recipes(world, me)


def test_a_known_recipe_is_refined_from_the_herbs_carried(game, monkeypatch):
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (1.0, 1.0))
    world, me = game.world, game.player.id
    recipe = A.recipe_entity(world, "earth_qi")
    world.relate(me, recipe, "knows_recipe", 0.1)
    for name in ("ginseng", "tiger bone vine", "willow bark"):
        H.make_herb(world, name, 0, me)
    H.learn(world, me, ["ginseng", "tiger bone vine", "willow bark"])  # one refines only from herbs one knows
    turn = game.perform(Action("alchemy"))
    assert f"Refine {world.entity(recipe).name}" in labels(turn)
    game.perform(Action("refine", recipe))
    assert any(world.entity(i).kind == "pill" for i in world.targets(me, "owns"))


def test_the_herbalist_sells_herbs_and_a_furnace(game):
    world, me = game.world, game.player.id
    turn = game.perform(Action("herbalist"))
    buys = [c for c in turn.all_choices if c.action.verb == "buy_herb"]
    assert buys and f"Buy a bronze furnace ({H.FURNACE_PRICE} silver)" in labels(turn)
    game.perform(buys[0].action)
    assert H.herbs_of(world, me)


def test_gathering_can_be_done_from_the_scene(game):
    world, me = game.world, game.player.id
    assert "Search the surroundings for herbs" in labels(game.perform(Action("look")))
    start = world.time
    game.perform(Action("gather"))
    assert world.time >= start + H.GATHER_WATCHES


def test_the_poisoned_may_seal_and_the_sheet_tells_of_it(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.realm, body.energy_years = 1, 1.0
    save_body(world, me, body)
    X.poison(world, me, 2, 20, "a hidden needle")
    assert "Seal your acupoints against the poison" in labels(game.perform(Action("look")))
    text = " | ".join(t for t, _ in sheet_lines(world, me))
    assert "1 poison(s) in your blood" in text
    page = " | ".join(t for t, _ in game.perform(Action("alchemy")).lines)
    assert "grade unknown" in page  # a needle's poison is not named until known


def test_a_poison_that_outlasts_you_is_your_death(game):
    world, me = game.world, game.player.id
    X.poison(world, me, 5, 40, "a hidden needle")
    world.set_time(world.time + 3 * WATCHES_PER_DAY + 1)
    turn = game.perform(Action("rest"))
    assert world.entity(me).data.get("dying") or world.entity(me).data.get("dead") or \
        any("poison" in t for t, _ in turn.lines)


def test_a_poison_death_waits_for_the_deed_to_end(game):
    world, me = game.world, game.player.id
    route = next(c.action for c in game.perform(Action("routes")).all_choices if c.action.verb == "travel")
    X.poison(world, me, 5, 40, "a hidden needle")
    world.set_time(world.time + 2 * WATCHES_PER_DAY)  # a day short of death: the road will take the rest
    assert not X.lethal(load_body(world, me))
    game.perform(route)  # travel commits step by step: death comes when the journey's turn is done, not midway
    assert world.entity(me).data.get("dying") or world.entity(me).data.get("dead")


def test_typed_words_reach_the_furnace(game):
    turn = game.perform(Action("look"))
    for word, verb in (("alchemy", "alchemy"), ("gather", "gather"), ("herbalist", "herbalist"), ("seal", "seal"),
                       ("force out", "force_out")):
        assert parse(word, turn.choices, turn.extra).verb == verb


def test_help_names_alchemy(game):
    assert any("alchemy | gather | herbalist" in t for t, _ in game.perform(Action("help")).lines)


def test_every_alchemy_deed_has_a_journal_line():
    for kind in ("herb_tasted", "herbs_gathered", "herb_bought", "furnace_bought", "experimented", "refined",
                 "pill_taken", "blade_coated", "acupoints_sealed", "poison_forced", "poison_art_bought",
                 "beast_butchered", "bathed"):
        assert kind in SUMMARIES, kind


def test_a_slain_venomous_beast_can_be_butchered_from_the_scene(game):
    world, me = game.world, game.player.id
    beast = world.add_entity("person", "a red toad", {"beast": True, "venomous": True, "occupation": "red toad",
                                                      "traits": ["hot-tempered"], "realm": "second-rate"}, "test:toad")
    world.update_data(beast, dead=True)
    game._slain_beast = beast
    assert "Drink a red toad's blood" in labels(game.perform(Action("look")))
    game.perform(Action("butcher", "blood"))
    assert load_body(world, me).resist == PP.BLOOD_RESIST


def test_a_strong_child_takes_no_apprentice(game):
    import random
    from systems.agendas import apprentice_events
    world = game.world
    child = world.add_entity("person", "A Prodigy", {"occupation": "merchant", "traits": [], "realm": "second-rate",
                                                     "age": 8, "portrait": {"hair": 0, "face": 0, "robe": 0}},
                             "test:prodigy")
    world.relate(child, game.place.id, "located_in")
    youth = world.add_entity("person", "A Willing Youth", {"occupation": "merchant", "traits": [], "realm": "mortal",
                                                          "age": 15, "lived_to": 4,
                                                          "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:youth")
    world.relate(youth, game.place.id, "located_in")  # someone to take on, were the child allowed to

    class Always(random.Random):
        def random(self):
            return 0.0
    assert apprentice_events(world, child, 4, Always()) == []
