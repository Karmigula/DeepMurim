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
from systems import factions as F
from systems import founding, halls
from systems.creation import CreationChoice
from world.events import Event, commit
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
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)  # tests that want a transmission ask for one


def a_sect(game, kind="orthodox_sect"):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)
    seat = halls.seat_of(world, sect)
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, seat, "located_in")  # near: its crisis is played in full (spec 2.4)
    return sect, seat


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def kill(world, person, place, cause="age"):
    commit(world, [Event("died", (person, person), place, {"cause": cause, "world": True})])


def a_season(game):
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)


def name_heir(world, sect, person):
    commit(world, [Event("named_chief", (person,), world.entity(sect).data["seat"], {"faction": sect, "season": 0})])


def calm_elders(world, sect, seat):
    for elder in staff(world, sect, seat, "elder"):
        world.update_data(elder, traits=["kind"])


def test_the_chief_disciple_is_named_in_the_first_season_of_each_year(game):
    world = game.world
    sect, seat = a_sect(game)
    assert C.name_chief_events(world, sect, 5) == []
    [named] = C.name_chief_events(world, sect, 4)
    chief = named.actors[0]
    assert C.role_in(world, chief, sect) in ("keeper", "disciple")
    commit(world, [named])
    assert world.entity(sect).data["heir"] == chief
    assert world.facts(predicate="named_chief", subject=chief)
    assert C.name_chief_events(world, sect, 8) == []  # still fit: no new naming


def test_a_player_member_the_leader_favours_is_named_chief_disciple(game):
    world, me = game.world, game.player.id
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    [gift] = commit(world, [Event("gift_given", (me, leader), seat, {})])
    world.add_memory(leader, gift, "grateful", 1.0, True)
    [named] = C.name_chief_events(world, sect, 4)
    assert named.actors == (me,)


def test_a_fit_chief_disciple_takes_the_seat_when_no_ambitious_elder_stands_above(game):
    world = game.world
    sect, seat = a_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    name_heir(world, sect, keeper)
    calm_elders(world, sect, seat)
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    a_season(game)
    assert staff(world, sect, seat, "leader") == [keeper]
    assert SC.live(world, sect) is None and world.entity(sect).data.get("heir") is None


def test_an_ambitious_elder_above_the_chief_disciple_starts_a_crisis(game):
    world = game.world
    sect, seat = a_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    name_heir(world, sect, keeper)
    calm_elders(world, sect, seat)
    proud = staff(world, sect, seat, "elder")[0]
    world.update_data(proud, traits=["proud"])
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    assert SC.doubt(world, sect) == "close"
    a_season(game)
    occurrence = SC.live(world, sect)
    assert occurrence is not None and occurrence.data["type"] == SC.KIND and occurrence.data["place"] == seat
    crisis = SC.crisis_of(occurrence)
    assert crisis["cause"] == "close" and crisis["leader"] == leader and crisis["phase"] == "mourning"
    assert {"person": keeper, "kind": "chief"} in crisis["claimants"]
    assert {"person": proud, "kind": "elder"} in crisis["claimants"]
    assert staff(world, sect, seat, "leader") == []
    assert check_crises(world) == []


def test_the_clock_leaves_the_seat_empty_while_its_crisis_lives(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat, cause="killed")
    a_season(game)
    first = SC.live(world, sect)
    assert first is not None
    n = clock.world_tick(world) + 1
    promotions = clock.succession_events(world, sect, n)  # the clock's next season, asked while the crisis lives
    assert not [e for e in promotions if e.data.get("role") == "leader"]
    assert SC.live(world, sect).id == first.id and staff(world, sect, seat, "leader") == []
    assert check_crises(world) == []


def test_what_puts_a_seat_in_doubt(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    [keeper] = staff(world, sect, seat, "keeper")
    calm_elders(world, sect, seat)
    world.update_data(sect, fallen={"leader": leader, "cause": "killed", "place": seat})
    assert SC.doubt(world, sect) == "violence"
    world.update_data(sect, fallen={"leader": leader, "cause": "age", "place": seat + 1})
    assert SC.doubt(world, sect) == "token"  # died away from the seat: the token is not in the hall
    world.update_data(sect, fallen={"leader": leader, "cause": "age", "place": seat})
    assert SC.doubt(world, sect) == "close"  # no chief disciple, and two elders of a realm
    name_heir(world, sect, keeper)
    assert SC.doubt(world, sect) is None
    world.update_data(keeper, age=12)
    assert SC.doubt(world, sect) == "heir"  # a child cannot hold the seat
    world.update_data(keeper, age=30, sealed_in={"realm": 1, "season": 0})
    assert SC.doubt(world, sect) == "heir"


def test_a_blood_heir_claims_in_a_clan(game):
    world = game.world
    clan, seat = a_sect(game, "martial_clan")
    [leader] = staff(world, clan, seat, "leader")
    child = founding.make_person(world, "test:child", seat, occupation="wandering swordsman", age=20)
    world.relate(leader, child, "kin_of", 0, {"role": "child"})
    claims = C.declare(world, clan, leader)
    assert {"person": child, "kind": "blood"} in claims
    crisis = {"faction": clan, "claimants": claims}
    assert "blood" in C.proofs(world, crisis, {"person": child, "kind": "blood"})


def test_at_most_three_claim_the_seat(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    for i in range(3):
        child = founding.make_person(world, f"test:child:{i}", seat, occupation="wandering swordsman", age=20)
        world.relate(leader, child, "kin_of", 0, {"role": "child"})
        world.relate(child, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 0, "status": "member",
                                                   "secret": False})
    assert len(C.declare(world, sect, leader)) == 3


def test_with_fewer_than_two_claimants_the_seat_is_filled_at_once(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    for elder in staff(world, sect, seat, "elder"):
        kill(world, elder, seat)
    kill(world, leader, seat, cause="killed")
    a_season(game)
    assert SC.live(world, sect) is None
    assert len(staff(world, sect, seat, "leader")) == 1


def test_voters_lean_to_whom_they_like_and_the_loyal_to_the_named(game):
    world = game.world
    sect, seat = a_sect(game)
    [keeper] = staff(world, sect, seat, "keeper")
    elders = staff(world, sect, seat, "elder")
    name_heir(world, sect, keeper)
    for elder in elders:
        world.update_data(elder, traits=["proud"])
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat)
    a_season(game)
    crisis = SC.crisis_of(SC.live(world, sect))
    backing, undecided = C.camps(world, crisis)
    assert all(backing[e][0] == e for e in elders)  # the claimants back themselves
    assert keeper in backing[keeper]
    branch_keepers = [v for v in C.voters(world, sect) if v not in elders and v != keeper]
    voter = branch_keepers[0] if branch_keepers else None
    if voter is not None:
        world.update_data(voter, traits=["loyal"])
        assert C.lean(world, crisis, voter, {"person": keeper, "kind": "chief"}, full=False) >= C.PROOF_LEAN["chief"] + C.LOYAL_LEAN


def test_the_heralds_cry_the_crisis_with_its_claimants(game):
    world = game.world
    sect, seat = a_sect(game)
    [leader] = staff(world, sect, seat, "leader")
    kill(world, leader, seat, cause="killed")
    a_season(game)
    sky.observe(world, seat)
    [fact] = world.facts(predicate="crisis")
    crisis = SC.crisis_of(SC.live(world, sect))
    variant = fact.data["variant"]
    assert variant["people"] == [c["person"] for c in crisis["claimants"]] and variant["target"] == sect
