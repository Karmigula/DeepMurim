import random

import pytest

import systems.encounters as encounters
import systems.events.beast_tide as beast_tide
import systems.events.tribulation as tribulation
import systems.market as market
import systems.realms as realms
import systems.sky as sky
import systems.world_events as W
import systems.duel as duel
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from tests.test_world_events import begin
from world.events import Event, commit
from world.gen.materialize import region_of


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


def texts(turn):
    return [t for t, _ in turn.lines]


def at_the_bottleneck(game, realm=2):
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years, body.bottleneck = realm, realms.REALMS[realm + 1].threshold, True
    save_body(game.world, game.player.id, body)


def test_breaking_through_to_first_rate_calls_down_the_lightning(game, monkeypatch):
    monkeypatch.setattr(realms, "breakthrough_chance", lambda body, met: 1.0)
    at_the_bottleneck(game)
    turn = game.perform(Action("breakthrough"))
    assert any("Clouds gather" in t for t in texts(turn)), texts(turn)
    world, me, town = game.world, game.player.id, game.place.id
    [fact] = world.facts(predicate="tribulation", subject=me)
    assert fact.variant["realm"] == "first-rate"
    assert any(row[W.TYPE] == "tribulation" for row in W.showing(world, town))


def test_a_lesser_breakthrough_brings_no_lightning(game, monkeypatch):
    monkeypatch.setattr(realms, "breakthrough_chance", lambda body, met: 1.0)
    at_the_bottleneck(game, realm=1)
    game.perform(Action("breakthrough"))
    assert game.world.facts(predicate="tribulation") == []


def test_purity_and_rest_steady_the_roll(game):
    world, me = game.world, game.player.id

    def outcomes(purity):
        body = load_body(world, me)
        body.purity = purity
        save_body(world, me, body)
        found = []
        for t in range(300):
            world.set_time(20 * W.SEASON + t)
            found.append(tribulation.player_roll(world, me))
        return found
    pure, rough = outcomes(0.9), outcomes(0.2)
    assert pure.count("clean") > rough.count("clean")
    assert "crippled" not in pure and "crippled" in rough


def test_scars_and_crippled_meridians_are_real(game):
    world, me, town = game.world, game.player.id, game.place.id
    commit(world, [Event("tribulation", (me,), town, {"realm": 3, "outcome": "scarred"})])
    assert any(i.kind == "internal" for i in load_body(world, me).injuries)
    commit(world, [Event("tribulation", (me,), town, {"realm": 3, "outcome": "crippled"})])
    assert any(m.state == "damaged" for m in load_body(world, me).meridians.values())


def test_an_npc_tribulation_lights_the_sky_only_if_it_is_recent(game):
    world, town = game.world, game.place.id
    n = world.time // W.SEASON
    elder = founding.make_person(world, "test:elder", town, occupation="monk", age=50, realm="second-rate")
    old = founding.make_person(world, "test:old", town, occupation="monk", age=70, realm="second-rate")
    commit(world, [Event("broke_through", (old,), town, {"realm": 3, "season": n - 5})])
    assert world.facts(predicate="tribulation", subject=old) and not W.showing(world, town)
    commit(world, [Event("broke_through", (elder,), town, {"realm": 3, "season": n})])
    assert world.facts(predicate="tribulation", subject=elder)
    assert any(row[W.TYPE] == "tribulation" for row in W.showing(world, town))
    assert any(m.feeling == "respect" for m in world.memories(game.player.id, about=elder))


def test_a_beast_tide_fills_the_roads_with_beasts(game, monkeypatch):
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.2)
    world, me, town = game.world, game.player.id, game.world.entity(game.place.id)

    def kinds():
        found = []
        for t in range(300):
            world.set_time(10 * W.SEASON + 100 + t)
            events = encounters.road_encounter_events(world, me, town)
            found += [e.data["kind"] for e in events if e.kind == "encounter"]
        return found
    plain = kinds()
    world.set_time(10 * W.SEASON + 100)
    long_tide = dict(W.TYPES["beast_tide"], stages={**W.TYPES["beast_tide"]["stages"], "active": 1000})
    monkeypatch.setitem(W.TYPES, "beast_tide", long_tide)  # the samples span more than its 15 days
    begin(world, "beast_tide", region_of(world, town.id).id, starts=world.time - 6 * 4, bounty=50, hunts={}, paid=[])
    tide = kinds()
    assert len(tide) > 1.5 * len(plain) and tide.count("beast") > 0.6 * len(tide)


def test_a_beast_tide_attacks_the_towns(game, monkeypatch):
    monkeypatch.setattr(beast_tide, "ATTACK_CHANCE", 1.0)
    world, town = game.world, game.place.id
    herbs = market.price(world, town, "herbs")
    begin(world, "beast_tide", region_of(world, town).id, starts=world.time - 6 * 4, bounty=50, hunts={}, paid=[])
    sky.observe(world, town)
    dead = world._conn.execute("select count(*) from chronicle where kind = 'died' and data like '%beasts%'").fetchone()[0]
    assert dead >= 1 and market.price(world, town, "herbs") > herbs


def test_three_beast_kills_pay_the_bounty(game):
    world, me, town = game.world, game.player.id, game.place.id
    begin(world, "beast_tide", region_of(world, town).id, starts=world.time - 6 * 4, bounty=50, hunts={}, paid=[])
    silver = silver_of(world, me)
    for _ in range(3):
        commit(world, beast_tide.hunt_events(world, me, town))
    assert silver_of(world, me) == silver + 50
    assert beast_tide.hunt_events(world, me, town) == []


def test_winning_a_fight_with_a_beast_counts_as_a_hunt(game):
    world, me, town = game.world, game.player.id, game.place.id
    occurrence = begin(world, "beast_tide", region_of(world, town).id, starts=world.time - 6 * 4,
                       bounty=50, hunts={}, paid=[])
    region = region_of(world, town)
    beast = encounters.make_roamer(world, region, "beast", 0, 0.5)
    game._start_duel(beast, "duel")
    d = game.combat
    event = duel._end_event(world, d, "won", "broken", random.Random(1), d.harm, 3, verdict="kill")
    game._commit([event])
    game._finish_duel(event.data)
    assert world.entity(occurrence).data["data"]["hunts"] == {str(me): 1}
