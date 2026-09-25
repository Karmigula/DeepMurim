import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from debug.invariants import check_realms
from engine.game import Game
from systems import factions as F
from systems import founding
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import ensure_town


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


def opening(game, kind="ceiling", value="second-rate"):
    """The first ancient realm, its gate moved to the player's town (the sects are near), opening now."""
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": kind, "value": value})
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    return realm, W.index(world)[-1][W.ID]


def at(game, occurrence, when):
    """Move to a stage of the opening and let the gate town see it."""
    d = game.world.entity(occurrence).data
    game.world.set_time({"announced": d["ends"]["foretold"], "active": d["active"][0], "closed": d["active"][1]}[when])
    sky.observe(game.world, d["place"])


def away(game):
    world, me = game.world, game.player.id
    world.unrelate(me, "located_in")
    world.relate(me, ensure_town(world, 5, 5, 0), "located_in")


def test_the_ceiling_refuses_the_strong(game):
    world, town = game.world, game.place.id
    realm, _ = opening(game)
    strong = founding.make_person(world, "test:strong", town, occupation="monk", age=50, realm="first-rate")
    weak = founding.make_person(world, "test:weak", town, occupation="monk", age=20, realm="third-rate")
    assert "will not admit" in G.admits(world, realm, strong) and G.admits(world, realm, weak) is None


def test_a_token_realm_hands_out_tokens_and_spends_them_at_the_gate(game):
    world = game.world
    realm, occurrence = opening(game, "token", None)
    at(game, occurrence, "announced")
    tokens = world.entity(occurrence).data["data"]["tokens"]
    assert G.TOKENS[0] <= len(tokens) <= G.TOKENS[1]
    assert all(len(world.sources(t, "owns")) == 1 for t in tokens)
    at(game, occurrence, "active")
    delvers = world.entity(occurrence).data["data"]["delvers"]
    assert delvers and all(world.entity(t).data["used"] for t in tokens if not world.sources(t, "owns"))
    assert all(not G.tokens_of(world, p, realm) for p in delvers)  # each spent theirs to pass


def test_the_near_sects_send_their_strongest_under_the_ceiling(game):
    world = game.world
    realm, occurrence = opening(game)
    at(game, occurrence, "active")
    t = world.entity(occurrence).data["data"]
    assert t["delvers"] and all(T.realm_of(world, p) <= G.ceiling_of(world, realm) for p in t["delvers"])
    for team in t["teams"]:
        assert len(team["members"]) <= (G.PER_SECT if team["faction"] is not None else 1)
    assert len(t["delvers"]) <= G.MAX_DELVERS
    assert not any(d.get("role") in G.HEADS for p in t["delvers"] for _, _, d in F.memberships(world, p))


def test_a_closing_far_away_settles_every_fate_and_moves_only_the_sealed(game):
    world = game.world
    realm, occurrence = opening(game)
    at(game, occurrence, "active")
    away(game)
    at(game, occurrence, "closed")
    t = world.entity(occurrence).data["data"]
    [closed] = [e for e in world.chronicle_of_kind("realm_closed") if e.data["occurrence"] == occurrence]
    fates = closed.data["fates"]
    assert set(fates) == {str(p) for p in t["delvers"]} and t["closed"]
    for person, fate in fates.items():
        p = int(person)
        inside = world.targets(p, "located_in") == [realm]
        assert inside == (fate == "sealed")
        assert (fate == "dead") == bool(world.entity(p).data.get("dead"))
        if fate == "sealed":
            assert p in world.entity(realm).data["sealed"]
            assert all(d.get("status") == "missing" for _, _, d in F.memberships(world, p))
    assert world.entity(realm).data["history"][-1]["entered"] == len(t["delvers"])
    assert check_realms(world) == []


def test_survivors_carry_the_story_out(game, monkeypatch):
    monkeypatch.setattr(G, "OUT_BASE", 1.0)
    world = game.world
    realm, occurrence = opening(game)
    at(game, occurrence, "active")
    away(game)
    at(game, occurrence, "closed")
    delvers = world.entity(occurrence).data["data"]["delvers"]
    heard = {f.subject for _, f in world.known_facts(world.entity(occurrence).data["place"]) if f.predicate == "delved"}
    assert heard == set(delvers)


