import pytest

import systems.agendas as agendas
import systems.encounters as encounters
import systems.lineage as lineage
import systems.lives as lives
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls, law
from systems.attitude import attitude
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.kin import avengers_for
from systems.reputation import reputation
from systems.standing import _towns, standing
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
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


def local(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **{"occupation": "herbalist", "age": 30, **data})


def deed(game, predicate, target, weight=3.0):
    me, town = game.player.id, game.place.id
    return record_fact(game.world, me, predicate, target, place=town, weight=weight,
                       variant=make_variant(predicate, me, target, place=game.world.entity(town).name))


def succeed(game, monkeypatch, heir):
    """Die of age and carry on as `heir`, a child of the player."""
    agendas._pair(game.world, game.player.id, heir, "child")
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    game.perform(Action("meditate", 90))
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    old = game.player.id
    game.perform(Action("succeed", heir))
    return old


def test_the_town_knows_the_heir_by_the_old_name(game, monkeypatch):
    town = game.place.id
    for i in range(4):
        deed(game, "defeated", local(game, f"test:beaten:{i}"))
    son = local(game, "test:son", age=20)
    old = succeed(game, monkeypatch, son)
    theirs, mine = reputation(game.world, town, old), reputation(game.world, town, son)
    assert mine.renown >= 0.5 * theirs.renown > 0
    assert lineage.inherited(game.world, town, son) == [(old, 0.5)]


def test_a_name_unheard_of_carries_nothing(game, monkeypatch):
    son = local(game, "test:son", age=20)
    old = succeed(game, monkeypatch, son)
    far = F.ensure_roster(game.world)[0]
    assert lineage.inherited(game.world, game.world.entity(far).data["seat"] or 999999, son) == []
    assert lineage.predecessor(game.world, son) == old


def test_old_gratitude_warms_to_the_heir(game, monkeypatch):
    friend = local(game, "test:friend")
    moment = game.world.chronicle_about(game.player.id, limit=1)[0].id
    game.world.add_memory(friend, moment, "grateful", 1.0, True)
    son = local(game, "test:son", age=20)
    cold = attitude(game.world, friend, son).score
    succeed(game, monkeypatch, son)
    assert attitude(game.world, friend, son).score > cold


def test_a_faction_judges_the_heir_by_the_founder(game, monkeypatch):
    world, me = game.world, game.player.id
    faction = next(f for f in F.ensure_roster(world) if world.entity(f).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, faction)
    spared = founding.make_person(world, "test:spared", seat, occupation="hunter", age=30)
    record_fact(world, me, "spared", spared, place=seat, weight=3.0,  # a mercy the righteous heard of
                variant=make_variant("spared", me, spared, place=world.entity(seat).name))
    son = local(game, "test:son", age=20)
    old = succeed(game, monkeypatch, son)
    fact = game.world.facts(predicate="heir_of", subject=son)[0]
    for town in _towns(game.world, faction):
        believe(game.world, town, fact.id, fact.variant, None, 1.0, 0, "test")
    theirs = standing(game.world, faction, old).score
    assert theirs > 0 and standing(game.world, faction, son).score == pytest.approx(0.5 * theirs, abs=0.002)


def test_avengers_turn_on_the_heir(game, monkeypatch):
    monkeypatch.setattr(lineage, "GRUDGE_SHARE", 1.0)
    victim = local(game, "test:victim", kin_ready=True)
    brother = local(game, "test:brother", kin_ready=True)
    game.world.relate(victim, brother, "kin_of", data={"role": "sibling"})
    game.world.relate(brother, victim, "kin_of", data={"role": "sibling"})
    commit(game.world, [Event("died", (game.player.id, victim), game.place.id, {"cause": "killed"})])
    son = local(game, "test:son", age=20)
    old = succeed(game, monkeypatch, son)
    assert brother in avengers_for(game.world, old)
    assert brother in avengers_for(game.world, son)


def test_the_heir_answers_for_half_the_debts(game, monkeypatch):
    town = game.place.id
    for i in range(3):
        deed(game, "killed", local(game, f"test:slain:{i}"))
    son = local(game, "test:son", age=20)
    old = succeed(game, monkeypatch, son)
    theirs = law.bounty(game.world, town, old)
    assert theirs > 0 and law.bounty(game.world, town, son) == round(0.5 * theirs)
