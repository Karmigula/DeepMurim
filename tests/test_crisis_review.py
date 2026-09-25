"""Phase 4g final review: the Critical and Important findings, each pinned by a test."""

import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.regency as R
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_clock as clock
from engine.actions import Action
from engine.crisis_page import succession_lines
from engine.game import Game
from systems import factions as F
from systems import founding, halls
from systems.creation import CreationChoice
from tests.test_crisis_play import crisis_at_seat, to_stage
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


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def far_from(world, me, seat):
    home = world.entity(seat).data
    world.unrelate(me, "located_in")
    world.relate(me, ensure_town(world, home["x"] + 6, home["y"] + 6, 0), "located_in")


def test_a_claimant_who_is_no_member_can_still_take_the_seat(game):
    """C1: a clan head's son, never of the clan, wins it: he joins as its leader; the clock does not crash."""
    world = game.world
    clan = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "martial_clan")
    seat = halls.seat_of(world, clan)
    son = founding.make_person(world, "test:son", seat, occupation="wandering swordsman", age=25)
    assert F.membership(world, son, clan) is None
    commit(world, [clock._promotion(world, son, clan, "leader", 4, None)])
    assert C.role_in(world, son, clan) == "leader" and F.membership(world, son, clan)[0] == 4


def test_a_forfeit_after_the_player_is_gone_goes_against_their_side(game, monkeypatch):
    """I2: the player claims, the trial waits for them, they die and an heir carries on: their side forfeits."""
    monkeypatch.setattr(SC, "REFUSE_CHANCE", 0.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {c["person"]: [c["person"]] + ([other] if c["person"] == me else []) for c in crisis["claimants"]},
        [1, 2, 3, 4, 5]))  # the player's camp the largest, short of a majority: a trial the player must fight
    to_stage(world, occurrence, seat, "active")
    trial = SC.crisis_of(world.entity(occurrence.id))["trial"]
    assert trial["pending"] and me in trial["champions"].values()
    heir = founding.make_person(world, "test:heir", seat, occupation="wandering swordsman", age=25)
    commit(world, [Event("died", (me, me), seat, {"cause": "age", "player": True})])
    world.set_meta("player_id", heir)
    world.set_time(world.entity(occurrence.id).data["over_at"])
    sky.observe(world, seat)
    [leader] = staff(world, sect, seat, "leader")
    assert leader != me and not world.entity(leader).data.get("dead")


def test_a_crisis_settled_far_away_deposes_the_holder_it_did_not_choose(game, monkeypatch):
    """I3: a grown ward wins a far refusal crisis against their regent: one leader, the ward."""
    monkeypatch.setattr(R, "REFUSE_HANDOVER", 1.0)
    monkeypatch.setattr(SC, "FAR_PROOF", 1000.0)  # the chief disciple's claim carries it
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    far_from(world, me, seat)
    [keeper] = staff(world, sect, seat, "keeper")
    [regent] = staff(world, sect, seat, "leader")
    world.update_data(regent, traits=["proud"])
    world.update_data(sect, regency_for=keeper)
    commit(world, R.regency_events(world, clock.world_tick(world) + 1))
    assert C.staff(world, sect, ("leader",)) == [keeper]


def test_the_token_passes_to_the_new_leader_and_falls_where_its_holder_dies(game):
    """I4: the chief disciple held the token and lost; the winner takes it up. A holder's death sets it down."""
    world = game.world
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    token = SC.crisis_of(occurrence)["token"]
    assert T.holder(world, token) == keeper
    crisis = SC.crisis_of(world.entity(occurrence.id))
    world.update_data(occurrence.id, data={**crisis, "sways": {str(v): {str(proud): 5.0} for v in C.voters(world, sect)}})
    to_stage(world, occurrence, seat, "active")
    assert staff(world, sect, seat, "leader") == [proud] and T.holder(world, token) == proud
    commit(world, [Event("died", (proud, proud), seat, {"cause": "age", "world": True})])
    assert T.holder(world, token) is None and T.lies_at(world, token) == seat


def test_a_holder_who_dies_sets_the_token_down(game):
    """I4: a token never stays with the dead."""
    world = game.world
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    token = SC.crisis_of(occurrence)["token"]
    commit(world, [Event("died", (keeper, keeper), seat, {"cause": "age", "world": True})])
    assert T.holder(world, token) is None and T.lies_at(world, token) == seat


def test_the_succession_block_names_only_those_you_have_heard_of(game):
    """I5: from a far town, a member reads F6: the claimants are there, their names only if known."""
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    far_from(world, me, seat)
    text = " | ".join(t for t, _ in succession_lines(world, me))
    assert world.entity(proud).name not in text and world.entity(keeper).name not in text
    assert "a claimant you have not met" in text


def test_a_regent_who_beats_their_grown_ward_rules_in_their_own_name(game):
    """I6: the refusal crisis won by the regent ends the regency; no new refusal next season."""
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, seat, "located_in")
    [keeper] = staff(world, sect, seat, "keeper")
    [regent] = staff(world, sect, seat, "leader")
    world.update_data(sect, regency_for=keeper)
    claimants = [{"person": keeper, "kind": "chief"}, {"person": regent, "kind": "regent"}]
    commit(world, [Event("regency_over", (), seat, {"faction": sect})])
    commit(world, SC.begin_events(world, sect, clock.world_tick(world) + 1, "regency", claimants, None, force=True))
    occurrence = SC.live(world, sect)
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "sways": {str(v): {str(regent): 5.0} for v in C.voters(world, sect)}})
    world.set_time(occurrence.data["ends"]["active"])
    sky.observe(world, seat)
    assert C.staff(world, sect, ("leader",)) == [regent]
    assert world.entity(sect).data.get("regency_for") is None
