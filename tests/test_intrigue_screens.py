import pytest

import systems.encounters as encounters
import systems.legitimacy as L
import systems.murder as M
import systems.plots as P
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.crisis_page import scheme_lines, succession_lines
from engine.game import Game
from narrate.brief import scene_brief
from systems.creation import CreationChoice
from tests.intrigue import still
from tests.test_intrigue_play import a_murder
from tests.test_scheming import poisoner
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


def texts(lines):
    return " | ".join(t for t, _ in lines)


def test_the_succession_block_shows_what_you_have_found_and_whom_you_suspect(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, proud, plot = a_murder(game, monkeypatch)
    world.relate(me, sect, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    assert "Found:" not in texts(succession_lines(world, me))
    game.perform(Action("examine_body", SC.live(world, sect).id))
    text = texts(succession_lines(world, me))
    assert "Found:" in text and "on the late master's lips" in text
    assert f"Suspicions: {world.entity(proud).name} (1 thing)" in text


def test_your_schemes_are_listed_with_what_could_betray_them(game):
    world, me = game.world, game.player.id
    assert scheme_lines(world, me) == []
    sect, seat, leader, vial = poisoner(game)
    game.perform(Action("talk", leader))
    game.perform(Action("slip_poison", leader))
    text = texts(scheme_lines(world, me))
    assert "Your schemes:" in text and "The poisoning of" in text and "the body" in text
    assert "Your schemes:" in texts(game.perform(Action("standing")).lines)


def test_the_scene_brief_carries_your_suspicions(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, proud, plot = a_murder(game, monkeypatch)
    game.perform(Action("examine_body", SC.live(world, sect).id))
    brief = scene_brief(world, seat, me, "t")
    assert any(f"You suspect {world.entity(proud).name}" in fact for fact in brief.facts)


def test_help_names_the_investigation(game):
    assert any("examine body | accuse <name>" in t for t, _ in game.perform(Action("help")).lines)
