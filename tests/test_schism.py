import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.schism as schism
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_clock as clock
from debug.invariants import check_crises
from engine.game import Game
from engine.standing_page import known_factions
from narrate.gossip_text import rumour_text
from systems import factions as F
from systems import founding, halls
from systems.beliefs import believe
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import ensure_town, region_of


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
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)


def a_sect(game, near=True):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    home = world.entity(seat).data
    where = seat if near else ensure_town(world, home["x"] + 6, home["y"] + 6, 0)
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, where, "located_in")
    return sect, seat


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def kill(world, person, place, cause="age"):
    commit(world, [Event("died", (person, person), place, {"cause": cause, "world": True})])


def a_season(game):
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)


def one_season(game):
    """Exactly one season of the faction clock, whatever the time."""
    clock.run_season(game.world, clock.world_tick(game.world) + 1)


def backer(world, sect, seat, i):
    person = founding.make_person(world, f"test:backer:{i}", seat, occupation="wandering swordsman", age=30,
                                  realm="second-rate")
    world.relate(person, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 0, "status": "member",
                                                "secret": False})
    return person


def at_war(game, monkeypatch, near=True):
    """The chief disciple wins the trial; the proud elder refuses it: the camps go to war."""
    monkeypatch.setattr(SC, "REFUSE_CHANCE", 1.0)
    monkeypatch.setattr(SC, "trial_chance", lambda world, a, b: 0.0)
    world = game.world
    sect, seat = a_sect(game, near)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["proud"])
    world.update_data(elders[1], traits=["kind"], realm="mortal")
    proud = elders[0]
    ours, theirs = [backer(world, sect, seat, i) for i in range(3)], [backer(world, sect, seat, i + 3) for i in range(3)]
    camps = {keeper: [keeper] + ours, proud: [proud] + theirs}
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {k: [p for p in v if not world.entity(p).data.get("dead")] for k, v in camps.items()}, [1, 2]))
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    a_season(game)
    occurrence = SC.live(world, sect)
    world.set_time(occurrence.data["ends"]["active"])
    sky.observe(world, seat)
    assert SC.crisis_of(world.entity(occurrence.id))["phase"] == "strife"
    return sect, seat, keeper, proud, theirs, occurrence


def test_a_camp_that_yields_ends_the_strife(game, monkeypatch):
    monkeypatch.setattr(schism, "YIELD", (1.0, 1.0))
    world = game.world
    sect, seat, keeper, proud, theirs, occurrence = at_war(game, monkeypatch)
    one_season(game)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["phase"] == "settled" and crisis["outcome"]["how"] == "strife"
    assert crisis["strife"]["seasons"] == 1
    [leader] = staff(world, sect, seat, "leader")
    assert leader in (keeper, proud)
    assert world.entity(sect).data["crisis"] is None and check_crises(world) == []


def test_a_clash_can_cost_the_losing_camp_a_backer(game, monkeypatch):
    monkeypatch.setattr(schism, "YIELD", (0.0, 0.0))
    monkeypatch.setattr(schism, "KILL_CHANCE", 1.0)
    world = game.world
    sect, seat, keeper, proud, theirs, occurrence = at_war(game, monkeypatch)
    one_season(game)
    [clash] = world.chronicle_of_kind("strife_clash")
    victim = clash.data["victim"]
    assert victim is not None and world.entity(victim).data.get("dead")


def test_two_seasons_of_strife_split_the_sect(game, monkeypatch):
    monkeypatch.setattr(schism, "YIELD", (0.0, 0.0))
    monkeypatch.setattr(schism, "KILL_CHANCE", 0.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, theirs, occurrence = at_war(game, monkeypatch)
    one_season(game)
    one_season(game)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    new = crisis["outcome"]["schism"]
    assert crisis["phase"] == "settled" and new is not None
    breakaway = world.entity(new)
    old = world.entity(sect)
    loser = proud if staff(world, sect, seat, "leader") == [keeper] else keeper
    assert breakaway.data["parent"] == sect and breakaway.data["tier"] == "minor"
    assert breakaway.name.endswith(old.name) and breakaway.name.split(" ")[0] in schism.PREFIXES
    assert F.membership(world, loser, new)[1]["role"] == "leader" and F.membership(world, loser, new)[0] == 4
    assert F.membership(world, loser, sect)[1]["status"] == "released"
    assert F.stance(world, sect, new) == schism.STANCE and F.stance(world, new, sect) == schism.STANCE
    assert new in region_of(world, breakaway.data["seat"]).data["minors"]
    assert old.data["history"][-1]["schism"] == new
    [fact] = world.facts(predicate="schism")
    believe(world, me, fact.id, fact.data["variant"], None, 0.9, 1, "gossip")
    assert breakaway.name in rumour_text(world, fact.data["variant"], me)
    assert new in known_factions(world, me, seat)  # a tale's new sect is one the player has heard of
    assert check_crises(world) == []


def test_past_the_caps_the_losers_are_exiled(game, monkeypatch):
    monkeypatch.setattr(schism, "YIELD", (0.0, 0.0))
    monkeypatch.setattr(schism, "KILL_CHANCE", 0.0)
    monkeypatch.setattr(schism, "MAX_BREAKAWAYS", 0)
    world = game.world
    sect, seat, keeper, proud, theirs, occurrence = at_war(game, monkeypatch)
    one_season(game)
    one_season(game)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["outcome"]["schism"] is None
    [exile] = world.chronicle_of_kind("exiled")
    loser = exile.actors[0]
    assert F.membership(world, loser, sect)[1]["status"] == "released"
    assert world.entity(loser).data["occupation"] == "wandering swordsman"


def test_a_close_contest_far_away_may_split_the_sect(game, monkeypatch):
    monkeypatch.setattr(schism, "FAR_STRIFE", 1.0)
    monkeypatch.setattr(schism, "FAR_GAP", 99.0)
    monkeypatch.setattr(schism, "FAR_SCHISM", 1.0)
    world = game.world
    sect, seat = a_sect(game, near=False)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["proud"])
    world.update_data(elders[1], traits=["kind"], realm="mortal")
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    one_season(game)
    [new] = schism.breakaways(world, sect)
    assert world.entity(sect).data["history"][-1]["schism"] == new
    assert check_crises(world) == []
