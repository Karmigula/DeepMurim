import pytest

import systems.sect_seasons as seasons
from app import App
from config import Config
from engine.actions import Action
from engine.ledger import ledger_lines
from engine.standing_page import faction_facts, known_factions, standing_lines
from systems import factions as F
from tests.test_sect import calm, found_sect, game  # noqa: F401


def test_the_ledger_shows_treasury_roster_relations_and_chronicle(game):
    sect, town = found_sect(game)
    game.world.set_time(game.world.time + seasons.SEASON)
    turn = game.perform(Action("ledger"))
    text = [t for t, _ in turn.lines]
    assert any(t.startswith("Test Pine Sect (righteous)") for t in text)
    assert any(t.startswith("Treasury:") for t in text)
    assert any(t.startswith("Roster (3):") for t in text)
    assert any("Relations:" == t for t in text)
    assert any(t.startswith("  The ") and "of year" in t for t in text)


def test_the_ledger_names_only_factions_you_have_heard_of(game):
    sect, town = found_sect(game)
    heard = set(known_factions(game.world, game.player.id, town))
    text = " ".join(t for t, _ in ledger_lines(game.world, game.player.id))
    unheard = [game.world.entity(f).name for f in F.ensure_roster(game.world) if f not in heard]
    assert unheard and not any(name in text for name in unheard)


def test_no_sect_no_ledger(game):
    assert game.perform(Action("ledger")).lines[-1] == ("You lead no sect.", "system")


def test_f6_and_briefs_mention_the_sect(game):
    sect, town = found_sect(game)
    assert any(t.startswith("Your sect: Test Pine Sect") for t, _ in standing_lines(game.world, game.player.id, town))
    assert faction_facts(game.world, game.player.id, None)[0] == "You lead the Test Pine Sect, 3 disciples strong."


def test_f7_opens_the_ledger(game, tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Leader", world_seed=11)
    app.handle_key("f7", "")
    assert any("You lead no sect." in text for text, _ in app.log)
    app.shutdown()
