import pytest

import systems.chambers as C
import systems.delve as D
import systems.encounters as encounters
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_realms
from engine.actions import Action
from engine.game import Game
from engine.lineage_page import lineage_lines
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import max_qi
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


def inside(game, *first_floor):
    """Enter a realm (gate in the player's town, open rule) whose first floor is these chambers, then a stair."""
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": "open", "value": None},
                      floors=[list(first_floor) + [room("stair")], [room("inheritance")]])
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    sky.observe(world, town)
    game.perform(Action("enter_realm", realm))
    return realm


def actions(turn):
    return [c.action for c in turn.all_choices]


def end_duel(game, result, verdict=None):
    """End the running duel with this result, the way the fight menu does after the last exchange."""
    import systems.duel as duel
    from world.seed import rng_for
    d = game.combat
    event = duel._end_event(game.world, d, result, "limit", rng_for(1, "end"), d.harm, 5, verdict)
    game._commit([event])
    return game._finish_duel(event.data)


def test_a_guardian_is_fought_and_stays_slain(game):
    world, me = game.world, game.player.id
    realm = inside(game, room("guardian", species="stone lion", realm=2, guardian=None))
    assert Action("fight_guardian") in actions(game.perform(Action("look")))
    game.perform(Action("fight_guardian"))
    lion = world.entity(realm).data["floors"][0][0]["contents"]["guardian"]
    assert game.combat is not None and game.combat.opponent == lion and world.entity(lion).data["realm_spirit"]
    end_duel(game, "won", "kill")
    assert world.entity(realm).data["floors"][0][0]["state"] == "slain"
    assert Action("delve_on") in actions(game.perform(Action("look")))


def test_slipping_past_a_guardian_or_facing_it(game, monkeypatch):
    world = game.world
    realm = inside(game, room("guardian", species="jade serpent", realm=2, guardian=None))
    monkeypatch.setattr(C, "SLIP_BOUNDS", (1.0, 1.0))
    game.perform(Action("slip_past"))
    assert world.entity(realm).data["floors"][0][0]["state"] == "passed" and game.combat is None
    world.update_data(realm, floors=[[room("guardian", species="jade serpent", realm=2, guardian=None), room("stair")],
                                     [room("inheritance")]])
    monkeypatch.setattr(C, "SLIP_BOUNDS", (0.0, 0.0))
    game.perform(Action("slip_past"))
    assert game.combat is not None  # seen: it fights


def test_a_formation_trial_grants_insight_once_an_opening(game, monkeypatch):
    world, me = game.world, game.player.id
    inside(game, room("trial", trial="formation"))
    monkeypatch.setattr(C, "FORMATION_BOUNDS", (1.0, 1.0))
    insight = load_body(world, me).insight
    game.perform(Action("attempt_trial"))
    assert load_body(world, me).insight > insight
    assert Action("attempt_trial") not in actions(game.perform(Action("look")))


def test_a_failed_formation_costs_qi_and_hurts(game, monkeypatch):
    world, me = game.world, game.player.id
    inside(game, room("trial", trial="formation"))
    monkeypatch.setattr(C, "FORMATION_BOUNDS", (0.0, 0.0))
    body = load_body(world, me)
    body.qi = max_qi(body)
    save_body(world, me, body)
    game.perform(Action("attempt_trial"))
    after = load_body(world, me)
    assert after.qi <= 0.75 * max_qi(body) and len(after.injuries) == len(body.injuries) + 1  # halved, then two watches' rest


def test_the_qi_pressure_asks_for_qi_and_gives_cultivation(game):
    world, me = game.world, game.player.id
    inside(game, room("trial", trial="pressure"))
    body = load_body(world, me)
    body.qi = max_qi(body)
    save_body(world, me, body)
    energy = body.energy_years
    game.perform(Action("attempt_trial"))
    assert load_body(world, me).energy_years > energy


def test_the_mirror_is_you_and_beating_it_sharpens_your_art(game):
    from systems.duel import best_art
    world, me = game.world, game.player.id
    mine = best_art(world, me)  # a hunter's family art
    inside(game, room("trial", trial="mirror"))
    game.perform(Action("attempt_trial"))
    reflection = game.combat.opponent
    assert world.entity(reflection).data["realm_spirit"] and best_art(world, reflection).technique.id == mine.technique.id
    end_duel(game, "spar_won")
    assert best_art(world, me).mastery == pytest.approx(mine.mastery + C.MIRROR_MASTERY)


def test_the_inheritance_is_won_once_and_names_your_master(game):
    world, me = game.world, game.player.id
    realm = inside(game)
    game.perform(Action("delve_on"))  # the stair down
    assert Action("face_shade") in actions(game.perform(Action("look")))
    game.perform(Action("face_shade"))
    shade = game.combat.opponent
    from systems.tournaments import realm_of
    assert realm_of(world, shade) == realm_of(world, me) + 1
    end_duel(game, "passed")
    master = world.entity(realm).data["master"]
    assert world.entity(realm).data["inheritance_claimed_by"] == me
    assert any(t == master["art"] for t, _, _ in world.relations_from(me, "knows"))
    assert any(d.get("role") == "master" for _, _, d in world.relations_from(me, "kin_of"))  # kin_of lists only the living
    assert any("Master" in t and master["name"] in t for t, _ in lineage_lines(world, me))
    assert Action("face_shade") not in actions(game.perform(Action("look")))
    assert check_realms(world) == []


def test_failing_the_shade_throws_you_back_for_this_opening(game):
    world, me = game.world, game.player.id
    inside(game)
    game.perform(Action("delve_on"))
    game.perform(Action("face_shade"))
    end_duel(game, "failed")
    assert D.position(world, me)["chamber"] == 0
    assert Action("face_shade") not in actions(game.perform(Action("look")))


def test_what_the_dead_carried_lies_where_they_fell(game):
    world, me = game.world, game.player.id
    realm = inside(game, room("trial", trial="formation"))
    rival = C._spirit(world, "test:fallen", realm, 1, 0, "Ma Chen", realm="second-rate")
    world.update_data(rival, realm_spirit=False, beast=False)
    herb = world.add_entity("treasure", "a blood lotus", {"kind": "herb", "value": 300, "used": False})
    world.relate(rival, herb, "owns")
    commit(world, [G_died(rival, realm)])
    assert herb in world.entity(realm).data["floors"][0][0]["contents"]["remains"]
    assert world.sources(herb, "owns") == [realm]
    game.perform(Action("take_remains", herb))
    assert world.sources(herb, "owns") == [me]


def G_died(person, realm):
    from world.events import Event
    return Event("died", (person, person), realm, {"cause": "realm", "world": True})


def test_an_opening_renews_what_was_taken_and_slain(game, monkeypatch):
    monkeypatch.setattr(C, "RESTOCK_CHANCE", 1.0)
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    spent = [{"kind": "treasure", "state": "looted", "contents": {"prize": {"kind": "herb", "name": "a herb", "value": 1}}},
             {"kind": "guardian", "state": "slain", "contents": {"species": "stone lion", "realm": 2, "guardian": 99}},
             {"kind": "stair", "state": "untouched", "contents": {}}]
    world.update_data(realm, gate=town, floors=[spent, [room("inheritance")]])
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    sky.observe(world, town)
    floor = world.entity(realm).data["floors"][0]
    assert floor[0]["state"] == "untouched" and floor[1]["state"] == "untouched" and floor[1]["contents"]["guardian"] is None
