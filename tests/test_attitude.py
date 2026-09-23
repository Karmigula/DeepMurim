import pytest

from engine.game import Game
from systems.attitude import Attitude, afraid, attitude, word_for
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.reputation import Reputation, reputation
from world.events import Event, Witness, commit

RIGHTEOUS = ("Jade", "Azure", "White", "Upright")
RUTHLESS = ("Crimson", "Blood", "Black", "Iron")


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("curious", "lazy"), realm="mortal", occupation="innkeeper"):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {"occupation": occupation, "traits": list(traits), "realm": realm,
                                                 "surname": surname, "given": given})
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def deed(game, actor, predicate, target, **story):
    return record_fact(game.world, actor, predicate, target, place=game.place.id,
                       variant=make_variant(predicate, actor, target, place=game.place.name, **story))


def test_bands():
    assert [word_for(s) for s in (1.2, 0.5, 0.0, -0.5, -1.5, -2.5)] == \
        ["warm", "friendly", "neutral", "wary", "hostile", "hateful"]


def test_a_stranger_with_no_history_is_neutral(game):
    assert attitude(game.world, person(game, "Hu Mei"), game.player.id) == Attitude(0.0, "neutral", None)


def test_gratitude_fades_with_the_seasons(game):
    npc = person(game, "Hu Mei")
    commit(game.world, [Event("helped", (game.player.id, npc), game.place.id, {},
                              witnesses=(Witness(npc, "grateful", 1.0),))])
    now = attitude(game.world, npc, game.player.id)
    assert now.word == "warm" and now.reason == "you showed them mercy"
    game.world.set_time(game.world.time + 720)
    assert attitude(game.world, npc, game.player.id).word == "neutral"


def test_rumours_of_a_killing_turn_the_kind_hateful_and_the_greedy_hostile(game):
    victim = person(game, "Wang Li")
    kind = person(game, "Old Wu", traits=("kind", "honest"))
    greedy = person(game, "Ma Bo", traits=("greedy", "lazy"))
    deed(game, game.player.id, "killed", victim)
    heard = attitude(game.world, kind, game.player.id)
    assert heard.word == "hateful"
    assert heard.reason == f"heard you killed Wang Li in {game.place.name}"
    assert attitude(game.world, greedy, game.player.id).word == "hostile"


def test_a_persona_is_judged_apart_from_the_player(game):
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    victim = person(game, "Wang Li")
    townsman = person(game, "Old Wu", traits=("kind", "honest"))
    deed(game, persona, "killed", victim, masked=True)
    assert attitude(game.world, townsman, game.player.id).word == "neutral"
    assert attitude(game.world, townsman, persona).word == "hateful"
    deed(game, persona, "is", game.player.id)
    assert attitude(game.world, townsman, game.player.id).word == "hateful"


def test_fear_needs_a_killing_and_a_stronger_believed_realm(game):
    weak = person(game, "Hu Mei")
    strong = person(game, "Iron Gu", realm="first-rate")
    victim = person(game, "Wang Li", realm="third-rate")
    deed(game, game.player.id, "defeated", victim, realm="third-rate")
    assert not afraid(game.world, weak, game.player.id)
    deed(game, game.player.id, "killed", victim, realm="third-rate")
    assert afraid(game.world, weak, game.player.id)
    assert not afraid(game.world, strong, game.player.id)


def test_a_town_that_has_heard_nothing_knows_nothing(game):
    assert reputation(game.world, game.place.id, game.player.id) == Reputation(0.0, "unknown", "hard to read", None)


def test_killing_bandits_makes_a_righteous_name(game):
    for name in ("Ma Bo", "Ma Da", "Ma San"):
        bandit = person(game, name, occupation="bandit")
        deed(game, game.player.id, "killed", bandit, form="fist")
    rep = reputation(game.world, game.place.id, game.player.id)
    assert rep.word == "renowned" and rep.path == "righteous"
    adjective, noun, of, place = rep.epithet.split(" ", 3)
    assert adjective in RIGHTEOUS and noun == "Fist" and of == "of" and place == game.place.name
    assert reputation(game.world, game.place.id, game.player.id) == rep


def test_killing_townsfolk_makes_a_ruthless_name(game):
    for name in ("Wang Li", "Hu Mei", "Old Wu"):
        deed(game, game.player.id, "killed", person(game, name), form="palm")
    rep = reputation(game.world, game.place.id, game.player.id)
    assert rep.path == "ruthless" and rep.epithet.split(" ")[0] in RUTHLESS and rep.epithet.split(" ")[1] == "Palm"


def test_masked_deeds_count_for_the_persona_until_the_town_knows(game):
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    deed(game, persona, "killed", person(game, "Ma Bo", occupation="bandit"), masked=True)
    assert reputation(game.world, game.place.id, persona).renown > 0
    assert reputation(game.world, game.place.id, game.player.id).renown == 0
    deed(game, persona, "is", game.player.id)
    assert reputation(game.world, game.place.id, game.player.id).renown > 0
