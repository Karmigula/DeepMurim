import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.mortality as mortality
from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from systems import cultivation
from systems.bodies import load_body
from systems.creation import CreationChoice


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


def texts(turn):
    return [t for t, _ in turn.lines]


def die_of_age(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    return game.perform(Action("meditate", 90))


def test_the_player_ages_with_the_seasons(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    game.perform(Action("meditate", 90))
    assert game.player.data["age"] == 18.25
    assert "(18)" in game.perform(Action("look")).status


def test_white_hair_warns_that_the_end_is_near(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    life = mortality.lifespan(game.world, game.player.id)
    game.world.update_data(game.player.id, age=life - mortality.WHITE_HAIR - 0.1)
    turn = game.perform(Action("meditate", 90))
    assert "Your hair has gone white." in texts(turn)
    assert "lifespan near" in turn.status


def test_old_age_can_kill(game, monkeypatch):
    town = game.place.id
    turn = die_of_age(game, monkeypatch)
    me = game.world.entity(game.world.get_meta("player_id"))
    assert me.data["dead"] and me.data["dying"]["cause"] == "age"
    assert game.world.targets(me.id, "buried_at") == [town]
    assert [c.action.verb for c in turn.choices][-1] == "new_world"
    assert any(t.startswith("Hero died of old age in") for t in texts(turn))
    [fact] = game.world.facts(predicate="died", subject=me.id)
    assert fact.weight == mortality.DEATH_WEIGHT


def test_the_dead_can_only_choose(game, monkeypatch):
    die_of_age(game, monkeypatch)
    assert texts(game.perform(Action("meditate", 7)))[-1] == "You are dead. Choose how your story goes on."
    assert any(t.startswith("Hero died of old age") for t in texts(game.perform(Action("look"))))


def test_qi_deviation_can_kill(game, monkeypatch):
    monkeypatch.setattr(mortality, "DEVIATION_DEATH", 1.0)
    body = load_body(game.world, game.player.id)
    events = cultivation._deviation_event(game.world, game.player.id, game.place.id, body, 100.0,
                                          list(body.meridians), "test")
    game._commit(events)
    assert game.player.data["dying"]["cause"] == "deviation"


def test_the_death_screen_survives_a_reload(tmp_path, monkeypatch):
    path = tmp_path / "dead.world"
    g = Game.new(path, "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    die_of_age(g, monkeypatch)
    g.close()
    again = Game.load(path)
    turn = again.start()
    assert [c.action.verb for c in turn.choices][-1] == "new_world" and "dead" in turn.status
    assert texts(again.perform(Action("rest", 7)))[-1] == "You are dead. Choose how your story goes on."
    again.close()


def test_a_new_world_returns_to_the_title(tmp_path, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Mortal", world_seed=11)
    app.submit("meditate season")
    assert app.state == "game" and app.choices[-1].action.verb == "new_world"
    app.submit(str(len(app.choices)))
    assert app.state == "title" and app.game is None
    app.shutdown()
