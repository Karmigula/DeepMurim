import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.regency as R
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_clock as clock
from debug.invariants import check_crises, check_factions, check_sect
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls
from systems.creation import CreationChoice
from systems.membership import set_membership
from tests.test_sect import found_sect
from world.events import Event, commit
from world.gen.materialize import ensure_town, region_of
from tests.intrigue import still


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
    still(monkeypatch)  # 4h's intrigue stilled: these test 4g's crises
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def labels(turn):
    return [c.label for c in turn.all_choices]


def the_sect(game, at_seat=True):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    home = world.entity(seat).data
    where = seat if at_seat else ensure_town(world, home["x"] + 6, home["y"] + 6, 0)
    world.unrelate(me, "located_in")
    world.relate(me, where, "located_in")
    return sect, seat


def player_leads(game, at_seat=True):
    """The player has won the orthodox sect's seat."""
    world, me = game.world, game.player.id
    sect, seat = the_sect(game, at_seat)
    [leader] = staff(world, sect, seat, "leader")
    commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    world.update_data(sect, fallen=None)
    world.relate(me, sect, "member_of", 4, {"role": "leader", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    return sect, seat


def settle_for(world, occurrence, seat, person):
    crisis = SC.crisis_of(world.entity(occurrence.id))
    world.update_data(occurrence.id, data={**crisis, "sways": {str(v): {str(person): 5.0}
                                                               for v in C.voters(world, crisis["faction"])}})
    world.set_time(world.entity(occurrence.id).data["ends"]["active"])
    sky.observe(world, seat)


def test_a_regent_claims_for_a_child_and_hands_over_when_they_come_of_age(game, monkeypatch):
    world = game.world
    sect, seat = the_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    world.update_data(keeper, age=12)
    for elder in staff(world, sect, seat, "elder"):
        world.update_data(elder, traits=["kind"])
    [leader] = staff(world, sect, seat, "leader")
    claims = C.declare(world, sect, leader)
    regent = next(c["person"] for c in claims if c["kind"] == "regent")
    assert {"person": keeper, "kind": "chief"} in claims
    commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    clock.world_tick(world)
    world.set_time(world.time + lives.SEASON)
    clock.run_due(world)
    occurrence = SC.live(world, sect)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {c["person"]: [c["person"]] + ([1, 2, 3] if c["person"] == regent else []) for c in crisis["claimants"]}, []))
    settle_for(world, occurrence, seat, regent)
    assert staff(world, sect, seat, "leader") == [regent]
    assert world.entity(sect).data["regency_for"] == keeper
    world.update_data(keeper, age=16)
    commit(world, R.regency_events(world, clock.world_tick(world) + 1))
    assert staff(world, sect, seat, "leader") == [keeper]
    assert C.role_in(world, regent, sect) == "elder" and world.entity(sect).data["regency_for"] is None


def test_an_ambitious_regent_may_refuse_to_hand_over(game, monkeypatch):
    monkeypatch.setattr(R, "REFUSE_HANDOVER", 1.0)
    world = game.world
    sect, seat = the_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    [leader] = staff(world, sect, seat, "leader")
    world.update_data(leader, traits=["proud"])
    world.update_data(sect, regency_for=keeper)
    commit(world, R.regency_events(world, clock.world_tick(world) + 1))
    crisis = SC.crisis_of(SC.live(world, sect))
    assert crisis["cause"] == "regency"
    assert {c["person"] for c in crisis["claimants"]} == {keeper, leader}
    assert check_crises(world) == []  # the regent holds the seat while contesting it


def test_a_long_absence_brings_a_regent_and_an_ambitious_regent_takes_the_seat(game):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game, at_seat=False)
    elders = staff(world, sect, seat, "elder")
    for elder in elders:
        world.update_data(elder, traits=["proud"])
    n = clock.world_tick(world)
    world.update_data(sect, visited=n)
    assert R.absence_events(world, n + R.ABSENCE - 1) == []
    commit(world, R.absence_events(world, n + R.ABSENCE))
    regent = world.entity(sect).data["regent"]["person"]
    assert regent in elders and world.facts(predicate="regency", subject=regent)
    commit(world, R.absence_events(world, n + 2 * R.ABSENCE))
    assert staff(world, sect, seat, "leader") == [regent]
    assert F.membership(world, me, sect)[0] == 3 and world.entity(sect).data["usurped_from"] == me
    assert world.facts(predicate="usurped", subject=regent)
    assert check_factions(world) == []


def test_coming_home_ends_a_loyal_regency_and_contests_an_ambitious_one(game):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game)
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["kind"])
    world.update_data(sect, regent={"person": elders[0], "since": 0})
    game.perform(Action("look"))
    assert world.entity(sect).data["regent"] is None and SC.live(world, sect) is None
    world.update_data(elders[1], traits=["proud"])
    world.update_data(sect, regent={"person": elders[1], "since": 0})
    game.perform(Action("look"))
    crisis = SC.crisis_of(SC.live(world, sect))
    assert {c["person"] for c in crisis["claimants"]} == {me, elders[1]} and crisis["cause"] == "regency"
    assert check_crises(world) == []


