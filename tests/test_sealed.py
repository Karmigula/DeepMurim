import pytest

import systems.delve as D
import systems.encounters as encounters
import systems.realm_gates as G
import systems.sealed as S
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_lineage, check_realms
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.bodies import load_body
from systems.creation import CreationChoice
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(G, "WANDERER_CHANCE", 0.0)
    monkeypatch.setattr(G, "near_sects", lambda world, gate: [])


def room(kind, **contents):
    return {"kind": kind, "state": "untouched", "contents": contents}


def opening(game, realm):
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    game.perform(Action("look"))
    return occurrence


def sealed_in(game, period=12, bands=()):
    """Enter a realm at the player's town (with these bands chosen at the gate), and stay until the gate closes."""
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": "open", "value": None}, period=period,
                      floors=[[room("trial", trial="formation"), room("stair")], [room("inheritance")]])
    data = {**SR.opening_data(realm), "delvers": list(bands), "teams": [{"faction": None, "members": [b]} for b in bands]}
    commit(world, sky.start_events(world, "realm_opening", town, world.time, data))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    game.perform(Action("look"))
    game.perform(Action("enter_realm", realm))
    world.set_time(world.entity(occurrence).data["active"][1] + 1)
    game.perform(Action("look"))
    return realm, occurrence


def actions(turn):
    return [c.action for c in turn.all_choices]


def test_the_gate_closes_on_you_and_on_the_band_beside_you(game, monkeypatch):
    import systems.delvers as R
    monkeypatch.setattr(R, "step_events", lambda world, player: [])  # the band stays where it was put
    world, me, town = game.world, game.player.id, game.place.id
    rival = founding.make_person(world, "test:rival", town, occupation="wandering swordsman", age=25, realm="third-rate")
    realm, occurrence = sealed_in(game, bands=[rival])
    assert S.sealed_realm(world, me) == realm and me in world.entity(realm).data["sealed"]
    assert rival in world.entity(realm).data["sealed"] and world.entity(rival).data["sealed_in"]
    closed = [e for e in world.chronicle_of_kind("realm_closed") if e.data["occurrence"] == occurrence]
    assert closed and closed[0].data["fates"][str(me)] == "sealed"
    assert check_realms(world) == []


def test_a_sealed_season_cultivates_three_times_over(game):
    world, me = game.world, game.player.id
    realm, _ = sealed_in(game)
    assert Action("sealed_cultivate") in actions(game.perform(Action("look")))
    energy, when = load_body(world, me).energy_years, world.time
    game.perform(Action("sealed_cultivate"))
    assert world.time == when + W.SEASON and load_body(world, me).energy_years > energy


def test_the_sealed_walk_on_when_the_realm_opens_again(game):
    world, me = game.world, game.player.id
    realm, _ = sealed_in(game)
    world.set_time(world.time + 4 * W.SEASON)
    again = opening(game, realm)
    assert S.sealed_realm(world, me) is None and me in world.entity(again).data["data"]["entered"]
    assert D.position(world, me) is not None and me not in world.entity(realm).data["sealed"]
    assert check_realms(world) == []


def test_a_search_may_find_another_way_out(game, monkeypatch):
    monkeypatch.setattr(S, "SEARCH_BOUNDS", (1.0, 1.0))
    world, me, town = game.world, game.player.id, game.place.id
    realm, _ = sealed_in(game)
    game.perform(Action("search_exit"))
    assert world.targets(me, "located_in") == [town] and S.sealed_realm(world, me) is None
    assert D.position(world, me) is None and me not in world.entity(realm).data["sealed"]


def test_letting_your_heir_carry_on_ends_your_tale(game):
    from systems.agendas import _pair
    world, me, town = game.world, game.player.id, game.place.id
    pupil = founding.make_person(world, "test:pupil", town, occupation="apprentice", age=18)
    _pair(world, me, pupil, "disciple")
    realm, _ = sealed_in(game)
    game.perform(Action("heir_carry_on"))
    assert world.entity(me).data.get("dying", {}).get("cause") == "sealed"
    game.perform(Action("succeed", pupil))
    assert world.get_meta("player_id") == pupil and world.entity(me).data["dead"]
    assert world.targets(me, "buried_at") == [realm] and check_lineage(world) == []


def test_the_gate_closes_between_two_steps_and_no_one_walks_out(game):
    world, me, town = game.world, game.player.id, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": "open", "value": None}, period=12,
                      floors=[[room("trial", trial="formation"), room("stair")], [room("inheritance")]])
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    game.perform(Action("look"))
    game.perform(Action("enter_realm", realm))
    world.set_time(world.entity(occurrence).data["active"][1] - 1)  # a watch before the gate closes
    game.perform(Action("delve_rest"))
    assert S.sealed_realm(world, me) == realm and check_realms(world) == []
    assert Action("leave_realm") not in actions(game.perform(Action("look")))


def test_a_one_off_realm_keeps_its_sealed(game):
    world, me = game.world, game.player.id
    realm, _ = sealed_in(game, period=None)
    found = actions(game.perform(Action("look")))
    assert Action("sealed_cultivate") not in found
    assert Action("search_exit") in found and Action("heir_carry_on") in found
