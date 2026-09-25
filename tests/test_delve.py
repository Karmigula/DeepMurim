import pytest

import systems.delve as D
import systems.encounters as encounters
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_realms
from engine.actions import Action
from engine.game import Game
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
    monkeypatch.setattr(G, "near_sects", lambda world, gate: [])  # an empty realm: no rival bands (Task 5 has those)
    monkeypatch.setattr(G, "WANDERER_CHANCE", 0.0)


def room(kind, **contents):
    return {"kind": kind, "state": "untouched", "contents": contents}


def open_realm(game, rule=("open", None), floors=None):
    """The first ancient realm with its gate in the player's town, standing open now."""
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    changes = {"gate": town, "rule": {"kind": rule[0], "value": rule[1]}}
    if floors is not None:
        changes["floors"] = floors
    world.update_data(realm, **changes)
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    sky.observe(world, town)
    return realm, occurrence


def actions(turn):
    return [c.action for c in turn.all_choices]


def texts(turn):
    return [t for t, _ in turn.lines]


def test_you_enter_at_the_gate_while_it_stands_open(game):
    world, me = game.world, game.player.id
    realm, occurrence = open_realm(game)
    assert Action("enter_realm", realm) in actions(game.perform(Action("look")))
    turn = game.perform(Action("enter_realm", realm))
    assert world.targets(me, "located_in") == [realm] and D.position(world, me) == {"realm": realm, "floor": 1, "chamber": 0}
    assert me in world.entity(occurrence).data["data"]["entered"]
    header = texts(game.perform(Action("look")))[0]
    assert world.entity(realm).name.lower() in header.lower() and "floor 1 of" in header and "the gate closes in" in header
    assert check_realms(world) == []


def test_the_gate_explains_what_its_rule_refuses(game):
    world, me = game.world, game.player.id
    realm, _ = open_realm(game, ("token", None))
    turn = game.perform(Action("enter_realm", realm))
    assert any("jade token" in t for t in texts(turn)) and world.targets(me, "located_in") != [realm]


def test_a_token_is_spent_to_enter(game):
    world, me = game.world, game.player.id
    realm, _ = open_realm(game, ("token", None))
    token = world.add_entity("treasure", "a jade token", {"kind": "token", "realm": realm, "used": False, "value": 120})
    world.relate(me, token, "owns")
    game.perform(Action("enter_realm", realm))
    assert world.targets(me, "located_in") == [realm]
    assert world.entity(token).data["used"] and not world.sources(token, "owns")


def test_a_token_can_be_bought_from_its_holder(game):
    from systems import founding
    from systems.purse import silver_of
    world, me, town = game.world, game.player.id, game.place.id
    realm, _ = open_realm(game, ("token", None))
    holder = founding.make_person(world, "test:holder", town, occupation="wandering swordsman", age=30)
    token = world.add_entity("treasure", "a jade token", {"kind": "token", "realm": realm, "used": False, "value": 120})
    world.relate(holder, token, "owns")
    world.update_data(me, silver=500)
    turn = game.perform(Action("talk", holder))
    assert Action("buy_token", holder) in actions(turn)
    game.perform(Action("buy_token", holder))
    assert world.sources(token, "owns") == [me] and silver_of(world, me) == 500 - D.TOKEN_PRICE * 120
    game.perform(Action("farewell"))
    game.perform(Action("enter_realm", realm))
    assert world.targets(me, "located_in") == [realm]


def test_a_quota_realm_lets_the_unsponsored_try_to_slip_in(game, monkeypatch):
    world, me = game.world, game.player.id
    realm, _ = open_realm(game, ("quota", None))
    monkeypatch.setattr("systems.tournaments.sponsor_of", lambda world, player: None)
    assert Action("sneak_realm", realm) in actions(game.perform(Action("look")))
    monkeypatch.setattr(D, "SNEAK_BOUNDS", (0.0, 0.0))
    game.perform(Action("sneak_realm", realm))
    assert world.targets(me, "located_in") != [realm]
    assert [f for f in world.facts(predicate="trespassed") if f.subject == me]
    monkeypatch.setattr(D, "SNEAK_BOUNDS", (1.0, 1.0))
    game.perform(Action("sneak_realm", realm))
    assert world.targets(me, "located_in") == [realm]


def test_moving_on_costs_time_and_a_guardian_bars_the_way(game):
    world, me = game.world, game.player.id
    floors = [[room("treasure", prize={"kind": "herb", "name": "a blood lotus", "value": 300}),
               room("guardian", species="stone lion", realm=2, guardian=None), room("stair")],
              [room("inheritance")]]
    realm, _ = open_realm(game, floors=floors)
    game.perform(Action("enter_realm", realm))
    before = world.time
    turn = game.perform(Action("take_treasure"))
    herb = [i for i in world.targets(me, "owns") if world.entity(i).name == "a blood lotus"]
    assert herb and world.time == before + D.STEP and world.entity(realm).data["floors"][0][0]["state"] == "looted"
    game.perform(Action("delve_on"))
    assert D.position(world, me)["chamber"] == 1
    found = actions(game.perform(Action("look")))
    assert Action("delve_on") not in found and Action("delve_back") in found  # the lion bars the way on


def test_stairs_lead_down_and_up_and_you_leave_only_from_the_first_floor(game):
    world, me, town = game.world, game.player.id, game.place.id
    realm, _ = open_realm(game, floors=[[room("stair")], [room("trial", trial="formation"), room("stair")],
                                        [room("inheritance")]])
    game.perform(Action("enter_realm", realm))
    assert Action("leave_realm") in actions(game.perform(Action("look")))
    game.perform(Action("delve_on"))  # the stair down
    assert D.position(world, me) == {"realm": realm, "floor": 2, "chamber": 0}
    assert Action("leave_realm") not in actions(game.perform(Action("look")))
    game.perform(Action("delve_back"))  # back up to the stair on floor 1
    assert D.position(world, me) == {"realm": realm, "floor": 1, "chamber": 0}
    game.perform(Action("leave_realm"))
    assert world.targets(me, "located_in") == [town] and D.position(world, me) is None
    assert [f for f in world.facts(predicate="delved") if f.subject == me]


def test_inside_only_the_delve_and_its_pages_answer(game):
    world = game.world
    realm, _ = open_realm(game)
    game.perform(Action("enter_realm", realm))
    turn = game.perform(Action("market"))
    assert any("inside" in t for t in texts(turn))
    assert any("Last Disciple" not in t for t in texts(game.perform(Action("journal"))))


def test_the_rules_check_your_delve_position(game):
    world, me = game.world, game.player.id
    realm, _ = open_realm(game)
    game.perform(Action("enter_realm", realm))
    world.update_data(me, delve={"realm": realm, "floor": 9, "chamber": 0})
    assert any("delve" in p for p in check_realms(world))
