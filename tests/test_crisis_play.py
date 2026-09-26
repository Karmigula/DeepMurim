import pytest

import systems.claimants as C
import systems.crisis_play as P
import systems.duties as duties
import systems.encounters as encounters
import systems.lives as lives
import systems.ranks as ranks
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_clock as clock
from debug.invariants import check_crises, check_factions
from engine.actions import Action
from engine.game import Game
from narrate.outcomes import SUMMARIES
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
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def labels(turn):
    return [c.label for c in turn.all_choices]


def crisis_at_seat(game, rank=2):
    """The player, a member of the given rank, stands at the orthodox sect's seat as its crisis begins."""
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", rank, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                               "secret": False})
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    proud, other = staff(world, sect, seat, "elder")
    world.update_data(proud, traits=["proud"])
    world.update_data(other, traits=["kind"], realm="mortal")
    [leader] = staff(world, sect, seat, "leader")
    commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    clock.world_tick(world)
    world.set_time(world.time + lives.SEASON)
    clock.run_due(world)
    return sect, seat, keeper, proud, other, SC.live(world, sect)


def to_stage(world, occurrence, seat, stage):
    world.set_time(occurrence.data["ends"][stage])
    sky.observe(world, seat)


def test_a_core_disciple_may_claim_the_seat_in_the_mourning(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    turn = game.perform(Action("look"))
    name = world.entity(sect).name
    assert f"Claim the seat of the {name}" in labels(turn)
    game.perform(Action("claim_seat", occurrence.id))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert {"person": me, "kind": "player"} in crisis["claimants"] and crisis["declared"][str(me)] == me
    assert world.facts(predicate="claimed_seat", subject=me)
    assert f"Claim the seat of the {name}" not in labels(game.perform(Action("look")))


def test_an_outer_disciple_may_not_claim(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game, rank=1)
    assert P.claim_block(world, occurrence, me) == "Only a core disciple or better, or the named heir, may claim the seat."
    assert ranks.promotion_block(world, me, sect) is not None


def test_declaring_for_a_claimant_and_changing_camps_once(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    assert f"Declare for {world.entity(keeper).name}" in labels(game.perform(Action("look")))
    game.perform(Action("declare_for", keeper))
    assert SC.crisis_of(world.entity(occurrence.id))["declared"][str(me)] == keeper
    game.perform(Action("declare_for", proud))
    assert SC.crisis_of(world.entity(occurrence.id))["declared"][str(me)] == proud
    assert any(m.feeling == "wronged" for m in world.memories(keeper, about=me))  # the camp left behind remembers
    turn = game.perform(Action("declare_for", keeper))
    assert any("changed camps once" in t for t, _ in turn.lines)
    backing, _ = C.camps(world, SC.crisis_of(world.entity(occurrence.id)))
    assert me in backing[proud]  # the player's own vote, for a member of rank 2


def test_swaying_a_voter_by_word_gift_and_threat(game, monkeypatch):
    monkeypatch.setattr(P, "speak_chance", lambda world, voter, player: 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    turn = game.perform(Action("talk", other))
    assert f"Speak to them for {world.entity(keeper).name}" in labels(turn)
    game.perform(Action("sway", (other, "speak")))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["sways"][str(other)][str(keeper)] == P.SWAY["speak"]
    turn = game.perform(Action("sway", (other, "gift")))
    assert any("already worked on them" in t for t, _ in turn.lines)  # once a voter a stage
    world.update_data(me, silver=500)
    to_stage(world, occurrence, seat, "announced")  # the canvass: a new stage, a new chance
    game.perform(Action("talk", other))
    price = P.gift_price(world, SC.crisis_of(world.entity(occurrence.id)), other)
    game.perform(Action("sway", (other, "gift")))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["sways"][str(other)][str(keeper)] > P.SWAY["speak"]
    assert world.entity(me).data["silver"] == 500 - price


def test_a_threat_needs_the_upper_hand_and_leaves_a_grudge(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    assert P.sway_block(world, world.entity(occurrence.id), me, other, "threat") == "They do not fear you."
    monkeypatch.setattr(P, "realm_of", lambda world, person: 5 if person == me else 0)
    game.perform(Action("talk", other))
    game.perform(Action("sway", (other, "threat")))
    assert SC.crisis_of(world.entity(occurrence.id))["sways"][str(other)][str(keeper)] == P.SWAY["threat"]
    assert any(m.feeling == "wronged" for m in world.memories(other, about=me))


def test_a_favour_done_in_the_canvass_wins_the_voter(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    game.perform(Action("talk", other))
    game.perform(Action("sway", (other, "favour")))
    duty = duties.open_duty(world, me)
    assert duty is not None and duty.data["favour"]["voter"] == other
    commit(world, duties.done_events(world, me, seat))
    assert SC.crisis_of(world.entity(occurrence.id))["sways"][str(other)][str(keeper)] == P.SWAY["favour"]


def test_the_player_who_claims_and_wins_leads_the_sect(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    sways = {str(v): {str(me): 5.0} for v in C.voters(world, sect)}
    world.update_data(occurrence.id, data={**crisis, "sways": sways})
    to_stage(world, occurrence, seat, "active")
    assert F.membership(world, me, sect)[0] == 4 and F.membership(world, me, sect)[1]["role"] == "leader"
    assert check_factions(world) == [] and check_crises(world) == []


def test_a_champion_fights_the_trial_for_their_claimant(game, monkeypatch):
    monkeypatch.setattr(SC, "REFUSE_CHANCE", 0.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    assert f"Offer to fight as {world.entity(keeper).name}'s champion" in labels(game.perform(Action("look")))
    game.perform(Action("champion_for", keeper))
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: ({keeper: [keeper, me], proud: [proud]}, [1, 2, 3]))
    to_stage(world, occurrence, seat, "active")
    side, foe = P.my_trial(world, world.entity(occurrence.id), me)
    assert side == keeper and foe == proud
    assert f"Fight the trial against {world.entity(proud).name}" in labels(game.perform(Action("look")))
    game.perform(Action("fight_trial", occurrence.id))
    assert game.combat is not None
    commit(world, P.trial_result_events(world, world.entity(occurrence.id), me, won=True))
    assert staff(world, sect, seat, "leader") == [keeper]


def test_searching_the_late_masters_chambers_can_turn_up_the_will(game, monkeypatch):
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 1.0, "other": 1.0})
    monkeypatch.setattr(T, "WILL_STATES", (("hidden", 1.0),))
    monkeypatch.setattr(T, "SEARCH_BASE", 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    to_stage(world, occurrence, seat, "announced")
    assert "Search the late master's chambers" in labels(game.perform(Action("look")))
    game.perform(Action("search_chambers", occurrence.id))
    will = SC.crisis_of(world.entity(occurrence.id))["will"]
    assert will["state"] == "held" and will["holder"] == me
    turn = game.perform(Action("look"))
    assert "Read out the late master's will" in labels(turn) and "Burn the late master's will" in labels(turn)
    assert "Search the late master's chambers" not in labels(turn)  # once a season
    game.perform(Action("reveal_will", occurrence.id))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["will"]["state"] == "read" and "will" in C.proofs(world, crisis, SC.claimant(crisis, keeper))


def test_the_leaders_token_changes_hands(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    token = SC.crisis_of(occurrence)["token"]
    T.put(world, token, place=seat)  # set down in the hall
    turn = game.perform(Action("look"))
    assert f"Pick up {world.entity(token).name}" in labels(turn)
    game.perform(Action("take_token", token))
    assert T.holder(world, token) == me
    assert f"Hand the leader's token to {world.entity(proud).name}" in labels(game.perform(Action("look")))
    game.perform(Action("hand_token", (token, proud)))
    assert T.holder(world, token) == proud
    assert any(m.feeling == "grateful" and m.indelible for m in world.memories(proud, about=me))
    assert "token" in C.proofs(world, SC.crisis_of(world.entity(occurrence.id)),
                               SC.claimant(SC.crisis_of(occurrence), proud))
    assert check_crises(world) == []


def test_a_token_can_be_bought_from_a_holder_who_is_no_claimant(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    token = SC.crisis_of(occurrence)["token"]
    T.put(world, token, owner=other)
    price = P.token_price(world, token)
    world.update_data(me, silver=price + 10)
    turn = game.perform(Action("talk", other))
    assert f"Buy {world.entity(token).name} ({price} silver)" in labels(turn)
    game.perform(Action("buy_sect_token", (other, token)))
    assert T.holder(world, token) == me and world.entity(me).data["silver"] == 10


def test_rank_three_is_as_high_as_anyone_rises_without_a_crisis(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    world.relate(me, sect, "member_of", 3, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    assert ranks.promotion_block(world, me, sect) == "Only a crisis opens the leader's seat."


def test_every_crisis_event_you_take_part_in_has_a_journal_line():
    for kind in ("crisis_declared", "crisis_claimed", "crisis_swayed", "crisis_champion", "chambers_searched",
                 "will_revealed", "will_burned", "will_taken", "sect_token_bought", "sect_token_taken",
                 "sect_token_won", "sect_token_handed", "crisis_trial", "crisis_settled", "crisis_refused",
                 "crisis_lost"):
        assert kind in SUMMARIES, kind


def test_a_claimant_who_dies_before_the_contest_leaves_it_to_the_others(game):
    """Review focus: the player claims, then dies; the contest goes on among the living."""
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    commit(world, [Event("died", (me, me), seat, {"cause": "age", "player": True})])
    to_stage(world, occurrence, seat, "active")
    [leader] = staff(world, sect, seat, "leader")
    assert leader in (keeper, proud) and check_crises(world) == []
