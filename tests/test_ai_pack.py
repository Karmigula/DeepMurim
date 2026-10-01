import gc
import re
import time

import pytest

import systems.encounters as encounters
import systems.toxins as X
from ai.pack import LIMITS, MAX_PACK, build_pack
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice


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


def test_the_pack_tells_where_you_are_what_you_may_do_and_what_you_carry(game):
    pack = build_pack(game)
    for section in ("HERE:", "LIMITS:", "CARRYING:", "LATELY:", "YOU:"):
        assert section in pack, section
    assert game.place.name in pack and LIMITS[0] in pack
    assert f"you carry {game.world.entity(game.player.id).data['silver']} silver" in pack
    here = next(p for p in game.world.sources(game.place.id, "located_in") if p != game.player.id)
    assert game.world.entity(here).name in pack  # those here are named, as the scene names them
    assert len(pack) <= MAX_PACK


def test_the_pack_carries_no_ids_and_no_stranger_from_elsewhere(game):
    world = game.world
    far = world.add_entity("person", "Gu Faraway", {"occupation": "monk", "traits": ["kind"], "realm": "mortal",
                                                    "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:pack:far")
    pack = build_pack(game)
    assert "Gu Faraway" not in pack
    assert not re.search(r"#\d", pack)


def test_the_pack_follows_what_you_do(game):
    game.perform(Action("rest", 1))
    assert "rest" in build_pack(game).split("LATELY:")[1].lower()


def test_a_poison_unnamed_is_not_given_away(game):
    X.poison(game.world, game.player.id, 3, 12, "a hidden needle")
    pack = build_pack(game)
    assert "grade unknown" in pack and "grade 3" not in pack


def test_the_pack_is_quick(game):
    build_pack(game)
    gc.collect()
    start = time.perf_counter()
    for _ in range(20):
        build_pack(game)
    assert (time.perf_counter() - start) / 20 < 0.015
