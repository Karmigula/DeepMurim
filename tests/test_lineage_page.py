import time

import pytest

import systems.agendas as agendas
import systems.encounters as encounters
import systems.lives as lives
from app import App
from config import Config
from debug.invariants import check_lineage
from engine.actions import Action
from engine.game import Game
from engine.lineage_page import lineage_lines
from systems import founding
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
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


def local(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **{"occupation": "herbalist", "age": 30, **data})


def texts(lines):
    return [t for t, _ in lines]


def succeed(game, monkeypatch, heir):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    game.perform(Action("meditate", 90))
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    game.perform(Action("succeed", heir))


def test_the_page_lists_family_and_who_would_inherit(game):
    me = game.player.id
    son, wife = local(game, "test:son", age=20, gender="man"), local(game, "test:wife", gender="woman")
    agendas._pair(game.world, me, son, "child")
    agendas._pair(game.world, me, wife, "spouse")
    lines = texts(game.perform(Action("lineage")).lines)
    name = game.world.entity(son).name
    assert lines[0] == "Your lineage"
    assert any(t.startswith("  Spouse: " + game.world.entity(wife).name) for t in lines)
    assert any(t.startswith(f"  Child: {name}, 20") for t in lines)
    assert "If you died today:" in lines and any(t.startswith(f"  1. {name}") for t in lines)


def test_ancestors_are_remembered_with_how_they_died(game, monkeypatch):
    son = local(game, "test:son", age=20)
    agendas._pair(game.world, game.player.id, son, "child")
    succeed(game, monkeypatch, son)
    lines = texts(lineage_lines(game.world, game.player.id))
    assert "Ancestors:" in lines and any("Hero, died of old age in" in t for t in lines)
    assert check_lineage(game.world) == []


def test_f8_opens_the_page(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Elder", world_seed=11)
    app.handle_key("f8", "")
    assert any(text == "Your lineage" for text, _ in app.log)
    app.shutdown()


def test_briefs_name_the_relation(game):
    son = local(game, "test:son", age=20, gender="man")
    agendas._pair(game.world, game.player.id, son, "child")
    game.perform(Action("talk", son))
    assert f"{game.world.entity(son).name} is your son." in game.last_briefs[-1].facts


def test_an_ancestor_who_still_owns_things_is_caught(game, monkeypatch):
    son = local(game, "test:son", age=20)
    agendas._pair(game.world, game.player.id, son, "child")
    old = game.player.id
    succeed(game, monkeypatch, son)
    game.world.update_data(old, silver=5)
    assert any("still holds" in p for p in check_lineage(game.world))


def test_succession_and_the_page_are_quick(game, monkeypatch):
    me = game.player.id
    for i in range(30):
        agendas._pair(game.world, me, local(game, f"test:kin:{i}", age=20 + i), "child")
    start = time.perf_counter()
    lineage_lines(game.world, me)
    page = time.perf_counter() - start
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    game.perform(Action("meditate", 90))
    start = time.perf_counter()
    game.perform(Action("succeed", game.world.relations_from(me, "kin_of")[0][0]))
    step = time.perf_counter() - start
    assert page < 0.05 and step < 0.1, f"page {page * 1000:.0f} ms, succession {step * 1000:.0f} ms"
