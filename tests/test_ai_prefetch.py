import gc
import re
import time

import pytest

import systems.encounters as encounters
from ai.narrate import PROSE_SCHEMA, SYSTEM
from ai.prefetch import build_prefetch, words_of
from engine.actions import Action
from engine.game import Game
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.gen.materialize import people_at


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def a_tale(game, holder, about="bandits"):
    world = game.world
    far = world.add_entity("person", "Gu Bandit", {"occupation": "bandit", "traits": ["cunning"], "realm": "mortal",
                                                   "portrait": {"hair": 0, "face": 0, "robe": 0}}, f"test:pre:{about}")
    variant = make_variant("robbed", far, None, place="the marsh road")
    fact = record_fact(world, far, "robbed", None, place=None, variant=variant, spread=False)
    believe(world, holder, fact, variant, None, 0.9, 1, "test")
    return fact


def test_the_people_here_are_always_told(game):
    text = build_prefetch(game, "I look around.")
    for person in people_at(game.world, game.place.id, exclude=game.player.id)[:15]:
        assert f"- {person.name}, {person.data['occupation']}" in text


def test_someone_named_brings_what_they_are_and_remember(game):
    here = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    game.perform(Action("talk", here.id))
    text = build_prefetch(game, f"I ask {here.name} about the road.")
    assert f"{here.name.upper()} AS YOU KNOW THEM:" in text and f"WHAT {here.name.upper()} REMEMBERS OF YOU:" in text
    assert "Met " in text


def test_beliefs_touching_the_words_come_with_their_handles(game):
    here = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    a_tale(game, here.id)
    text = build_prefetch(game, f"{here.name}, have you heard of anyone robbed on the roads?")
    assert "WHAT THOSE HERE HOLD ON YOUR WORDS" in text and re.search(r"\[b[0-9a-f]{10}\].*Gu Bandit robbed", text)
    assert "WHAT THOSE HERE HOLD" not in build_prefetch(game, f"{here.name}, what fine weather.")


def test_the_prefetch_carries_no_ids_and_is_quick(game):
    here = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    a_tale(game, here.id)
    typed = f"I ask {here.name} about anyone robbed."
    assert not re.search(r"#\d", build_prefetch(game, typed))
    gc.collect()
    start = time.perf_counter()
    for _ in range(10):
        build_prefetch(game, typed)
    assert (time.perf_counter() - start) / 10 < 0.02


def test_words_are_the_telling_ones():
    assert words_of("Tell me about the robbed merchant, would you?") == {"robbed", "merchant"}


def test_prose_is_asked_as_a_paragraph():
    assert "one paragraph of about 3-6" in SYSTEM and PROSE_SCHEMA["properties"]["prose"]["maxLength"] == 1500
