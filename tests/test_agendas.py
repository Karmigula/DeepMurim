import math

import pytest

import systems.agendas as agendas
import systems.encounters as encounters
import systems.lives as lives
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.kin import kin_of
from world.events import Event, commit
from world.gen.materialize import ensure_town, region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


def empty_town(game):
    """A town nobody has visited, so no seeded residents stand in it."""
    return ensure_town(game.world, 9, 9, 0)


def someone(game, path, town, **data):
    pid = founding.make_person(game.world, path, town, **data)
    lives.lived_to(game.world, pid)
    return pid


def one_season(game, *people):
    game.world.set_time(game.world.time + lives.SEASON)
    for pid in people:
        lives.catch_up(game.world, pid)


def wed(game, a, b, town):
    commit(game.world, [Event("married", (a, b), town, {"season": lives.current_season(game.world)})])


def test_two_singles_marry(game, monkeypatch):
    monkeypatch.setattr(agendas, "MARRY_CHANCE", 1.0)
    town = empty_town(game)
    a = someone(game, "test:a", town, age=25, occupation="innkeeper")
    b = someone(game, "test:b", town, age=27, occupation="scholar")
    one_season(game, a)
    assert agendas.spouse_of(game.world, a) == b and agendas.spouse_of(game.world, b) == a
    assert game.world.facts(predicate="married", subject=a)


def test_with_no_one_to_marry_a_newcomer_moves_in(game, monkeypatch):
    monkeypatch.setattr(agendas, "MARRY_CHANCE", 1.0)
    town = empty_town(game)
    a = someone(game, "test:lonely", town, age=30, occupation="hunter")
    one_season(game, a)
    partner = agendas.spouse_of(game.world, a)
    assert partner is not None and game.world.targets(partner, "located_in") == [town]
    assert game.world.entity(partner).data["lived_to"] == lives.current_season(game.world)


def test_a_married_couple_has_one_child(game, monkeypatch):
    monkeypatch.setattr(agendas, "BIRTH_CHANCE", 1.0)
    town = empty_town(game)
    a = someone(game, "test:ma", town, age=28, occupation="innkeeper")
    b = someone(game, "test:pa", town, age=30, occupation="blacksmith")
    wed(game, a, b, town)
    one_season(game, a, b)
    [child] = agendas.children_of(game.world, a)
    assert agendas.children_of(game.world, b) == [child]
    data = game.world.entity(child).data
    assert data["age"] == 0 and data["occupation"] == "child" and data["kin_ready"]
    assert data["lived_to"] == lives.current_season(game.world)
    assert game.world.targets(child, "located_in") == [town]
    assert sorted(agendas.parents_of(game.world, child)) == sorted([a, b])


def test_a_second_child_is_a_sibling(game, monkeypatch):
    monkeypatch.setattr(agendas, "BIRTH_CHANCE", 1.0)
    town = empty_town(game)
    a = someone(game, "test:mb", town, age=28, occupation="innkeeper")
    b = someone(game, "test:pb", town, age=30, occupation="blacksmith")
    wed(game, a, b, town)
    one_season(game, a, b)
    one_season(game, a, b)
    first, second = agendas.children_of(game.world, a)
    assert (second, "sibling") in kin_of(game.world, first)


def test_a_full_town_has_no_more_births(game, monkeypatch):
    monkeypatch.setattr(agendas, "BIRTH_CHANCE", 1.0)
    town = empty_town(game)
    cap = math.ceil(agendas.POP_CAP * game.world.entity(town).data["npc_count"])
    a = someone(game, "test:mc", town, age=28, occupation="innkeeper")
    b = someone(game, "test:pc", town, age=30, occupation="blacksmith")
    for i in range(cap - 2):
        someone(game, f"test:crowd:{i}", town, age=40, occupation="scholar")
    wed(game, a, b, town)
    one_season(game, a, b)
    assert agendas.children_of(game.world, a) == []


def test_births_below_the_cap_record_the_population(game, monkeypatch):
    monkeypatch.setattr(agendas, "BIRTH_CHANCE", 1.0)
    town = empty_town(game)
    a = someone(game, "test:md", town, age=28, occupation="innkeeper")
    b = someone(game, "test:pd", town, age=30, occupation="blacksmith")
    wed(game, a, b, town)
    one_season(game, a, b)
    [fact] = game.world.facts(predicate="born")
    assert fact.data["population"] == 2


