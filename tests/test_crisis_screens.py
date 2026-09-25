import pytest

import systems.encounters as encounters
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action, Choice
from engine.commands import parse
from engine.crisis_page import sheet_crisis_lines, succession_lines
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.brief import scene_brief
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.membership import set_membership
from tests.test_crisis_play import crisis_at_seat


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


def texts(lines):
    return " | ".join(t for t, _ in lines)


def test_the_succession_block_shows_the_stage_the_claimants_and_your_camp(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    text = texts(succession_lines(world, me))
    assert f"Succession: the {world.entity(sect).name}" in text and "the mourning" in text and "days left" in text
    assert f"{world.entity(keeper).name}, the chief disciple (your camp)" in text
    assert f"{world.entity(proud).name}, an elder" in text
    assert "no will has been read" in text.lower() and "leader's token" in text
    assert "Succession:" in texts(game.perform(Action("standing")).lines)


def test_undecided_voters_are_shown_only_once_you_have_worked_on_them(game, monkeypatch):
    import systems.crisis_play as P
    monkeypatch.setattr(P, "speak_chance", lambda world, voter, player: 0.0)  # they stay undecided
    import systems.claimants as C
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: ({keeper: [keeper], proud: [proud]}, [other]))
    game.perform(Action("declare_for", keeper))
    assert world.entity(other).name not in texts(succession_lines(world, me))
    game.perform(Action("talk", other))
    game.perform(Action("sway", (other, "speak")))
    assert f"Undecided: {world.entity(other).name}" in texts(succession_lines(world, me))


def test_the_sky_page_lists_the_crises_you_have_heard_of(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    sky.observe(world, seat)
    [fact] = world.facts(predicate="crisis")
    believe(world, me, fact.id, fact.data["variant"], None, 0.9, 1, "gossip")
    text = texts(game.perform(Action("sky")).lines)
    assert "Succession crises heard of:" in text and "is without a master" in text


def test_the_sheet_names_the_posts_a_crisis_made(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    name = world.entity(sect).name
    world.update_data(sect, heir=me)
    assert f"Chief disciple of the {name}" in texts(sheet_crisis_lines(world, me))
    set_membership(world, me, sect, rank=4, role="leader")
    assert f"Leader of the {name}" in texts(sheet_lines(world, me))
    set_membership(world, me, sect, rank=3, role="retired")
    assert f"Retired master of the {name}" in texts(sheet_crisis_lines(world, me))


def test_help_and_typed_commands_reach_the_crisis(game):
    world = game.world
    assert any("claim | declare <name>" in t for t, _ in game.perform(Action("help")).lines)
    assert parse("claim", []) == Action("claim_seat")
    assert parse("search chambers", []) == Action("search_chambers")
    assert parse("step down", []) == Action("step_down")
    choices = [Choice("Declare for Baek Rin", Action("declare_for", 41))]
    assert parse("declare baek", choices) == Action("declare_for", 41)


def test_the_scene_at_a_seat_in_crisis_tells_of_the_mourning(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    brief = scene_brief(world, seat, me, "t")
    assert any(f"The {world.entity(sect).name} mourns its master" in fact for fact in brief.facts)


def test_a_save_reloaded_mid_crisis_keeps_its_camps(game):
    """Review focus: the crisis lives in the save: camps, choices and the Succession block come back."""
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("declare_for", keeper))
    path = world.path
    game.close()
    again = Game.load(path)
    try:
        turn = again.look()
        assert Action("declare_for", proud) in [c.action for c in turn.all_choices]
        assert "(your camp)" in texts(succession_lines(again.world, me))
    finally:
        again.close()