def test_a_usurped_master_may_reclaim_the_seat(game):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game)
    usurper = staff(world, sect, seat, "elder")[0]
    set_membership(world, me, sect, rank=3, role="member")
    set_membership(world, usurper, sect, rank=4, role="leader")
    world.update_data(sect, usurped_from=me)
    turn = game.perform(Action("look"))
    assert f"Reclaim the seat of the {world.entity(sect).name}" in labels(turn)
    game.perform(Action("reclaim_seat", sect))
    crisis = SC.crisis_of(SC.live(world, sect))
    assert {c["person"] for c in crisis["claimants"]} == {me, usurper} and crisis["cause"] == "usurped"


def test_stepping_down_in_favour_of_a_clear_successor(game):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game)
    strong, weak = staff(world, sect, seat, "elder")
    world.update_data(strong, traits=["kind"])
    world.update_data(weak, traits=["kind"], realm="mortal")
    assert f"Step down in favour of {world.entity(strong).name}" in labels(game.perform(Action("look")))
    game.perform(Action("step_down", (sect, strong)))
    assert staff(world, sect, seat, "leader") == [strong]
    assert F.membership(world, me, sect)[1]["role"] == "retired" and F.membership(world, me, sect)[0] == 3
    assert world.facts(predicate="stepped_down", subject=me)


def test_stepping_down_against_an_ambitious_elder_starts_a_crisis(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game)
    chosen, proud = staff(world, sect, seat, "elder")
    world.update_data(proud, traits=["proud"])
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {c["person"]: [c["person"]] for c in crisis["claimants"]}, [1, 2, 3]))
    game.perform(Action("step_down", (sect, chosen)))
    crisis = SC.crisis_of(SC.live(world, sect))
    assert {c["person"] for c in crisis["claimants"]} == {chosen, proud} and crisis["cause"] == "stepped_down"
    assert F.membership(world, me, sect)[1]["role"] == "retired"
    assert me in C.voters(world, sect)  # the old master may still back and sway


def test_a_founded_sect_handed_on_becomes_a_school_of_the_world(game):
    world, me = game.world, game.player.id
    sect, town = found_sect(game)
    elder = founding.make_person(world, "test:elder", town, occupation="wandering swordsman", age=40,
                                 realm="second-rate")
    founding.enrol(world, elder, sect, 70, role="elder", rank=3)
    game.perform(Action("step_down", (sect, elder)))
    data = world.entity(sect).data
    assert data["type"] == "school" and data["founder"] is None and data["tier"] == "minor"
    assert sect in region_of(world, town).data["minors"]
    assert founding.my_sect(world, me) is None
    assert F.membership(world, elder, sect)[1]["role"] == "leader"
    assert check_sect(world) == [] and check_factions(world) == []


def test_an_heir_the_elders_doubt_must_win_the_founded_sect(game):
    world, me = game.world, game.player.id
    sect, town = found_sect(game)
    elder = founding.make_person(world, "test:elder", town, occupation="wandering swordsman", age=40,
                                 realm="first-rate")
    founding.enrol(world, elder, sect, 70, role="elder", rank=3)
    heir = founding.make_person(world, "test:heir", town, occupation="wandering swordsman", age=20, realm="third-rate")
    commit(world, [Event("died", (me, me), town, {"cause": "age", "player": True})])
    commit(world, [Event("succession", (me, heir), town, {"kind": "named", "silver": 0, "arts": [], "home": town,
                                                          "led": [[sect, False]]})])
    crisis = SC.crisis_of(SC.live(world, sect))
    assert crisis["cause"] == "heir"
    assert {"person": heir, "kind": "player"} in crisis["claimants"] and SC.claimant(crisis, elder) is not None
    assert world.get_meta("player_id") == heir and check_crises(world) == []


def test_an_heir_no_one_doubts_holds_the_seat_their_forebear_won(game):
    world, me = game.world, game.player.id
    sect, seat = player_leads(game)
    for elder in staff(world, sect, seat, "elder"):
        world.update_data(elder, realm="mortal")
    heir = founding.make_person(world, "test:heir", seat, occupation="wandering swordsman", age=25,
                                realm="first-rate")
    world.relate(heir, sect, "member_of", 2, {"role": "keeper", "hall": None, "merit": 0, "status": "member",
                                              "secret": False})
    commit(world, [Event("succession", (me, heir), seat, {"kind": "named", "silver": 0, "arts": [], "home": seat,
                                                          "led": [[sect, True]]})])
    assert C.role_in(world, heir, sect) == "leader" and SC.live(world, sect) is None
