import random

import pytest

import systems.encounters as encounters
import systems.frames as R
import systems.legitimacy as L
import systems.murder as M
import systems.plots as P
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action, Choice
from engine.commands import parse
from engine.game import Game
from narrate.outcomes import SUMMARIES
from systems import factions as F
from systems.creation import CreationChoice
from tests.intrigue import still
from tests.test_crisis_play import crisis_at_seat, to_stage
from tests.test_plots import poisoned_sect
from world.events import commit


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


def labels(turn):
    return [c.label for c in turn.all_choices]


def a_murder(game, monkeypatch):
    monkeypatch.setattr(M, "MURDER_CHANCE", 1.0)
    monkeypatch.setattr(M, "RED_HERRING", 0.0)
    monkeypatch.setattr(M, "EXAMINE_BASE", 1.0)
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    sect, seat, leader, proud, plot = poisoned_sect(game)
    import systems.lives as lives
    import systems.world_clock as clock
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)
    return sect, seat, proud, plot


def test_the_body_the_quarters_and_the_accusation(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, proud, plot = a_murder(game, monkeypatch)
    turn = game.perform(Action("look"))
    assert "Examine the late master's body" in labels(turn)
    turn = game.perform(Action("examine_body", SC.live(world, sect).id))
    assert any("This was no natural death" in t for t, _ in turn.lines)
    assert any(f"You have found it" in t for t, _ in turn.lines)
    name = world.entity(proud).name
    assert f"Search {name}'s quarters" in labels(game.perform(Action("look")))
    game.perform(Action("search_quarters", proud))
    assert f"Accuse {name} before the elders" in labels(game.perform(Action("look")))
    turn = game.perform(Action("accuse", (proud, sect)))
    assert any("nowhere to hide" in t for t, _ in turn.lines)
    assert world.entity(plot.id).data["state"] == "exposed"


def test_the_witness_is_asked_about_the_night(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, proud, plot = a_murder(game, monkeypatch)
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "witness")
    turn = game.perform(Action("talk", witness))
    assert "Ask about the night the master died" in labels(turn)
    turn = game.perform(Action("ask_clue", (witness, "witness")))
    assert any("what they saw that night" in t for t, _ in turn.lines)
    assert P.suspicions(world, me, sect) == {proud: ["witness"]}


def test_a_proud_man_falsely_accused_calls_you_out(game, monkeypatch):
    monkeypatch.setattr(M, "RED_HERRING", 1.0)
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    monkeypatch.setattr(M, "MURDER_CHANCE", 1.0)
    world, me = game.world, game.player.id
    import tests.test_plots as TP
    innocent_sect = TP.poisoned_sect  # the plotter is pinned there; build a red herring by hand instead
    sect, seat, leader, proud, plot = innocent_sect(game)
    innocent = next(p for p in (c["witness"] for c in plot.data["clues"] if c.get("witness")) if p != proud)
    world.update_data(innocent, traits=["proud"])
    clues = [dict(c, points_to=innocent, false=True) if c["kind"] in ("witness", "motive") else c
             for c in plot.data["clues"]]
    world.update_data(plot.id, clues=clues)
    commit(world, P.found_events(world, world.entity(plot.id), "witness", me, seat))
    commit(world, P.found_events(world, world.entity(plot.id), "motive", me, seat))
    turn = game.perform(Action("accuse", (innocent, sect)))
    assert any("falls apart" in t for t, _ in turn.lines)
    assert game.challenger == innocent


def test_a_claimant_may_face_the_founders_test(game, monkeypatch):
    monkeypatch.setattr(L, "test_chance", lambda world, person: 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    assert "Enter the founder's hall and face the test" in labels(game.perform(Action("look")))
    turn = game.perform(Action("founder_test", occurrence.id))
    assert any("you are chosen" in t for t, _ in turn.lines)
    assert F.membership(world, me, sect)[1]["role"] == "leader"


def test_a_forged_wills_seal_can_be_examined(game, monkeypatch):
    monkeypatch.setattr(R, "FORGE_CHANCE", 1.0)
    monkeypatch.setattr(R, "seal_chance", lambda world, player: 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(proud, traits=["cunning"])
    to_stage(world, occurrence, seat, "announced")
    assert "Examine the will that was read" in labels(game.perform(Action("look")))
    turn = game.perform(Action("examine_will", occurrence.id))
    assert any("the seal is not the late master's" in t for t, _ in turn.lines)


def test_a_framed_player_may_demand_the_seat_back(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    commit(world, R.frame_events(world, world.entity(occurrence.id), proud, me, "frame:test", random.Random(1)))
    framed = world.entity(me).data["framed"]
    world.update_data(me, framed={**framed, "since": framed["since"] - R.PLAYER_RETURN})
    label = f"Demand the seat of the {world.entity(sect).name} you were cast out of"
    assert label in [c.label for c in game._general_extras()]  # a grudge may call the player out first
    game.perform(Action("return_seat", sect))
    assert world.chronicle_of_kind("heir_returned")


def test_typed_commands_reach_the_investigation(game):
    assert parse("examine body", []) == Action("examine_body")
    choices = [Choice("Accuse Ha Haolong before the elders", Action("accuse", (39, 9)))]
    assert parse("accuse ha haolong", choices) == Action("accuse", (39, 9))


def test_every_deed_of_the_investigation_has_a_journal_line():
    for kind in ("body_examined", "clue_found", "quarters_searched", "plot_exposed", "false_accusation",
                 "asked_night", "asked_about", "will_examined", "founder_passed", "founder_failed", "heir_returned"):
        assert kind in SUMMARIES, kind
