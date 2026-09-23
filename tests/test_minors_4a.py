"""The deferred minors from the phase 4a final review."""

import pytest

import systems.agendas as agendas
import systems.encounters as encounters
import systems.lives as lives
import systems.rumours as rumours
import systems.wars as wars
import systems.world_clock as clock
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls
from systems.bodies import load_body
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import ensure_town


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


def local(game, path, town=None, **data):
    return founding.make_person(game.world, path, town or game.place.id, **data)


def test_a_death_heard_as_a_rumour_reaches_the_journal(game):
    world, me, town = game.world, game.player.id, game.place.id
    friend = local(game, "test:friend", occupation="tea seller", age=40)
    game.perform(Action("talk", friend))
    game.perform(Action("farewell"))
    teller = local(game, "test:teller", occupation="innkeeper", age=40)
    commit(world, [Event("died", (friend, friend), town, {"cause": "age", "world": True})])
    belief, fact = next((b, f) for b, f in world.known_facts(town) if f.predicate == "died" and f.subject == friend)
    game._commit(rumours.heard_events(world, me, teller, town, belief, fact))
    journal = [t for t, _ in game.perform(Action("journal")).lines]
    assert any(t.endswith(f"Heard: {world.entity(friend).name} died.") for t in journal)


def test_a_birth_catches_up_the_spouse_first(game, monkeypatch):
    monkeypatch.setattr(agendas, "BIRTH_CHANCE", 1.0)
    town = ensure_town(game.world, 9, 9, 0)
    a = local(game, "test:ma", town=town, occupation="innkeeper", age=28)
    b = local(game, "test:pa", town=town, occupation="blacksmith", age=30)
    commit(game.world, [Event("married", (a, b), town, {"season": lives.current_season(game.world)})])
    game.world.set_time(game.world.time + 4 * lives.SEASON)
    lives.catch_up(game.world, a, until=lives.lived_to(game.world, a) + 1)
    assert game.world.entity(b).data["lived_to"] >= game.world.entity(a).data["lived_to"]


def test_the_staff_of_a_lost_hall_are_let_go_where_they_stand(game, monkeypatch):
    for name, value in (("CLASH_CHANCE", 1.0), ("WAR_CHANCE", 1.0), ("KILL_CHANCE", 0.0), ("HALL_LOSS", 1.0)):
        monkeypatch.setattr(wars, name, value)
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    cult = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "demonic_cult")
    town = halls.seat_of(world, sect)
    halls.seat_of(world, cult)
    world.update_data(town, halls=[*halls.halls_here(world, town), cult])
    world.update_data(cult, branches=[*world.entity(cult).data["branches"], town], power=0)
    world.update_data(sect, power=100)
    halls._hire(world, world.entity(cult), town, halls.BRANCH_STAFF)
    branch = halls.staff_at(world, cult, town)
    clock.world_tick(world)
    world.set_time(world.time + lives.SEASON)
    clock.run_due(world)
    assert cult not in halls.halls_here(world, town)
    for person in branch:
        assert F.membership(world, person, cult)[1]["status"] == "released"
        assert world.targets(person, "located_in") == [town]


def test_feud_wounds_date_from_the_season_they_were_taken(game, monkeypatch):
    monkeypatch.setattr(agendas, "REVENGE_CHANCE", 1.0)
    monkeypatch.setattr(agendas, "FEUD_DEATH", 0.0)
    town = ensure_town(game.world, 9, 9, 0)
    killer = local(game, "test:k", town=town, occupation="wandering swordsman", age=40)
    victim = local(game, "test:v", town=town, occupation="hunter", age=35, kin_ready=True)
    sister = local(game, "test:s", town=town, occupation="herbalist", age=33, kin_ready=True)
    game.world.relate(victim, sister, "kin_of", data={"role": "sibling"})
    game.world.relate(sister, victim, "kin_of", data={"role": "sibling"})
    commit(game.world, [Event("died", (killer, victim), town, {"cause": "test", "world": True})])
    start = lives.lived_to(game.world, sister)
    game.world.set_time(game.world.time + 8 * lives.SEASON)
    lives.catch_up(game.world, sister, until=start + 1)
    wounds = [i for p in (killer, sister) for i in load_body(game.world, p).injuries if i.cause == "a feud"]
    assert wounds and all(i.since <= (start + 1) * lives.SEASON for i in wounds)
