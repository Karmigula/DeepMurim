import gc
import time
from pathlib import Path

import pytest

import systems.alchemy as A
import systems.encounters as encounters
import systems.herbs as H
import systems.toxins as X
from engine.game import Game
from systems.creation import CreationChoice

BATCH = ["ginseng", "tiger bone vine"]


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=100000)
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


def test_the_fork_guide_covers_alchemy():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("herbs.toml", "recipes.toml", "herb_lore", "knows_recipe", "residue", "poisoned", "WOUND_HOOKS",
                 "ABSORB_HOOKS", "BEAST_HOOKS", "Myriad Poison Body", "check_alchemy"):
        assert word in guide, word


def test_an_experiment_and_a_refining_are_quick(game):
    world, me = game.world, game.player.id
    herbs = [H.make_herb(world, n, 0, me) for n in BATCH]
    assert average(lambda: A.experiment_events(world, me, game.place.id, herbs)) < 0.005
    recipe = A.recipe_entity(world, "earth_qi")
    world.relate(me, recipe, "knows_recipe", 0.5)
    assert average(lambda: A.refine_events(world, me, game.place.id, recipe, herbs)) < 0.005


def test_the_poison_watch_over_twenty_poisoned_is_quick(game):
    world = game.world
    for n in range(20):
        person = world.add_entity("person", f"Sick {n}", {"occupation": "tea seller", "traits": [], "realm": "mortal",
                                                          "portrait": {"hair": 0, "face": 0, "robe": 0}}, f"test:sick:{n}")
        world.relate(person, game.place.id, "located_in")
        X.poison(world, person, 2, 40, "test")
    assert len(world.get_meta("poisoned")) == 20
    assert average(lambda: X.season_hook(world, 1)) < 0.05


def test_the_refine_choices_stay_quick_with_many_herbs(game):
    world, me = game.world, game.player.id
    for n in range(30):
        H.make_herb(world, sorted(H.HERBS)[n % len(H.HERBS)], 0, me)
    for key in list(A.RECIPES)[:6]:
        world.relate(me, A.recipe_entity(world, key), "knows_recipe", 0.2)
    assert average(lambda: [A.find_batch(world, me, r) for r, _ in A.known_recipes(world, me)]) < 0.05