def test_people_move_to_a_nearby_town(game, monkeypatch):
    monkeypatch.setattr(agendas, "MOVE_CHANCE", 1.0)
    town = empty_town(game)
    region = region_of(game.world, town).data
    neighbour = ensure_town(game.world, region["x"] + 1, region["y"], 0)
    mover = someone(game, "test:mover", town, age=30, occupation="tea seller")
    one_season(game, mover)
    assert game.world.targets(mover, "located_in") == [neighbour]
    assert game.world.facts(predicate="moved", subject=mover)


def test_the_married_do_not_move_away_from_their_spouse(game, monkeypatch):
    monkeypatch.setattr(agendas, "MOVE_CHANCE", 1.0)
    town = empty_town(game)
    region = region_of(game.world, town).data
    ensure_town(game.world, region["x"] + 1, region["y"], 0)
    a = someone(game, "test:stay", town, age=30, occupation="tea seller")
    b = someone(game, "test:stay2", town, age=30, occupation="scholar")
    wed(game, a, b, town)
    one_season(game, a)
    assert game.world.targets(a, "located_in") == [town]


def test_a_killing_starts_a_vendetta_between_families(game, monkeypatch):
    monkeypatch.setattr(agendas, "REVENGE_CHANCE", 1.0)
    monkeypatch.setattr(agendas, "FEUD_DEATH", 0.0)
    town = empty_town(game)
    killer = someone(game, "test:killer", town, age=40, occupation="wandering swordsman", realm="third-rate")
    victim = someone(game, "test:victim", town, age=35, occupation="hunter")
    sister = someone(game, "test:sister", town, age=33, occupation="herbalist", kin_ready=True)
    game.world.relate(victim, sister, "kin_of", data={"role": "sibling"})
    game.world.relate(sister, victim, "kin_of", data={"role": "sibling"})
    game.world.update_data(victim, kin_ready=True)
    commit(game.world, [Event("died", (killer, victim), town, {"cause": "test", "world": True})])
    assert agendas.grudge(game.world, sister, lives.current_season(game.world) + 1)[0] == killer
    one_season(game, sister)
    feuds = [e for e in game.world.chronicle_about(sister, limit=10) if e.kind == "feud"]
    assert len(feuds) == 1 and feuds[0].actors == (sister, killer)
    assert game.world.facts(predicate="defeated")


def test_revenge_rests_for_four_seasons(game, monkeypatch):
    monkeypatch.setattr(agendas, "REVENGE_CHANCE", 1.0)
    monkeypatch.setattr(agendas, "FEUD_DEATH", 0.0)
    town = empty_town(game)
    killer = someone(game, "test:k2", town, age=40, occupation="wandering swordsman")
    victim = someone(game, "test:v2", town, age=35, occupation="hunter")
    brother = someone(game, "test:b2", town, age=33, occupation="herbalist", kin_ready=True)
    game.world.relate(victim, brother, "kin_of", data={"role": "sibling"})
    game.world.relate(brother, victim, "kin_of", data={"role": "sibling"})
    game.world.update_data(victim, kin_ready=True)
    commit(game.world, [Event("died", (killer, victim), town, {"cause": "test", "world": True})])
    counts = []
    for _ in range(5):
        one_season(game, brother)
        counts.append(len([e for e in game.world.chronicle_about(brother, limit=40) if e.kind == "feud"]))
    assert counts == [1, 1, 1, 1, 2]


def test_a_master_takes_an_apprentice(game, monkeypatch):
    monkeypatch.setattr(agendas, "APPRENTICE_CHANCE", 1.0)
    town = empty_town(game)
    master = someone(game, "test:master", town, age=50, occupation="wandering swordsman", realm="second-rate")
    youth = someone(game, "test:youth", town, age=14, occupation="child")
    someone(game, "test:grown", town, age=35, occupation="scholar")
    one_season(game, master)
    assert (youth, "disciple") in kin_of(game.world, master) and (master, "master") in kin_of(game.world, youth)
    assert game.world.facts(predicate="apprenticed", subject=master)
