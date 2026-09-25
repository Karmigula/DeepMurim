import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_clock as clock
from debug.invariants import check_crises
from engine.game import Game
from narrate.gossip_text import rumour_text
from systems import factions as F
from systems import halls
from systems.beliefs import believe, known_people
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import ensure_town


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


def a_crisis(game, near=True):
    """The orthodox sect's chief disciple against a proud elder above them."""
    world = game.world
    sect, seat = a_sect(game, near)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["proud"])
    world.update_data(elders[1], traits=["kind"], realm="mortal")  # too weak to claim: two claimants, not three
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    a_season(game)
    return sect, seat, keeper, elders[0]


def to_contest(world, occurrence, seat):
    world.set_time(occurrence.data["ends"]["active"])
    sky.observe(world, seat)


def sway_all(world, occurrence, toward):
    crisis = SC.crisis_of(occurrence)
    sways = {str(v): {str(toward): 5.0} for v in C.voters(world, crisis["faction"])}
    world.update_data(occurrence.id, data={**crisis, "sways": sways})


def test_a_camp_with_a_majority_takes_the_seat(game):
    world = game.world
    sect, seat, keeper, proud = a_crisis(game)
    occurrence = SC.live(world, sect)
    sway_all(world, occurrence, keeper)
    to_contest(world, occurrence, seat)
    assert staff(world, sect, seat, "leader") == [keeper]
    assert SC.live(world, sect) is None and world.entity(sect).data["crisis"] is None
    assert SC.crisis_of(world.entity(occurrence.id))["outcome"] == {"leader": keeper, "how": "backing", "schism": None}
    line = world.entity(sect).data["history"][-1]
    assert line["winner"] == keeper and line["how"] == "backing" and proud in line["claimants"]
    [told] = [f for f in world.facts(predicate="crisis") if f.data["variant"]["stage"] == "settled"]
    assert told.subject == keeper
    assert any(m.feeling == "wronged" for m in world.memories(proud, about=keeper))  # the loser remembers
    assert check_crises(world) == []


def test_without_a_majority_the_two_largest_camps_meet_in_a_trial(game, monkeypatch):
    monkeypatch.setattr(SC, "REFUSE_CHANCE", 0.0)
    world = game.world
    sect, seat, keeper, proud = a_crisis(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: ({keeper: [keeper], proud: [proud]}, [1, 2]))
    occurrence = SC.live(world, sect)
    to_contest(world, occurrence, seat)
    trial = SC.crisis_of(world.entity(occurrence.id))["trial"]
    assert {trial["a"], trial["b"]} == {keeper, proud} and trial["winner"] in (keeper, proud)
    assert staff(world, sect, seat, "leader") == [trial["winner"]]
    assert SC.crisis_of(world.entity(occurrence.id))["outcome"]["how"] == "trial"


def test_a_proud_loser_may_refuse_the_trial(game, monkeypatch):
    monkeypatch.setattr(SC, "REFUSE_CHANCE", 1.0)
    monkeypatch.setattr(SC, "trial_chance", lambda world, a, b: 0.0)  # the second fighter always wins
    world = game.world
    sect, seat, keeper, proud = a_crisis(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: ({keeper: [keeper], proud: [proud]}, [1, 2]))
    occurrence = SC.live(world, sect)
    to_contest(world, occurrence, seat)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["trial"]["winner"] == keeper  # the proud elder ranks first and loses
    assert crisis["phase"] == "strife" and crisis["strife"] == {"a": keeper, "b": proud, "seasons": 0}
    assert staff(world, sect, seat, "leader") == [] and SC.live(world, sect) is not None


def test_a_trial_the_player_must_fight_waits_and_is_forfeit_if_they_never_come(game, monkeypatch):
    monkeypatch.setattr(SC, "REFUSE_CHANCE", 0.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud = a_crisis(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: ({keeper: [keeper], proud: [proud]}, [1, 2]))
    occurrence = SC.live(world, sect)
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "champions": {str(keeper): me}})
    to_contest(world, occurrence, seat)
    trial = SC.crisis_of(world.entity(occurrence.id))["trial"]
    assert trial["pending"] and trial["champions"][str(keeper)] == me
    assert staff(world, sect, seat, "leader") == []
    world.set_time(world.entity(occurrence.id).data["over_at"])
    sky.observe(world, seat)
    assert staff(world, sect, seat, "leader") == [proud]  # the player's side never came


def test_when_every_claimant_has_fallen_the_elders_choose(game):
    world = game.world
    sect, seat, keeper, proud = a_crisis(game)
    occurrence = SC.live(world, sect)
    kill(world, keeper, seat)
    kill(world, proud, seat)
    to_contest(world, occurrence, seat)
    [leader] = staff(world, sect, seat, "leader")
    assert SC.crisis_of(world.entity(occurrence.id))["outcome"]["how"] == "chosen"


def test_a_crisis_far_from_the_player_is_settled_in_a_line(game):
    world = game.world
    sect, seat, keeper, proud = a_crisis(game, near=False)
    assert SC.live(world, sect) is None
    assert not [row for row in sky.W.index(world) if row[sky.W.TYPE] == SC.KIND]
    [leader] = staff(world, sect, seat, "leader")
    assert leader in (keeper, proud)
    line = world.entity(sect).data["history"][-1]
    assert line["how"] == "far" and line["winner"] == leader
    [told] = world.facts(predicate="crisis")
    assert told.data["variant"]["stage"] == "settled" and set(told.data["variant"]["people"]) == {keeper, proud}
    assert check_crises(world) == []


def test_the_tale_of_a_crisis_names_its_claimants(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud = a_crisis(game)
    sky.observe(world, seat)
    [fact] = world.facts(predicate="crisis")
    text = rumour_text(world, fact.data["variant"], me)
    assert "is without a master" in text and world.entity(keeper).name in text and world.entity(proud).name in text
    believe(world, me, fact.id, fact.data["variant"], None, 0.9, 1, "gossip")
    assert {keeper, proud} <= set(known_people(world, me))  # a tale's names are people the player has heard of


def test_two_sects_seated_in_one_town_each_get_their_crisis_or_their_line(game):
    """Review focus: one live crisis a town (4d); the second is settled in a line, never lost."""
    world = game.world
    sect, seat = a_sect(game)
    cult = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "demonic_cult")
    world.update_data(cult, seat=seat)
    for faction in (sect, cult):
        for leader in C.staff(world, faction, ("leader",)):
            kill(world, leader, seat, cause="killed")
    a_season(game)
    live = [f for f in (sect, cult) if SC.live(world, f) is not None]
    settled = [f for f in (sect, cult) if f not in live]
    assert len(live) <= 1
    for faction in settled:
        if C.staff(world, faction, ("elder",)):
            assert C.staff(world, faction, ("leader",)) or world.entity(faction).data.get("history")
    assert check_crises(world) == []
