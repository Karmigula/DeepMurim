import pytest

import systems.agendas as agendas
import systems.bonds as bonds
import systems.encounters as encounters
import systems.lives as lives
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.kin import kin_of
from world.events import Event, commit


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
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


@pytest.fixture
def fond(monkeypatch):
    monkeypatch.setattr(bonds, "warmth", lambda world, npc, player: 1.0)


def local(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **{"occupation": "herbalist", **data})


def verbs(turn):
    return {c.action.verb for c in turn.all_choices}


def test_a_warm_friend_can_be_married(game, fond):
    npc = local(game, "test:love", age=25)
    assert "propose" in verbs(game.perform(Action("talk", npc)))
    game.perform(Action("propose", npc))
    assert agendas.spouse_of(game.world, game.player.id) == npc
    assert agendas.spouse_of(game.world, npc) == game.player.id
    assert game.world.facts(predicate="married", subject=game.player.id)


def test_a_refusal_stands_for_the_season(game, monkeypatch, fond):
    monkeypatch.setattr(bonds, "accept_chance", lambda score: 0.0)
    npc = local(game, "test:cold", age=25)
    game.perform(Action("talk", npc))
    game.perform(Action("propose", npc))
    assert agendas.spouse_of(game.world, game.player.id) is None
    assert bonds.propose_block(game.world, game.player.id, npc) == "They gave you their answer this season."


def test_the_player_can_have_children(game, monkeypatch, fond):
    monkeypatch.setattr(agendas, "BIRTH_CHANCE", 1.0)
    npc = local(game, "test:wife", age=28)
    game.perform(Action("talk", npc))
    game.perform(Action("propose", npc))
    lives.lived_to(game.world, npc)
    game.world.set_time(game.world.time + lives.SEASON)
    lives.catch_up(game.world, npc)
    [child] = agendas.children_of(game.world, game.player.id)
    assert agendas.children_of(game.world, npc) == [child]


def test_disciples_and_sworn_siblings(game, fond):
    youth, friend = local(game, "test:youth", age=16), local(game, "test:friend", age=30, gender="woman")
    game.perform(Action("talk", youth))
    game.perform(Action("take_disciple", youth))
    game.perform(Action("talk", friend))
    turn = game.perform(Action("swear", friend))
    assert (youth, "disciple") in kin_of(game.world, game.player.id)
    assert (friend, "sworn_sibling") in kin_of(game.world, game.player.id)
    assert (game.player.id, "sworn_sibling") in kin_of(game.world, friend)
    assert bonds.relation_word(game.world, friend, "sibling") == "your sworn sister"
    assert turn is not None


def test_heirs_come_in_order(game, fond):
    me = game.player.id
    elder, younger, small = local(game, "test:c1", age=30), local(game, "test:c2", age=20), local(game, "test:c3", age=9)
    for child in (elder, younger, small):
        agendas._pair(game.world, me, child, "child")
    pupil, sister = local(game, "test:pupil", age=17), local(game, "test:sister", age=40)
    agendas._pair(game.world, me, pupil, "disciple")
    agendas._pair(game.world, me, sister, "sworn_sibling")
    follower = local(game, "test:follower", age=35, sworn_to=me)
    assert bonds.candidates(game.world, me) == [(elder, "child"), (younger, "child"), (pupil, "disciple"),
                                                (sister, "sibling"), (follower, "follower")]
    game.perform(Action("talk", sister))
    game.perform(Action("name_heir", sister))
    assert bonds.candidates(game.world, me)[0] == (sister, "named")


def test_a_dead_named_heir_is_forgotten(game, fond):
    me = game.player.id
    heir, other = local(game, "test:heir", age=30), local(game, "test:other", age=20)
    agendas._pair(game.world, me, heir, "child")
    agendas._pair(game.world, me, other, "child")
    game.perform(Action("talk", heir))
    game.perform(Action("name_heir", heir))
    commit(game.world, [Event("died", (heir, heir), game.place.id, {"cause": "age", "world": True})])
    game.perform(Action("farewell"))
    game.perform(Action("meditate", 1))
    assert game.player.data.get("named_heir") is None
    assert bonds.candidates(game.world, me)[0] == (other, "child")
