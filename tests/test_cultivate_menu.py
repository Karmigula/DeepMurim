import pytest

from engine.commands import parse
from engine.game import Action, Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=42, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def verbs(choices):
    return [c.action.verb for c in choices]


def test_main_menu_always_fits_and_offers_cultivation(tmp_path):
    for seed in (1, 7, 42, 1234):
        g = Game.new(tmp_path / f"{seed}.world", "Hero", world_seed=seed)
        turn = g.start()
        assert len(turn.choices) <= 9
        assert {"cultivate", "look", "journal"} <= set(verbs(turn.choices))
        assert sum("road" in c.label for c in turn.all_choices) == 4
        g.close()


def test_busy_town_folds_travel_into_a_submenu(tmp_path):
    g = Game.new(tmp_path / "busy.world", "Hero", world_seed=7)
    turn = g.start()
    if "routes" in verbs(turn.choices):
        sub = g.perform(Action("routes"))
        assert sum("road" in c.label for c in sub.choices) == 4 and sub.choices[-1].action.verb == "back"
    g.close()


def test_cultivate_menu_and_meditation(game):
    menu = game.perform(Action("cultivate"))
    labels = [c.label for c in menu.choices]
    assert labels[:4] == ["Meditate for a day", "Meditate for a week", "Meditate for a month", "Seclusion for a season (90 days)"]
    assert "Practise an art..." in labels and "Rest for a week" in labels and labels[-1] == "Back"
    assert not any("breakthrough" in label for label in labels)
    assert any("mortal" in text for text, _ in menu.lines)
    turn = game.perform(Action("meditate", 7))
    assert game.submenu == "cultivate" and game.world.time == 28
    assert "You meditated for a week" in " ".join(t for t, _ in turn.lines)


def test_breakthrough_offered_only_at_bottleneck(game):
    body = load_body(game.world, game.player.id)
    body.energy_years, body.bottleneck = 1.0, True
    save_body(game.world, game.player.id, body)
    menu = game.perform(Action("cultivate"))
    assert "Attempt breakthrough to Third-rate" in [c.label for c in menu.choices]


def test_practise_and_meridian_menus(game):
    sub = game.perform(Action("practise_menu"))
    assert sub.choices[0].action.verb == "practise" and sub.choices[-1].action == Action("cultivate")
    turn = game.perform(sub.choices[0].action)
    assert "You practised the" in " ".join(t for t, _ in turn.lines)
    sub = game.perform(Action("meridian_menu"))
    assert len(sub.choices) == 9 and sub.choices[0].label == "Work on the Governing meridian for a week"
    turn = game.perform(sub.choices[0].action)
    assert turn.lines[-1][1] == "system" and "need" in turn.lines[-1][0]


def test_typed_cultivation_commands(game):
    turn = game.start()
    assert parse("meditate week", turn.choices, turn.extra) == Action("meditate", 7)
    assert parse("meditate season", turn.choices, turn.extra) == Action("meditate", 90)
    assert parse("rest", turn.choices, turn.extra) == Action("rest")
    assert parse("breakthrough", turn.choices, turn.extra) == Action("breakthrough")
    assert parse("cultivate", turn.choices, turn.extra) == Action("cultivate")
    assert parse("open governing", turn.choices, turn.extra) == Action("open_meridian", "Governing")
    art = next(c for c in turn.extra if c.action.verb == "practise")
    word = art.label.split()[2].lower()  # "Practise the <Adjective> ..."
    assert parse(f"practise {word}", turn.choices, turn.extra).verb in ("practise", "ambiguous")


def test_no_cultivating_mid_conversation(game):
    talk = next(c.action for c in game.start().all_choices if c.action.verb == "talk")
    game.perform(talk)
    assert game.perform(Action("meditate", 7)).lines[-1] == ("Finish your conversation first.", "system")


def test_status_shows_realm(game):
    assert "| Mortal |" in game.start().status
