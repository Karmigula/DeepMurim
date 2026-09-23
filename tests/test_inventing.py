import pytest

import systems.inventing as inventing
from engine.game import Action, Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.techniques import martial_arts

FRAGMENTS = [
    {"technique": "Azure Crane Palm", "form": "palm", "element": "water", "segment": ["Lung", "Heart"]},
    {"technique": "Iron Tiger Fist", "form": "fist", "element": "metal", "segment": ["Stomach", "Spleen"]},
    {"technique": "Silent Moon Palm", "form": "palm", "element": "water", "segment": ["Kidney", "Liver"]},
]


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def ready(game, insight=45.0):
    body = load_body(game.world, game.player.id)
    body.insight, body.realm, body.energy_years = insight, 1, 1.0
    save_body(game.world, game.player.id, body)
    game.world.update_data(game.player.id, fragments=list(FRAGMENTS))


def test_you_need_fragments_and_insight(game):
    assert "fragments" in inventing.why_not_create(game.world, game.player.id)
    ready(game, insight=5.0)
    assert "insight" in inventing.why_not_create(game.world, game.player.id)
    ready(game)
    assert inventing.why_not_create(game.world, game.player.id) is None
    assert inventing.creatable_forms(game.world, game.player.id) == ["fist", "palm"]


def test_creating_a_palm_art(game):
    ready(game)
    before = {a.technique.id for a in martial_arts(game.world, game.player.id)}
    start = game.world.time
    practise = game.perform(Action("practise_menu"))
    assert Action("create_menu") in [c.action for c in practise.choices]
    menu = game.perform(Action("create_menu"))
    palm = next(c.action for c in menu.choices if c.action == Action("create_art", "palm"))
    turn = game.perform(palm)
    new = [a for a in martial_arts(game.world, game.player.id) if a.technique.id not in before]
    assert len(new) == 1
    art = new[0]
    assert art.form == "palm" and art.source == "created" and art.mastery == pytest.approx(0.1)
    assert art.technique.data["creator"] == game.player.id and art.technique.data["element"] == "water"
    assert set(art.technique.data["route"]) <= {"Lung", "Heart", "Stomach", "Spleen", "Kidney", "Liver"}
    assert art.technique.data["grade"] == 2  # min(realm 1 + 1, 1 + 45 // 40)
    assert game.world.entity(game.player.id).data["fragments"] == []
    assert game.world.time == start + 7 * 4
    assert any("create" in t.lower() for t, _ in turn.lines)


def test_menus_hide_creation_until_ready(game):
    practise = game.perform(Action("practise_menu"))
    assert Action("create_menu") not in [c.action for c in practise.choices]
    assert game.perform(Action("create_menu")).lines[-1][1] == "system"
