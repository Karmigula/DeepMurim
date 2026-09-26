"""Phase 4h's final review: the fixes, each pinned."""
import random

import pytest

import systems.encounters as encounters
import systems.frames as R
import systems.legitimacy as L
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.scheming as S
import systems.succession_crisis as SC
import systems.testament as T
from debug.invariants import check_people, check_plots
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls
from systems.creation import CreationChoice
from systems.world_clock import _promotion
from tests.intrigue import still
from tests.test_crisis_contest import a_crisis, sway_all
from tests.test_crisis_play import crisis_at_seat, to_stage
from world.events import Event, commit


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
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(L, "MANUAL_CHANCE", 0.0)
    monkeypatch.setattr(S, "NPC_FIND", 0.0)


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def stand_at(world, me, town):
    world.unrelate(me, "located_in")
    world.relate(me, town, "located_in")


def labels(turn):
    return [c.label for c in turn.all_choices]


def test_the_camps_cannot_find_your_hand_without_a_clue(game, monkeypatch):
    monkeypatch.setattr(S, "NPC_FIND", 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(me, silver=500)
    game.perform(Action("forge_will", (occurrence.id, proud)))
    to_stage(world, occurrence, seat, "announced")
    [plot] = [world.entity(p.id) for p in world.entities("plot") if p.data["type"] == "forgery"]
    assert plot.data["state"] == "open" and not world.facts(predicate="forger", subject=me)


def test_a_spy_cast_out_for_another_crime_leaves_no_spy_plot_open(game):
    world = game.world
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    [keeper] = halls.staff_at(world, sect, seat, roles=("keeper",))
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    cult = of_type(world, "demonic_cult")
    commit(world, U.spy_events(world, sect, cult, keeper, "review:spy"))
    commit(world, M.murder_events(world, sect, leader, keeper, cult, seat, random.Random(5)))
    [murder] = P.plots_of(world, sect, ("murder",))
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    commit(world, P.exposed_events(world, murder, elder, seat))
    assert F.membership(world, keeper, sect)[1]["status"] == "expelled"
    assert P.plots_of(world, sect, ("spy",)) == [] and check_plots(world) == []


def test_a_framed_player_can_search_their_old_quarters_and_clear_their_name(game, monkeypatch):
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    commit(world, R.frame_events(world, world.entity(occurrence.id), proud, me, "frame:review", random.Random(1)))
    assert F.membership(world, me, sect)[1]["status"] == "expelled"
    [plot] = P.plots_of(world, sect, ("frame",))
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "false_witness")
    game.perform(Action("talk", witness))
    game.perform(Action("ask_clue", (witness, "false_witness")))
    game.perform(Action("farewell"))
    game.perform(Action("look"))
    if game.challenger is not None:  # one who bears you a grudge calls you out; not today
        game.perform(Action("answer_challenge", False))
    assert "Search your old quarters" in [c.label for c in game._general_extras()]
    game.perform(Action("search_quarters", me))
    assert sorted(P.suspicions(world, me, sect)[proud]) == ["false_witness", "planted"]
    game.perform(Action("accuse", (proud, sect)))
    assert F.membership(world, me, sect)[1]["status"] == "member"


def test_the_quarters_a_framed_exile_left_behind_can_be_searched(game, monkeypatch):
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    commit(world, R.frame_events(world, world.entity(occurrence.id), proud, keeper, "frame:exile", random.Random(1)))
    assert seat not in world.targets(keeper, "located_in")  # gone into exile
    [plot] = P.plots_of(world, sect, ("frame",))
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "false_witness")
    game.perform(Action("talk", witness))
    game.perform(Action("ask_clue", (witness, "false_witness")))
    game.perform(Action("farewell"))
    label = f"Search the quarters {world.entity(keeper).name} left behind"
    assert label in labels(game.perform(Action("look")))
    game.perform(Action("search_quarters", keeper))
    assert sorted(P.suspicions(world, me, sect)[proud]) == ["false_witness", "planted"]


def test_a_claimant_who_failed_the_founders_test_cannot_claim_again(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(sect, tier="great")
    monkeypatch.setattr(L, "test_chance", lambda w, p: 0.0)
    monkeypatch.setattr(L, "TEST_DEATH", 0.0)
    game.perform(Action("claim_seat", occurrence.id))
    game.perform(Action("founder_test", occurrence.id))
    assert SC.claimant(SC.crisis_of(world.entity(occurrence.id)), me) is None
    assert not [label for label in labels(game.perform(Action("look"))) if "Claim the seat" in label]
    game.perform(Action("claim_seat", occurrence.id))
    assert SC.claimant(SC.crisis_of(world.entity(occurrence.id)), me) is None


def test_a_puppets_plot_ends_with_its_crisis(game):
    world = game.world
    sect, seat, keeper, proud = a_crisis(game)
    occurrence = SC.live(world, sect)
    patron = next(i for i in F.ensure_roster(world) if i != sect)
    commit(world, U.puppet_events(world, occurrence, patron, proud, f"puppet:{occurrence.id}"))
    sway_all(world, occurrence, keeper)
    to_stage(world, occurrence, seat, "active")
    assert SC.live(world, sect) is None
    assert P.plots_of(world, sect, ("puppet",)) == [] and P.puppet_served(world, sect) == set()
    assert check_plots(world) == []


def test_a_frames_plot_ends_with_its_framer(game):
    world = game.world
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    commit(world, R.frame_events(world, world.entity(occurrence.id), proud, keeper, "frame:dead", random.Random(1)))
    commit(world, [Event("died", (proud, proud), seat, {"cause": "illness", "world": True})])
    commit(world, P.season_events(world, lives.current_season(world) + 1))
    assert P.plots_of(world, sect, ("frame",)) == []


def test_your_spy_found_out_names_you_the_spymaster(game):
    world, me = game.world, game.player.id
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    stand_at(world, me, seat)
    follower = founding.make_person(world, "test:follower", seat, occupation="wandering swordsman", age=25,
                                    sworn_to=me)
    world.update_data(me, silver=200)
    game.perform(Action("plant_spy", (follower, sect)))
    [plot] = P.plots_of(world, sect, ("spy",))
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    commit(world, P.exposed_events(world, plot, elder, seat))
    assert world.facts(predicate="spymaster", subject=me)


def test_an_outsider_named_is_forgotten_once_the_seat_is_filled(game):
    world = game.world
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    world.update_data(sect, outsider=elder)
    commit(world, [_promotion(world, elder, sect, "leader", 4, None)])
    assert world.entity(sect).data.get("outsider") is None


def test_one_who_dies_while_you_talk_with_them_leaves_the_conversation(game):
    world, me = game.world, game.player.id
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    stand_at(world, me, seat)
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    game.perform(Action("talk", elder))
    commit(world, [Event("died", (elder, elder), seat, {"cause": "founder_test", "world": True})])
    turn = game.perform(Action("ask", "news"))
    assert game.focus is None and check_people(game, turn) == []


def test_clues_from_two_plots_do_not_make_one_case(game):
    world, me = game.world, game.player.id
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    stand_at(world, me, seat)
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    commit(world, M.murder_events(world, sect, leader, elder, None, seat, random.Random(99)))
    commit(world, U.spy_events(world, sect, of_type(world, "demonic_cult"), elder, "review:two"))
    [murder] = P.plots_of(world, sect, ("murder",))
    [spy] = P.plots_of(world, sect, ("spy",))
    commit(world, P.found_events(world, murder, "body", me, seat))
    commit(world, P.found_events(world, world.entity(spy.id), "mark", me, seat))
    assert P.accuse_block(world, me, elder, sect) is not None
