"""The deferred minors from the phase 4b final review."""

import pytest

import systems.agendas as agendas
import systems.bonds as bonds
import systems.encounters as encounters
import systems.lives as lives
from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.attitude import attitude
from systems.creation import CreationChoice
from systems.techniques import known_arts, martial_arts, set_mastery, teach
from tests.test_sect import found_sect


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
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


def local(game, path, town=None, **data):
    return founding.make_person(game.world, path, town or game.place.id, **{"occupation": "herbalist", "age": 30, **data})


def die(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    turn = game.perform(Action("meditate", 90))
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    return turn


def succeed(game, monkeypatch, heir, role="child"):
    agendas._pair(game.world, game.player.id, heir, role)
    old = game.player.id
    die(game, monkeypatch)
    game.perform(Action("succeed", heir))
    return old


def test_a_masked_heir_is_not_known_by_the_ancestor(game, monkeypatch):
    friend = local(game, "test:friend", traits=["curious", "lazy"])  # no temperament terms
    moment = game.world.chronicle_about(game.player.id, limit=1)[0].id
    game.world.add_memory(friend, moment, "grateful", 1.0, True)
    son = local(game, "test:son", age=20)
    succeed(game, monkeypatch, son)
    warm = attitude(game.world, friend, son).score
    persona = game.world.add_entity("persona", "the Grey-Masked Stranger", {"of": son})
    assert warm > 0 and attitude(game.world, friend, persona).score == pytest.approx(-0.2)  # only the hidden face


def test_a_grandchild_is_remembered_through_both_forebears(game, monkeypatch):
    friend = local(game, "test:friend")
    moment = game.world.chronicle_about(game.player.id, limit=1)[0].id
    game.world.add_memory(friend, moment, "grateful", 1.0, True)
    son = local(game, "test:son", age=20)
    succeed(game, monkeypatch, son)
    grandson = local(game, "test:grandson", age=20)
    cold = attitude(game.world, friend, grandson).score
    succeed(game, monkeypatch, grandson)
    assert attitude(game.world, friend, grandson).score > cold


def test_an_inherited_art_keeps_the_heirs_mastery(game, monkeypatch):
    art = martial_arts(game.world, game.player.id)[0].technique.id
    son = local(game, "test:son", age=20)
    teach(game.world, son, art, completeness=0.1, known_completeness=0.1, source="taught")
    set_mastery(game.world, son, art, 0.6)
    succeed(game, monkeypatch, son)
    known = next(a for a in known_arts(game.world, son) if a.technique.id == art)
    assert known.completeness > 0.1 and known.mastery == pytest.approx(0.6)


def test_followers_serve_the_heir(game, monkeypatch):
    follower = local(game, "test:follower", sworn_to=game.player.id)
    son = local(game, "test:son", age=20)
    succeed(game, monkeypatch, son)
    assert game.world.entity(follower).data["sworn_to"] == son


def test_a_newcomer_leaves_no_orphaned_sect_or_followers(tmp_path, monkeypatch):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("First", world_seed=11)
    sect, town = found_sect(app.game)
    follower = founding.make_person(app.game.world, "test:follower", town, sworn_to=app.game.player.id)
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    app.submit("meditate season")
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    app.submit(str(next(i for i, c in enumerate(app.choices, 1) if c.action.verb == "newcomer")))
    for key in ("return", "return"):
        app.handle_key(key, "\r")
    world = app.game.world
    assert world.entity(sect).data.get("dissolved")
    assert not world.entity(follower).data.get("sworn_to")
    app.shutdown()


def test_is_candidate_agrees_with_the_list(game):
    me = game.player.id
    son, pupil, stranger = local(game, "test:son", age=20), local(game, "test:pupil", age=17), local(game, "test:x")
    agendas._pair(game.world, me, son, "child")
    agendas._pair(game.world, me, pupil, "disciple")
    listed = {p for p, _ in bonds.candidates(game.world, me)}
    for person in (son, pupil, stranger):
        assert bonds.is_candidate(game.world, me, person) == (person in listed)


def test_death_screen_labels_are_current(game, monkeypatch):
    far = local(game, "test:son", age=20)
    agendas._pair(game.world, game.player.id, far, "child")
    game.world.update_data(far, lived_to=lives.current_season(game.world) - 8)
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0 if age < 19 else 0.0)  # only the player dies
    turn = game.perform(Action("meditate", 90))
    label = next(c.label for c in turn.choices if c.action.target == far)
    assert ", 22," in label


def test_a_bug_report_on_the_death_screen_keeps_date_and_place(tmp_path, monkeypatch):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Mortal", world_seed=11)
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    app.submit("meditate season")
    context = app.debug_context("test")
    assert "date" in context and "place" in context and "game_state_error" not in context
    app.shutdown()
