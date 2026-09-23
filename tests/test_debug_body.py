import pytest

from debug.invariants import check_turn, check_world
from engine.game import Game, Turn
from narrate.brief import Brief, PersonBrief, PlaceBrief
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.techniques import martial_arts
from world.body import add_injury, to_dict


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=3, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def problems(game):
    return " | ".join(check_world(game.world))


def test_fresh_body_is_clean(game):
    assert check_world(game.world) == []


def test_body_invariants_catch_bad_numbers(game):
    world, pid = game.world, game.player.id
    body = load_body(world, pid)
    body.qi, body.deviation, body.energy_years = 1e6, 150, 3.0  # a mortal with 3 years and no bottleneck
    world.update_data(pid, body=to_dict(body))  # bypass save_body, which would clamp qi
    text = problems(game)
    assert "qi" in text and "deviation" in text and "energy" in text


def test_injury_and_meridian_invariants(game):
    world, pid = game.world, game.player.id
    body = load_body(world, pid)
    add_injury(body, "left arm", "cut", 2, world.time, "x")
    body.injuries[-1].severity = 9
    body.meridians["Lung"].state = "glowing"
    save_body(world, pid, body)
    text = problems(game)
    assert "severity 9" in text and "Lung" in text


def test_mastery_above_completeness_is_caught(game):
    world, pid = game.world, game.player.id
    art = martial_arts(world, pid)[0]
    world.relate(pid, art.technique.id, "knows", value=0.9, data={"completeness": 0.5, "known_completeness": 1.0, "source": "x"})
    assert "mastery" in problems(game)


def test_realm_label_must_match_body(game):
    game.world.update_data(game.player.id, realm="first-rate")
    assert "realm label" in problems(game)


def test_turn_catches_a_hidden_constitution_leak(game):
    world, pid = game.world, game.player.id
    body = load_body(world, pid)
    body.constitution, body.constitution_known = "Nine Yin Body", False
    save_body(world, pid, body)
    place = PlaceBrief("T", "town", "R", "plains", "spring", "dusk")
    you = PersonBrief("Hero", "you", (), "Mortal", "self")
    game.last_briefs = [Brief("cultivated", "now", place, you, None, {}, ("You have a Nine Yin Body.",), 1, "x")]
    assert any("constitution" in p for p in check_turn(game, Turn([], [], {"type": "scene"}, "s"), []))
