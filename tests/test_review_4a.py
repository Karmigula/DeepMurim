"""Findings from the phase 4a final review."""

import random

import pytest

import systems.agendas as agendas
import systems.encounters as encounters
import systems.lives as lives
import systems.world_clock as clock
from debug.invariants import check_world
from engine.actions import Action
from engine.game import Game
from engine.world_mixin import CHILD_BARRED
from systems import duties, founding, halls
from systems import factions as F
from systems.creation import CreationChoice
from systems.kin import avengers_for, ensure_kin
from world.events import Event, commit
from world.gen.materialize import ensure_town


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


def local(game, path, town=None, **data):
    return founding.make_person(game.world, path, town or game.place.id, **data)


def test_a_natural_death_conjures_no_new_relatives(game):
    pid = local(game, "test:loner", occupation="scholar", age=80)
    before = len(game.world.entities("person"))
    commit(game.world, [Event("died", (pid, pid), game.place.id, {"cause": "age", "world": True})])
    assert len(game.world.entities("person")) == before


def test_conjured_relatives_bring_no_relatives_of_their_own(game):
    pid = local(game, "test:rooted", occupation="scholar", age=40)
    relatives = ensure_kin(game.world, pid)
    assert relatives and all(game.world.entity(k).data.get("kin_ready") for k, _ in relatives)


def test_a_child_neither_hunts_the_player_nor_feuds(game):
    world, me = game.world, game.player.id
    father = local(game, "test:father", occupation="hunter", age=30, kin_ready=True)
    child = local(game, "test:son", occupation="child", age=2, kin_ready=True)
    world.relate(father, child, "kin_of", data={"role": "child"})
    world.relate(child, father, "kin_of", data={"role": "parent"})
    commit(world, [Event("died", (me, father), game.place.id, {"cause": "killed"})])
    assert child not in avengers_for(world, me)
    villain = local(game, "test:villain", occupation="wandering swordsman", age=40)
    mother = local(game, "test:mother", occupation="herbalist", age=30, kin_ready=True)
    world.relate(mother, child, "kin_of", data={"role": "child"})
    world.relate(child, mother, "kin_of", data={"role": "parent"})
    commit(world, [Event("died", (villain, mother), game.place.id, {"cause": "feud", "world": True})])
    assert agendas.grudge(world, child, lives.current_season(world) + 1) is None


def test_children_are_never_debtors_and_cannot_be_dunned(game):
    town = ensure_town(game.world, 9, 9, 0)
    child = local(game, "test:debtor", town=town, occupation="child", age=7)
    game.world.update_data(town, factions_ready=True, halls=[], seats=[])
    assert duties._resident(game.world, random.Random(1), town, set()) is None
    assert game.world.entity(child).data["age"] == 7
    assert "demand" in CHILD_BARRED


def test_a_destroyed_faction_releases_the_player_and_closes_their_duty(game, monkeypatch):
    world, me = game.world, game.player.id
    minor = next(f.id for f in world.entities("faction") if f.data.get("tier") == "minor" and f.data.get("seat")) \
        if any(f.data.get("tier") == "minor" for f in world.entities("faction")) else None
    if minor is None:
        from world.gen.materialize import ensure_region
        for x in range(-3, 4):
            F.minor_factions(world, world.entity(ensure_region(world, x, 0)))
        minor = next(f.id for f in world.entities("faction") if f.data.get("tier") == "minor")
    town = world.entity(minor).data["seat"]
    halls.settle_town(world, town)
    world.relate(me, minor, "member_of", 0, {"role": "member", "hall": None, "merit": 0, "status": "member", "secret": False})
    commit(world, duties.issue_events(world, me, minor, halls.keeper_at(world, minor, town), town))
    assert duties.open_duty(world, me) is not None
    monkeypatch.setattr(clock, "DESTROY_BELOW", 101)
    clock.world_tick(world)
    world.set_time(world.time + lives.SEASON)
    clock.run_due(world)
    assert world.entity(minor).data["dissolved"]
    assert F.membership(world, me, minor)[1]["status"] == "released"
    assert duties.open_duty(world, me) is None
    assert not [p for p in check_world(world) if "duty" in p]


def test_a_faction_nobody_has_visited_keeps_its_strength(game):
    cult = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "demonic_cult")
    start = game.world.entity(cult).data["power"]
    clock.world_tick(game.world)
    game.world.update_data(cult, power=max(0, start - 40))
    game.world.set_time(game.world.time + 8 * lives.SEASON)
    clock.run_due(game.world)
    assert game.world.entity(cult).data["power"] > start - 40


def test_people_made_offstage_age_from_the_day_they_appear(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    pid = local(game, "test:anchor", occupation="scholar", age=40)
    kin = [k for k, _ in ensure_kin(game.world, pid)]
    ages = {k: game.world.entity(k).data["age"] for k in kin}
    game.world.set_time(game.world.time + 4 * lives.SEASON)
    for k in kin:
        lives.catch_up(game.world, k)
        assert game.world.entity(k).data["age"] == ages[k] + 1


def test_an_old_save_ages_everyone_from_the_moment_it_loads(tmp_path, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    path = tmp_path / "old.world"
    old = Game.new(path, "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    old.start()
    far = ensure_town(old.world, 3, 3, 0)
    pid = local(old, "test:faraway", town=far, occupation="scholar", age=50)
    old.world._conn.execute("update entities set data = json_remove(data, '$.lived_to')")
    old.world.set_meta("world_tick", None)
    old.close()
    game = Game.load(path)
    game.start()
    game.world.set_time(game.world.time + 4 * lives.SEASON)
    lives.catch_up(game.world, pid)
    assert game.world.entity(pid).data["age"] == 51.0
    game.close()


def test_children_are_barred_from_every_fight_verb():
    assert {"challenge", "spar", "ask_follow", "sect_invite", "demand"} <= CHILD_BARRED
    assert Action("demand", 1).verb in CHILD_BARRED
