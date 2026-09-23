import pytest

import systems.duel as duel
from debug.invariants import check_turn, check_world
from engine.game import Action, Game, Turn
from systems.creation import CreationChoice
from systems.items import create_manual
from systems.techniques import create_technique, generate, martial_arts
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def technique(game):
    name, art = generate(rng_for(2, "x"), "martial", form="fist")
    return create_technique(game.world, name, art)


def text(problems):
    return " | ".join(problems)


def test_manual_rules(game):
    item = create_manual(game.world, game.player.id, technique(game), 0.9, claimed=0.5)
    assert "claims less" in text(check_world(game.world))
    game.world.unrelate(game.player.id, "owns", item)
    assert "owners" in text(check_world(game.world))


def test_belief_never_below_truth(game):
    art = martial_arts(game.world, game.player.id)[0]
    game.world.relate(game.player.id, art.technique.id, "knows", value=0.05,
                      data={"completeness": 1.0, "known_completeness": 0.5, "source": "x"})
    assert "believes" in text(check_world(game.world))


def test_fragment_rules(game):
    game.world.update_data(game.player.id, fragments=[{"form": "palm"}] * 13)
    problems = text(check_world(game.world))
    assert "fragments" in problems


def test_live_duel_rules(game):
    npc = game.world.add_entity("person", "Foe", {"occupation": "bandit", "traits": ["proud"], "realm": "mortal",
                                                  "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(npc, game.place.id, "located_in")
    game.perform(Action("talk", npc))
    game.perform(Action("challenge", npc))
    assert check_turn(game, game.look(), []) == []
    game.combat.harm["opponent"] = 250.0
    game.combat.stage = "sulking"
    problems = text(check_turn(game, Turn([], [], {"type": "scene"}, "s"), []))
    assert "harm" in problems and "stage" in problems
