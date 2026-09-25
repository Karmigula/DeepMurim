"""Phase 4f final review: the Critical and Important findings, each pinned by a test."""

import pytest

import systems.delve as D
import systems.encounters as encounters
import systems.lives as lives
import systems.realm_gates as G
import systems.sealed as S
import systems.secret_realms as SR
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from debug.invariants import check_realms
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.bodies import load_body, save_body
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


def inside(game, bands=()):
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": "open", "value": None}, period=12,
                      floors=[[room("trial", trial="formation"), room("stair")], [room("inheritance")]])
    data = {**SR.opening_data(realm), "delvers": list(bands), "teams": [{"faction": None, "members": [b]} for b in bands]}
    commit(world, sky.start_events(world, "realm_opening", town, world.time, data))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    game.perform(Action("look"))
    game.perform(Action("enter_realm", realm))
    return realm, occurrence


def test_a_typed_leave_cannot_walk_out_of_a_sealing(game):
    world, me = game.world, game.player.id
    realm, occurrence = inside(game)
    world.set_time(world.entity(occurrence).data["active"][1] + 1)
    game.perform(Action("look"))
    assert S.sealed_realm(world, me) == realm
    game.perform(Action("leave_realm"))
    game.perform(Action("delve_on"))
    assert world.targets(me, "located_in") == [realm] and S.sealed_realm(world, me) == realm
    assert D.position(world, me)["chamber"] == 0 and check_realms(world) == []


def test_a_typed_leave_cannot_pass_a_gate_the_clock_has_shut(game):
    world, me = game.world, game.player.id
    realm, occurrence = inside(game)
    world.set_time(world.entity(occurrence).data["active"][1] + 1)  # shut, not yet seen by anyone
    assert D.leave_events(world, me) == []


def test_bands_left_behind_when_you_leave_early_meet_their_own_fates(game, monkeypatch):
    import systems.delvers as R
    monkeypatch.setattr(R, "step_events", lambda world, player: [])
    monkeypatch.setattr(G, "OUT_BASE", 1.0)
    world, me, town = game.world, game.player.id, game.place.id
    bands = [founding.make_person(world, f"test:band:{i}", town, occupation="wandering swordsman", age=25,
                                  realm="third-rate") for i in range(3)]
    realm, occurrence = inside(game, bands)
    game.perform(Action("leave_realm"))
    world.set_time(world.entity(occurrence).data["active"][1] + 1)
    game.perform(Action("look"))
    assert world.entity(realm).data["sealed"] == []
    assert all(world.targets(p, "located_in") == [town] for p in bands)


def test_realm_spirits_are_off_the_life_clock(game):
    import systems.chambers as C
    world, me = game.world, game.player.id
    realm, _ = inside(game)
    spirit = C.mirror(world, realm, 1, 0, me)
    assert not lives.simulated(world.entity(spirit))


def test_the_sealed_are_not_invited_to_tournaments(game, monkeypatch):
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    star = founding.make_person(world, "test:star", town, occupation="wandering swordsman", age=25, realm="first-rate")
    G.seal(world, star, realm)
    import systems.rankings as R
    monkeypatch.setattr(R, "latest", lambda world, knower: {"lists": {"heaven": [star]}, "year": 1, "time": 0})
    import systems.events.grand_assembly as ga
    commit(world, sky.start_events(world, "grand_assembly", town, world.time, ga.start_data(world, town, 10, __import__("world.seed", fromlist=["rng_for"]).rng_for(1, "a"))))
    occurrence = world.entity(W.index(world)[-1][W.ID])
    assert star not in T.pool(world, occurrence, lambda p: True, 32, None)


def test_the_sealed_may_break_through(game):
    from systems.realms import REALMS
    world, me = game.world, game.player.id
    realm, occurrence = inside(game)
    world.set_time(world.entity(occurrence).data["active"][1] + 1)
    game.perform(Action("look"))
    body = load_body(world, me)
    body.energy_years, body.bottleneck = REALMS[1].threshold, True
    save_body(world, me, body)
    turn = game.perform(Action("look"))
    assert Action("breakthrough") in [c.action for c in turn.all_choices]
    turn = game.perform(Action("breakthrough"))
    assert not any("must wait until you are out" in t for t, _ in turn.lines)