def test_the_sealed_walk_out_at_the_next_opening(game, monkeypatch):
    monkeypatch.setattr(G, "OUT_BASE", 0.0)
    monkeypatch.setattr(G, "DEAD_CHANCE", 0.0)
    world, town = game.world, game.place.id
    realm, occurrence = opening(game)
    at(game, occurrence, "active")
    away(game)
    at(game, occurrence, "closed")
    sealed = list(world.entity(realm).data["sealed"])
    ages = {p: float(world.entity(p).data.get("age", 30)) for p in sealed}
    assert sealed and all(not lives.simulated(world.entity(p)) for p in sealed)  # frozen while sealed
    world.set_time(world.time + 8 * W.SEASON)
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    at(game, W.index(world)[-1][W.ID], "active")
    assert world.entity(realm).data["sealed"] == []
    for p in sealed:
        person = world.entity(p)
        assert world.targets(p, "located_in") == [town] and not person.data.get("sealed_in")
        assert float(person.data["age"]) == pytest.approx(ages[p] + 1.0, abs=0.3)  # eight seasons at half pace
        assert person.data["lived_to"] == lives.current_season(world)
        assert all(d.get("status") == "member" for _, _, d in F.memberships(world, p))


def test_a_sealed_leader_whose_post_was_filled_walks_out_an_elder(game):
    world, town = game.world, game.place.id
    realm, occurrence = opening(game)
    faction = next(f for f in G.near_sects(world, town))
    old = founding.make_person(world, "test:old leader", town, occupation="monk", age=50, realm="second-rate")
    new = founding.make_person(world, "test:new leader", town, occupation="monk", age=40, realm="second-rate")
    for person, status in ((old, "member"), (new, "member")):
        world.relate(person, faction, "member_of", 4, {"role": "leader", "hall": None, "merit": 0, "status": status,
                                                        "secret": False})
    G.seal(world, old, realm)  # gone: the sect's other leader holds the seat
    commit(world, [Event("walked_out", (old,), town, {"realm": realm})])
    assert F.membership(world, old, faction)[1]["role"] == "elder"


def test_an_inheritance_is_claimed_once(game, monkeypatch):
    monkeypatch.setattr(G, "OUT_BASE", 1.0)
    monkeypatch.setattr(G, "INHERIT_CHANCE", 1.0)
    world = game.world
    realm, occurrence = opening(game)
    at(game, occurrence, "active")
    away(game)
    at(game, occurrence, "closed")
    heir = world.entity(realm).data["inheritance_claimed_by"]
    assert heir is not None and world.entity(heir).data["titles"][-1].startswith("Last Disciple of")
    art = world.entity(realm).data["master"]["art"]
    assert any(t == art for t, _, _ in world.relations_from(heir, "knows"))
    world.set_time(world.time + 8 * W.SEASON)  # the next opening: the legacy is gone
    commit(world, sky.start_events(world, "realm_opening", game.place.id, world.time, SR.opening_data(realm)))
    again = W.index(world)[-1][W.ID]
    at(game, again, "active")
    at(game, again, "closed")
    assert sum(1 for e in world.chronicle_of_kind("realm_closed") if e.data["inherited"]) == 1
    assert world.entity(realm).data["inheritance_claimed_by"] == heir and check_realms(world) == []


def test_an_opening_far_away_makes_no_one_new(game):
    world = game.world
    away(game)
    realm = SR.ensure_realms(world)[0]
    gate = world.entity(realm).data["gate"]
    world.update_data(realm, rule={"kind": "token", "value": None})
    people = len(world.entities("person"))
    commit(world, sky.start_events(world, "realm_opening", gate, world.time, SR.opening_data(realm)))
    occurrence = W.index(world)[-1][W.ID]
    for when in ("announced", "active", "closed"):
        at(game, occurrence, when)
    assert len(world.entities("person")) == people  # the far wanderers and token-holders are never made


def test_the_rules_catch_someone_inside_a_realm_who_should_not_be(game):
    world, town = game.world, game.place.id
    realm, _ = opening(game)
    stray = founding.make_person(world, "test:stray", town, occupation="monk", age=30)
    world.unrelate(stray, "located_in")
    world.relate(stray, realm, "located_in")
    assert any("is inside" in p for p in check_realms(world))
