import random

import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.succession_crisis as SC
import systems.testament as T
import systems.tournaments as tournaments
import systems.world_clock as clock
from debug.invariants import check_crises
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.realms import realm_index
from world.events import Event, commit
from world.gen.materialize import people_at


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
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)


def a_sect(game, kind="orthodox_sect"):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)
    seat = halls.seat_of(world, sect)
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, seat, "located_in")  # near: its crisis is played in full (spec 2.4)
    return sect, seat


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def kill(world, person, place, cause="age", killer=None):
    commit(world, [Event("died", (killer or person, person), place, {"cause": cause, "world": True})])


def a_season(game):
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)


def a_crisis(game):
    """A crisis at the orthodox sect: its chief disciple against a proud elder."""
    world = game.world
    sect, seat = a_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["proud"])
    world.update_data(elders[1], traits=["kind"])
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    a_season(game)
    return sect, seat, keeper, elders[0], SC.live(world, sect)


def test_a_leader_who_dies_at_the_seat_leaves_the_token_in_the_hall(game, monkeypatch):
    monkeypatch.setattr(SC, "doubt", lambda world, faction: None)
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    token = T.token_of(world, sect)
    assert world.entity(token).data == {"kind": "sect_token", "faction": sect, "used": False}
    assert T.lies_at(world, token) == seat and T.holder(world, token) is None
    a_season(game)
    [heir] = staff(world, sect, seat, "leader")
    assert T.holder(world, token) == heir and T.lies_at(world, token) is None  # the new leader takes it up
    assert check_crises(world) == []


def test_a_killed_leaders_token_goes_with_the_killer(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    killer = staff(world, sect, seat, "disciple")[0]
    kill(world, leader, seat, cause="killed", killer=killer)
    assert T.holder(world, T.token_of(world, sect)) == killer
    assert SC.doubt(world, sect) == "violence"


def test_a_leader_who_dies_away_leaves_the_token_where_they_fell(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    away = game.place.id if game.place.id != seat else next(t.id for t in world.entities("town") if t.id != seat)
    kill(world, leader, away)
    assert T.lies_at(world, T.token_of(world, sect)) == away
    assert SC.doubt(world, sect) == "token"


def test_a_natural_death_may_pass_the_leaders_strength_to_the_chief_disciple(game, monkeypatch):
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 1.0)
    world = game.world
    sect, seat = a_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    proud = staff(world, sect, seat, "elder")[0]
    world.update_data(proud, traits=["proud"])
    before = realm_index(world.entity(keeper).data["realm"])
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat, cause="illness")
    assert realm_index(world.entity(keeper).data["realm"]) == before + 1
    assert world.facts(predicate="transmitted", subject=leader)
    assert SC.doubt(world, sect) is None  # the elder no longer stands above the heir
    a_season(game)
    assert staff(world, sect, seat, "leader") == [keeper]


def test_the_chief_disciple_takes_up_a_token_left_at_the_seat_when_the_crisis_begins(game):
    world = game.world
    sect, seat, keeper, proud, occurrence = a_crisis(game)
    crisis = SC.crisis_of(occurrence)
    assert T.holder(world, crisis["token"]) == keeper
    assert "token" in C.proofs(world, crisis, SC.claimant(crisis, keeper))
    assert check_crises(world) == []


def test_a_read_will_speaks_for_whom_it_names(game, monkeypatch):
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 1.0, "other": 1.0})
    monkeypatch.setattr(T, "WILL_STATES", (("read", 1.0),))
    world = game.world
    sect, seat, keeper, proud, occurrence = a_crisis(game)
    crisis = SC.crisis_of(occurrence)
    assert crisis["will"] == {"state": "read", "names": keeper, "holder": None}
    assert "will" in C.proofs(world, crisis, SC.claimant(crisis, keeper))
    assert C.named(world, crisis) == keeper


def test_a_hidden_will_is_found_by_a_camp_and_kept_by_one_it_does_not_name(game, monkeypatch):
    world = game.world
    will = {"state": "hidden", "names": 7, "holder": None}
    assert T.found_by(will, 7) == {"state": "read", "names": 7, "holder": None}
    assert T.found_by(will, 8) == {"state": "held", "names": 7, "holder": 8}
    monkeypatch.setattr(T, "CAMP_FIND", 1.0)
    sect, seat, keeper, proud, occurrence = a_crisis(game)
    crisis = {**SC.crisis_of(occurrence), "will": {"state": "hidden", "names": keeper, "holder": None}}
    found = T.camps_search(world, crisis, random.Random(1))["will"]
    assert found["state"] in ("read", "held") and (found["state"] == "read") == (found.get("holder") is None)


def test_a_held_will_is_hidden_by_a_claimant_it_does_not_name(game, monkeypatch):
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 1.0, "other": 1.0})
    monkeypatch.setattr(T, "WILL_STATES", (("held", 1.0),))
    sect, seat, keeper, proud, occurrence = a_crisis(game)
    will = SC.crisis_of(occurrence)["will"]
    assert will["state"] == "held" and will["names"] == keeper and will["holder"] == proud


def test_the_grand_elder_comes_down_the_mountain(game, monkeypatch):
    monkeypatch.setattr(T, "EMERGE_CHANCE", 1.0)
    world = game.world
    sect, seat, keeper, proud, occurrence = a_crisis(game)
    crisis = SC.crisis_of(occurrence)
    elder = crisis["grand_elder"]
    entity = world.entity(elder)
    assert entity.data["secluded"] and entity.data["occupation"] == "grand elder"
    assert elder not in [p.id for p in people_at(world, seat)]  # in seclusion: in no town's scene
    assert tournaments._in_a_realm(world, elder)  # nor at any tournament
    backing, _ = C.camps(world, crisis)
    tally = C.votes(world, crisis, backing)
    if C.ambitious(world, elder):
        assert {"person": elder, "kind": "grand_elder"} in crisis["claimants"] and tally[elder] == 3
    else:
        backed = crisis["grand_elder_backs"]
        assert tally[backed] == len(backing[backed]) + 2
    assert T.ensure_grand_elder(world, sect, None) == elder  # one for the sect, made once
