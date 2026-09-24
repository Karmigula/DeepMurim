import random

import pytest

import systems.cultivation as cultivation
import systems.encounters as encounters
import systems.lives as lives
import systems.market as market
import systems.sky as sky
import systems.wars as wars
import systems.world_events as W
from engine.game import Game
from systems import founding
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.duel import fighter_for
from systems.techniques import martial_arts
from tests.test_world_events import add_type, begin
from world.gen.materialize import region_of
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


def faction_of_type(world, kind):
    return next(f.id for f in world.entities("faction") if f.data["type"] == kind)


def join(world, person, faction):
    world.relate(person, faction, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                   "secret": False})


def test_a_qi_tide_speeds_the_players_cultivation_and_breakthrough(game):
    world, me, town = game.world, game.player.id, game.place.id
    body = load_body(world, me)
    body.bottleneck = True
    save_body(world, me, body)
    gained = cultivation.meditate_events(world, me, town, 7)[0].data["energy_gained"]
    chance = cultivation.breakthrough_events(world, me, town)[0].data["chance"]
    begin(world, "qi_tide", region_of(world, town).id, starts=world.time - 11 * 4)
    assert cultivation.meditate_events(world, me, town, 7)[0].data["energy_gained"] == pytest.approx(gained * 1.5, rel=0.01)
    assert cultivation.breakthrough_events(world, me, town)[0].data["chance"] == pytest.approx(min(max(chance, 0.95), chance * 1.2))


def test_npc_growth_reads_the_sky_of_its_own_season(game):
    world, town = game.world, game.place.id
    adept = world.entity(founding.make_person(world, "test:adept", town, occupation="wandering swordsman", age=30))
    n = world.time // W.SEASON
    plain = lives.step_events(world, adept, n, random.Random(1), 1, True)[0].data["years"]
    begin(world, "qi_tide", region_of(world, town).id, starts=n * W.SEASON)
    assert lives.step_events(world, adept, n, random.Random(1), 1, True)[0].data["years"] == pytest.approx(plain * 1.5, rel=0.01)
    assert lives.step_events(world, adept, n - 3, random.Random(1), 1, True)[0].data["years"] == pytest.approx(plain, rel=0.01)


def test_a_blood_moon_strengthens_dark_arts_only(game):
    world, town = game.world, game.place.id
    cultist = founding.make_person(world, "test:cultist", town, occupation="wandering swordsman", age=30)
    join(world, cultist, faction_of_type(world, "demonic_cult"))
    monk = founding.make_person(world, "test:monk", town, occupation="monk", age=30)
    join(world, monk, faction_of_type(world, "orthodox_sect"))
    dark, bright = fighter_for(world, cultist, None).realm_mult, fighter_for(world, monk, None).realm_mult
    begin(world, "blood_moon", None, starts=world.time - 6 * 4)
    assert fighter_for(world, cultist, None).realm_mult == pytest.approx(dark * 1.3)
    assert fighter_for(world, monk, None).realm_mult == pytest.approx(bright)


def test_the_encounter_knob_fills_the_roads(game, monkeypatch):
    add_type(monkeypatch, "red_sky", scope="world", cycle="trigger", stages={"active": 1000}, modifiers={"encounter": 4.0})
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.2)
    world, me, town = game.world, game.player.id, game.world.entity(game.place.id)

    def count():
        found = 0
        for t in range(400):
            world.set_time(10 * W.SEASON + 1000 + t)
            found += bool(encounters.road_encounter_events(world, me, town))
        return found
    plain = count()
    world.set_time(10 * W.SEASON + 1000)
    begin(world, "red_sky", None)
    assert count() > plain * 2


def test_the_clash_knob_stirs_war(game, monkeypatch):
    add_type(monkeypatch, "war_star", scope="world", cycle="trigger", stages={"active": 200}, modifiers={"clash": 4.0})
    monkeypatch.setattr(wars, "CLASH_CHANCE", 0.25)
    monkeypatch.setattr(wars, "WAR_CHANCE", 0.25)
    world = game.world
    n = world.time // W.SEASON
    plain = len([e for e in wars.clash_events(world, n) if e.kind == "clash"])
    begin(world, "war_star", None, starts=n * W.SEASON)
    assert len([e for e in wars.clash_events(world, n) if e.kind == "clash"]) > plain


def test_a_comet_raises_salt_and_rice(game):
    world, town = game.world, game.place.id
    salt, rice, silk = (market.price(world, town, g) for g in ("salt", "rice", "silk"))
    begin(world, "comet", None, starts=world.time - 31 * 4)
    assert market.price(world, town, "salt") == pytest.approx(salt * 1.3, abs=1)
    assert market.price(world, town, "rice") == pytest.approx(rice * 1.3, abs=1)
    assert market.price(world, town, "silk") == silk


def test_a_comet_is_read_differently_town_by_town(game):
    readings = {sky.reading(game.world, "comet", t) for t in range(1, 60)}
    assert len(readings) > 1 and readings <= set(W.TYPES["comet"]["readings"])


def test_a_dao_resonance_doubles_practice_and_names_the_master(game):
    import systems.events.dao_resonance as dao
    world, me, town = game.world, game.player.id, game.place.id
    master = founding.make_person(world, "test:master", town, occupation="monk", age=60, realm="first-rate")
    n = world.time // W.SEASON
    assert dao.eligible(world, town, n)
    art = martial_arts(world, me)[0]
    plain = cultivation.practise_events(world, me, town, art.technique.id, 2)[0].data
    world.set_time(world.time + 1)
    begin(world, "dao_resonance", town, **dao.start_data(world, town, n, rng_for(1, "t")))
    sky.observe(world, town)
    boosted = cultivation.practise_events(world, me, town, art.technique.id, 2)[0].data
    assert boosted["mastery_after"] - boosted["mastery_before"] == pytest.approx(
        2 * (plain["mastery_after"] - plain["mastery_before"]), rel=0.01)
    [fact] = world.facts(predicate="enlightened", subject=master)
    assert fact.variant["actor"] == master and fact.variant["realm"] == "first-rate"


def test_blood_moon_patrols_call_out_the_ruthless(game, monkeypatch):
    import systems.events.blood_moon as blood_moon
    from systems.reputation import Reputation
    world, me, town = game.world, game.player.id, game.place.id
    monk = founding.make_person(world, "test:monk", town, occupation="monk", age=30)
    join(world, monk, faction_of_type(world, "orthodox_sect"))
    monkeypatch.setattr(blood_moon, "reputation", lambda w, t, s: Reputation(9.0, "known", "ruthless", None))
    assert blood_moon.patrols(world, me) == []
    begin(world, "blood_moon", None, starts=world.time - 6 * 4)
    assert monk in blood_moon.patrols(world, me)
    assert blood_moon.patrols in encounters.HUNTER_HOOKS
