import pytest

import systems.daos as DA
import systems.encounters as encounters
import systems.heart as HT
import systems.heart_world as HW
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_heart
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.duel import Duel, fighter_for, yield_events
from tests.test_world_events import begin
from world.events import commit
from world.seed import rng_for


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


def master(game, tag, realm="second-rate", steady=10.0):
    pid = founding.make_person(game.world, f"test:mad:{tag}", game.place.id, occupation="monk", age=50, realm=realm)
    HT.write(game.world, pid, steady=steady)
    return pid


def test_a_troubled_master_goes_mad_and_it_is_news(game, monkeypatch):
    world = game.world
    monkeypatch.setattr(HW, "MAD_CHANCE", 1.0)
    low, calm_one, troubled = master(game, "low", "third-rate"), master(game, "calm", steady=70.0), master(game, "t")
    assert HW.season_events(world, low, 0, None) == [] and HW.season_events(world, calm_one, 0, None) == []
    events = HW.season_events(world, troubled, 0, None)
    assert [e.kind for e in events] == ["heart_madness"]
    commit(world, events)
    assert HW.mad(world, troubled) and world.facts("went_mad", subject=troubled)


def test_after_a_year_the_mad_come_back_to_themselves_or_die_of_it(game, monkeypatch):
    world = game.world
    monkeypatch.setattr(HW, "MAD_CHANCE", 1.0)
    one, two = master(game, "one"), master(game, "two")
    commit(world, HW.season_events(world, one, 0, None) + HW.season_events(world, two, 0, None))
    assert HW.season_events(world, one, 1, None) == []
    world.set_time(world.entity(one).data["mad_until"])
    monkeypatch.setattr(HW, "RECOVERY", 1.0)
    commit(world, HW.season_events(world, one, 4, None))
    assert not HW.mad(world, one) and not world.entity(one).data.get("dead")
    monkeypatch.setattr(HW, "RECOVERY", 0.0)
    [death] = HW.season_events(world, two, 4, None)
    assert death.kind == "died" and death.data["cause"] == "madness"
    commit(world, [death])
    assert world.entity(two).data.get("mad_until") is None and check_heart(world) == []


def test_the_mad_call_the_player_out_fight_harder_and_never_spare(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(HW, "MAD_CHANCE", 1.0)
    madman = master(game, "mad")
    plain = fighter_for(world, madman, None).realm_mult
    commit(world, HW.season_events(world, madman, 0, None))
    assert HW.hunting(world, me) == [madman]
    assert fighter_for(world, madman, None).realm_mult == pytest.approx(plain * HW.MAD_FIGHT)
    duel = Duel(1, me, madman, game.place.id, "duel")
    [end] = yield_events(world, duel)
    assert end.data["verdict"] in ("leave_for_dead", "kill")


def test_a_master_enlightened_in_a_resonance_opens_their_dao(game):
    import systems.events.dao_resonance as dao
    world, town = game.world, game.place.id
    sage = founding.make_person(world, "test:sage", town, occupation="monk", age=60, realm="first-rate")
    n = world.time // W.SEASON
    world.set_time(world.time + 1)
    begin(world, "dao_resonance", town, **dao.start_data(world, town, n, rng_for(1, "t")))
    sky.observe(world, town)
    assert list(DA.daos(world, sage).values()) == [HW.ENLIGHTENED_DAO]


def test_check_heart_flags_the_dead_still_mad(game):
    world = game.world
    madman = master(game, "m")
    world.update_data(madman, mad_until=world.time + 10, dead=True)
    assert "mad" in " | ".join(check_heart(world))
