import pytest

import systems.cultivation as cultivation
import systems.duel as duel
import systems.learning as learning
from engine.game import Action, Game
from engine.sheet import sheet_lines
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.items import create_manual, manuals_of
from systems.purse import silver_of
from systems.techniques import create_technique, generate, known_arts, martial_arts, teach
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "merchant"))
    g.start()
    yield g
    g.close()


def person(game, occupation, name):
    data = {"occupation": occupation, "traits": ["kind", "honest"], "realm": "mortal", "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", name, data, seed_path=f"test:{name}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def acquainted(game, npc):
    game.perform(Action("talk", npc))
    game.perform(Action("farewell"))
    return game.perform(Action("talk", npc))


def teacher(game, monkeypatch):
    monkeypatch.setitem(duel.TEACHER_CHANCE, "wandering swordsman", 1.0)
    return person(game, "wandering swordsman", "Master Seo")


def test_a_teacher_offers_lessons_to_acquaintances(game, monkeypatch):
    master = teacher(game, monkeypatch)
    first = game.perform(Action("talk", master))
    assert Action("learn_menu") not in [c.action for c in first.choices]
    game.perform(Action("farewell"))
    turn = acquainted(game, master)
    assert Action("learn_menu") in [c.action for c in turn.choices]
    menu = game.perform(Action("learn_menu"))
    assert menu.choices[0].action.verb == "learn_paid" and menu.choices[1].action.verb == "learn_test"
    assert menu.choices[-1].action == Action("talk_menu")


def test_paying_for_a_lesson(game, monkeypatch):
    master = teacher(game, monkeypatch)
    acquainted(game, master)
    art = learning.teachable_arts(game.world, master, game.player.id)[0]
    price = learning.lesson_price(art)
    before = silver_of(game.world, game.player.id)
    game.perform(Action("learn_paid", art.technique.id))
    known = next(a for a in known_arts(game.world, game.player.id) if a.technique.id == art.technique.id)
    assert known.source == "taught" and known.teacher == master
    assert silver_of(game.world, game.player.id) == before - price


def test_no_silver_no_lesson(game, monkeypatch):
    master = teacher(game, monkeypatch)
    acquainted(game, master)
    art = learning.teachable_arts(game.world, master, game.player.id)[0]
    game.world.update_data(game.player.id, silver=0)
    turn = game.perform(Action("learn_paid", art.technique.id))
    assert turn.lines[-1] == ("You cannot afford that lesson.", "system")
    assert art.technique.id not in {a.technique.id for a in known_arts(game.world, game.player.id)}


def test_passing_a_test_spar_teaches_the_art(game, monkeypatch):
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years = 3, 20.0
    save_body(game.world, game.player.id, body)
    master = teacher(game, monkeypatch)
    acquainted(game, master)
    art = learning.teachable_arts(game.world, master, game.player.id)[0]
    game.perform(Action("learn_test", art.technique.id))
    assert game.combat is not None and game.combat.mode == "test"
    for _ in range(3):
        game.perform(Action("intent", "guard"))
    assert game.combat is None
    assert art.technique.id in {a.technique.id for a in known_arts(game.world, game.player.id)}


def test_buying_and_studying_a_manual(game, monkeypatch):
    monkeypatch.setitem(learning.GOODS_CHANCE, "merchant", 1.0)
    seller = person(game, "merchant", "Trader Oh")
    turn = game.perform(Action("talk", seller))
    assert Action("browse") in [c.action for c in turn.choices]
    goods = game.perform(Action("browse"))
    item = goods.choices[0].action.target
    game.perform(Action("buy", item))
    assert item in [m.item.id for m in manuals_of(game.world, game.player.id)]
    game.perform(Action("farewell"))
    start = game.world.time
    practise = game.perform(Action("practise_menu"))
    study = next(c.action for c in practise.choices if c.action.verb == "study")
    game.perform(study)
    manual = next(m for m in manuals_of(game.world, game.player.id) if m.item.id == item)
    known = next(a for a in known_arts(game.world, game.player.id) if a.technique.id == manual.technique.id)
    assert known.source == "manual" and known.completeness == manual.true_completeness and known.known_completeness == 1.0
    assert game.world.time == start + 14 * 4


def test_a_lying_manual_is_found_out_only_by_deviation(game):
    name, art = generate(rng_for(3, "flawed"), "martial", form="palm")
    technique = create_technique(game.world, name, dict(art, route=["Lung", "Heart"], element="neutral"))
    item = create_manual(game.world, game.player.id, technique, 0.4)
    commit(game.world, learning.study_events(game.world, game.player.id, game.place.id, item))
    teach(game.world, game.player.id, technique, completeness=0.4, known_completeness=1.0, source="manual", mastery=0.4)
    assert "completeness 100%" in "\n".join(t for t, _ in sheet_lines(game.world, game.player.id))
    body = load_body(game.world, game.player.id)
    body.deviation = 99.0
    for m in ("Lung", "Heart"):
        body.meridians[m].state = "open"
    save_body(game.world, game.player.id, body)
    turn = game.perform(Action("practise", technique))
    text = " ".join(t for t, _ in turn.lines)
    assert "manual" in text and "never complete" in text
    known = next(a for a in martial_arts(game.world, game.player.id) if a.technique.id == technique)
    assert known.known_completeness == 0.4
