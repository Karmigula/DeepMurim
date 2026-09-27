import pytest

import systems.alchemy as A
import systems.herbs as H
from engine.game import Game
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit

# a batch of herbs that meets each base recipe: the table and the recipes agree
BATCHES = {
    "earth_qi": ["ginseng", "tiger bone vine"], "fire_qi": ["blood lotus", "red flame root"],
    "bottleneck": ["dragon-bone moss", "iron thorn", "iron thorn"], "purity": ["heaven's dew orchid"] * 2,
    "wood_healing": ["jade bamboo heart"] * 2, "earth_healing": ["yellow earth tuber"] * 2,
    "mending": ["snow lingzhi", "red flame root"], "calming": ["frost lotus leaf"] * 2,
    "cleansing": ["willow bark"] * 4, "metal_antidote": ["silver needle leaf", "silver needle leaf", "cold iron sand"],
    "pure_antidote": ["heaven's dew orchid", "heaven's dew orchid", "moon dew grass", "willow bark"],
    "yin_poison": ["black lotus", "corpse flower"], "yang_poison": ["scorpion tail weed"] * 2,
    "venom": ["green viper moss", "ghost reed"], "fire_tempering": ["golden sun peach"] * 3,
    "metal_tempering": ["iron thorn", "iron thorn", "silver needle leaf", "silver needle leaf"],
}


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    world, me = g.world, g.player.id
    world.update_data(me, silver=10000)
    yield g
    g.close()


def herbs(game, names, grade=0):
    return [H.make_herb(game.world, n, grade, game.player.id) for n in names]


def test_every_base_recipe_can_be_met_by_its_batch_and_only_it():
    assert set(BATCHES) == set(A.RECIPES)
    for key, names in BATCHES.items():
        assert A.MIN_HERBS <= len(names) <= A.MAX_HERBS
        found, needs = A.best_match(A.combine(names))
        assert found == key and all(needs.values()), key


def test_the_right_herbs_discover_a_recipe_and_a_pill(game):
    world, me = game.world, game.player.id
    batch = herbs(game, BATCHES["calming"])
    assert A.experiment_block(world, me, game.place.id, batch) is None
    [event] = A.experiment_events(world, me, game.place.id, batch)
    assert event.data["result"] == "discovered"
    commit(world, [event])
    recipe = A.recipe_entity(world, "calming")
    assert A.mastery(world, me, recipe) == A.DISCOVERED_MASTERY
    [pill] = [world.entity(i) for i in world.targets(me, "owns") if world.entity(i).kind == "pill"]
    assert pill.data["effect"] == "calming" and pill.data["grade"] == 1
    assert H.known(world, me, "frost lotus leaf") and silver_of(world, me) == 10000 - H.FURNACE_RENT


def test_three_needs_of_four_leave_a_hint(game):
    world, me = game.world, game.player.id
    batch = herbs(game, ["moon dew grass", "moon dew grass"])  # water and yin, but too weak to calm
    [event] = A.experiment_events(world, me, game.place.id, batch)
    assert event.data["result"] == "hint" and event.data["missed"] == "potency"
    commit(world, [event])
    assert "too weak" in world.entity(me).data["alchemy_hints"][0]


def test_a_toxic_sludge_poisons_its_maker(game):
    world, me = game.world, game.player.id
    batch = herbs(game, ["black lotus", "golden sun peach", "golden sun peach"])  # fire, yin: near nothing
    [event] = A.experiment_events(world, me, game.place.id, batch)
    assert event.data["result"] == "sludge" and event.data["fumes"]
    commit(world, [event])
    assert load_body(world, me).poisons


def test_the_same_herbs_give_the_same_answer(game):
    world, me = game.world, game.player.id
    one = A.experiment_events(world, me, game.place.id, herbs(game, BATCHES["venom"]))[0].data
    two = A.experiment_events(world, me, game.place.id, herbs(game, BATCHES["venom"]))[0].data
    assert (one["result"], one["recipe"]) == (two["result"], two["recipe"])


def test_refining_a_known_recipe_makes_pills_and_mastery(game, monkeypatch):
    world, me = game.world, game.player.id
    commit(world, A.experiment_events(world, me, game.place.id, herbs(game, BATCHES["earth_qi"])))
    recipe = A.recipe_entity(world, "earth_qi")
    batch = herbs(game, ["ginseng", "ginseng", "tiger bone vine"])
    assert A.refine_block(world, me, game.place.id, recipe, batch) is None
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (1.0, 1.0))
    [event] = A.refine_events(world, me, game.place.id, recipe, batch)
    assert event.data["success"] and event.data["count"] == 2  # potency 11 over a need of 6
    commit(world, [event])
    assert A.mastery(world, me, recipe) == pytest.approx(A.DISCOVERED_MASTERY + A.MASTERY_STEP)
    assert world.entity(me).data["alchemy_xp"] == event.data["grade"]
    assert event.data["purity"] == pytest.approx(0.4 + 0.5 * A.DISCOVERED_MASTERY)


def test_refining_needs_the_recipe_and_herbs_that_meet_it(game):
    world, me = game.world, game.player.id
    recipe = A.recipe_entity(world, "earth_qi")
    batch = herbs(game, ["ginseng", "tiger bone vine"])
    assert A.refine_block(world, me, game.place.id, recipe, batch) == "You do not know that recipe."
    world.relate(me, recipe, "knows_recipe", 0.1)
    weak = herbs(game, ["willow bark", "moon dew grass"])
    assert "will not make it" in A.refine_block(world, me, game.place.id, recipe, weak)


def test_a_bad_failure_cracks_the_furnace_and_burns(game, monkeypatch):
    world, me = game.world, game.player.id
    commit(world, H.furnace_events(world, me, game.place.id))
    recipe = A.recipe_entity(world, "earth_qi")
    world.relate(me, recipe, "knows_recipe", 0.1)
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (0.001, 0.001))  # all but hopeless: every failure is the worst
    monkeypatch.setattr(A, "CRACK_SHARE", 1e9)
    [event] = A.refine_events(world, me, game.place.id, recipe, herbs(game, ["ginseng", "tiger bone vine"]))
    assert not event.data["success"] and event.data["cracked"]
    commit(world, [event])
    assert H.furnace_of(world, me) is None  # cracked
    assert any(i.cause == "a cracked furnace" for i in load_body(world, me).injuries)


def test_the_alchemy_level_grows_with_experience(game):
    world, me = game.world, game.player.id
    assert A.level(world, me) == 0
    world.update_data(me, alchemy_xp=40)
    assert A.level(world, me) == 2
