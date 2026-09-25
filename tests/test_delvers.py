import pytest

import systems.delve as D
import systems.delvers as R
import systems.encounters as encounters
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_realms
from engine.actions import Action
from engine.game import Game
from systems import founding
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
    monkeypatch.setattr(R, "AMBUSH_CHANCE", 0.0)


def room(kind, **contents):
    return {"kind": kind, "state": "untouched", "contents": contents}


def band(world, town, name, realm="second-rate", traits=("calm", "honest")):
    person = founding.make_person(world, f"test:{name}", town, occupation="wandering swordsman", age=25, realm=realm)
    world.update_data(person, traits=list(traits))
    return person


def open_with_bands(game, floors, bands):
    """A realm at the player's town, open now, with these bands chosen at the gate (one member each)."""
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": "open", "value": None}, floors=floors)
    data = {**SR.opening_data(realm), "delvers": list(bands), "teams": [{"faction": None, "members": [b]} for b in bands]}
    commit(world, sky.start_events(world, "realm_opening", town, world.time, data))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    sky.observe(world, town)
    return realm, occurrence


def teams(world, occurrence):
    return world.entity(occurrence).data["data"]["teams"]


def put(world, occurrence, i, at):
    t = world.entity(occurrence).data["data"]
    moved = [dict(team) for team in t["teams"]]
    moved[i]["at"] = at
    world.update_data(occurrence, data={**t, "teams": moved})
    for member in moved[i]["members"]:
        world.update_data(member, delve_at=at)


def actions(turn):
    return [c.action for c in turn.all_choices]


def test_the_bands_are_placed_when_you_enter_the_strong_deeper(game):
    world, town = game.world, game.place.id
    floors = [[room("trial", trial="formation"), room("stair")], [room("trial", trial="mirror"), room("stair")],
              [room("inheritance")]]
    weak, strong = band(world, town, "weak", "third-rate"), band(world, town, "strong", "second-rate")
    realm, occurrence = open_with_bands(game, floors, [weak, strong])
    game.perform(Action("enter_realm", realm))
    placed = teams(world, occurrence)
    assert [t["at"][0] for t in placed] == [1, 2]
    for member in (weak, strong):
        assert world.targets(member, "located_in") == [realm] and world.entity(member).data["delve_at"]
    assert check_realms(world) == []


def test_bands_step_as_you_act_and_take_what_they_reach(game):
    world, town = game.world, game.place.id
    herb = {"kind": "herb", "name": "a snow lingzhi", "value": 400}
    floors = [[room("trial", trial="formation"), room("treasure", prize=herb), room("stair")], [room("inheritance")]]
    rival = band(world, town, "rival")
    realm, occurrence = open_with_bands(game, floors, [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 1])
    game.perform(Action("delve_rest"))
    assert world.entity(realm).data["floors"][0][1]["state"] == "looted"
    assert any(world.entity(i).name == "a snow lingzhi" for i in world.targets(rival, "owns"))


def test_rival_sects_clash_when_they_meet(game, monkeypatch):
    monkeypatch.setattr(R, "rivals", lambda world, a, b: True)
    monkeypatch.setattr(R, "CLASH_DEATH", 1.0)
    world, town = game.world, game.place.id
    floors = [[room("trial", trial="formation"), room("trial", trial="pressure"), room("stair")], [room("inheritance")]]
    a, b = band(world, town, "a", "first-rate"), band(world, town, "b", "third-rate")
    realm, occurrence = open_with_bands(game, floors, [a, b])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 2])
    put(world, occurrence, 1, [1, 2])
    game.perform(Action("delve_rest"))
    [stepped] = [e for e in world.chronicle_of_kind("delvers_stepped")][-1:]
    assert stepped.data["clashes"] and sum(world.entity(p).data.get("dead", False) for p in (a, b)) == 1


def test_a_band_can_win_the_inheritance_first(game, monkeypatch):
    monkeypatch.setattr(R, "INHERIT_CHANCE", 1.0)
    world, town = game.world, game.place.id
    rival = band(world, town, "heir")
    realm, occurrence = open_with_bands(game, [[room("stair")], [room("inheritance")]], [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [2, 0])
    game.perform(Action("delve_rest"))
    assert world.entity(realm).data["inheritance_claimed_by"] == rival


def test_a_band_in_your_chamber_bars_the_way_until_it_lets_you_pass(game):
    world, town = game.world, game.place.id
    rival = band(world, town, "gatekeeper")
    realm, occurrence = open_with_bands(game, [[room("trial", trial="formation"), room("stair")], [room("inheritance")]],
                                       [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 0])
    found = actions(game.perform(Action("look")))
    assert Action("delve_on") not in found and Action("ask_pass", 0) in found
    game.perform(Action("ask_pass", 0))
    assert Action("delve_on") in actions(game.perform(Action("look")))


def test_beating_a_band_routs_it(game):
    import systems.duel as duel
    from world.seed import rng_for
    world, town = game.world, game.place.id
    rival = band(world, town, "brawler")
    realm, occurrence = open_with_bands(game, [[room("trial", trial="formation"), room("stair")], [room("inheritance")]],
                                       [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 0])
    game.perform(Action("fight_rival", 0))
    d = game.combat
    event = duel._end_event(world, d, "won", "limit", rng_for(1, "end"), d.harm, 5, "spare")
    game._commit([event])
    game._finish_duel(event.data)
    assert not R.blocking(world, game.player.id)


def test_a_hostile_band_may_attack_first(game, monkeypatch):
    monkeypatch.setattr(R, "AMBUSH_CHANCE", 1.0)
    world, town = game.world, game.place.id
    rival = band(world, town, "proud one", "first-rate", traits=("proud", "greedy"))
    realm, occurrence = open_with_bands(game, [[room("trial", trial="formation"), room("stair")], [room("inheritance")]],
                                       [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 0])
    game.perform(Action("delve_rest"))
    assert game.combat is not None and game.combat.opponent == rival


def test_bands_make_for_the_gate_before_it_closes(game):
    world, town = game.world, game.place.id
    rival = band(world, town, "careful")
    realm, occurrence = open_with_bands(game, [[room("stair")], [room("trial", trial="formation"), room("inheritance")]],
                                       [rival])
    game.perform(Action("enter_realm", realm))
    put(world, occurrence, 0, [1, 0])
    world.set_time(world.entity(occurrence).data["active"][1] - 4)  # the last day
    game.perform(Action("delve_rest"))
    assert world.targets(rival, "located_in") == [town] and teams(world, occurrence)[0]["left"]
    assert [f for f in world.facts(predicate="delved") if f.subject == rival]
