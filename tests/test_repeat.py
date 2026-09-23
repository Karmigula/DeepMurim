"""Doing the same thing twice should not read like a stuck record."""


import random

import pytest

from app import App
from config import Config
from engine.game import Action, Game
from narrate.brief import Brief, PersonBrief, PlaceBrief
from narrate.procedural import SYMBOL, Grammar, ProceduralNarrator

PLACE = PlaceBrief("Jade Town", "town", "the Misty Peaks", "mountains", "spring", "dusk")
YOU = PersonBrief("Hero", "you", (), "mortal", "self")
LI = PersonBrief("Li Wei", "innkeeper", ("proud",), "mortal", "acquaintance")
ONE_OFF_KEYS = {"began", "body_awakened"}  # happens once per life; variety not needed
MIN_VARIETY = 6


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=42)
    yield g
    g.close()


def talk_to_someone(game):
    game.perform(next(c.action for c in game.look().all_choices if c.action.verb == "talk"))


def test_asking_again_is_remembered(game):
    talk_to_someone(game)
    game.perform(Action("ask", "work"))
    assert not any("already asked" in f for f in game.last_briefs[0].facts)
    game.perform(Action("ask", "work"))
    brief = game.last_briefs[0]
    assert brief.details["asked_before"] == "1"
    assert any("already asked" in f for f in brief.facts)
    game.perform(Action("ask", "town"))  # a different question is not a repeat
    assert "asked_before" not in game.last_briefs[0].details


def test_narrator_uses_again_lines_for_repeat_questions():
    grammar = Grammar({"asked.work": {"lines": ["FIRST"]}, "asked.work.again": {"lines": ["AGAIN"]}})
    narrator = ProceduralNarrator(grammar)
    first = Brief("asked", "w", PLACE, YOU, LI, {"topic": "work"}, (), 1, "a")
    again = Brief("asked", "w", PLACE, YOU, LI, {"topic": "work", "asked_before": "2"}, (), 1, "b")
    assert narrator.narrate(first)[0][0] == "FIRST"
    assert narrator.narrate(again)[0][0] == "AGAIN"


def test_repeat_look_says_nothing_changed(game):
    first = game.perform(Action("look")).lines
    second = game.perform(Action("look")).lines
    assert second[0] == ("Nothing has changed since you last looked.", "dim")
    assert first[0] != second[0]
    talk_to_someone(game)  # time passes
    game.perform(Action("farewell"))
    assert game.perform(Action("look")).lines[0][1] != "dim"


def test_narrator_avoids_recent_repeats():
    narrator = ProceduralNarrator()
    texts = []
    for n in range(40):
        brief = Brief("parted", "w", PLACE, YOU, LI, {}, (), 7, f"event:{n}")
        texts.append(narrator.narrate(brief)[0][0])
    for window in (texts[i:i + 4] for i in range(len(texts) - 3)):
        assert len(set(window)) == 4, window


def test_same_salt_still_gives_same_text():
    narrator = ProceduralNarrator()
    brief = Brief("parted", "w", PLACE, YOU, LI, {}, (), 7, "event:1")
    assert narrator.narrate(brief) == narrator.narrate(brief)


def _variety(grammar, text, depth=0):
    symbols = grammar.tables.get("symbols", {})
    total = 1
    for name in SYMBOL.findall(text):
        options = symbols.get(name, [""])
        total *= sum(_variety(grammar, o, depth + 1) for o in options) if depth < 5 else len(options)
    return total


def test_every_repeatable_line_has_enough_variety():
    grammar = Grammar.load()
    for key, table in grammar.tables.items():
        if key == "symbols" or key in ONE_OFF_KEYS:
            continue
        count = sum(_variety(grammar, line) for line in table["lines"])
        assert count >= MIN_VARIETY, (key, count)


def test_held_number_key_fires_once(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.handle_key("return", "\r")
    for ch in "Hero":
        app.handle_key(ch, ch)
    app.handle_key("return", "\r")
    app.handle_key("return", "\r")  # Random
    app.handle_key("1", "1")
    before = len(app.log)
    for _ in range(5):
        app.handle_key("1", "1", repeat=True)
    assert len(app.log) == before
    app.handle_key("h", "h", repeat=True)  # held letters still type, like any text box
    assert app.command == "h"
    app.shutdown()


def test_sentences_start_with_a_capital():
    grammar = Grammar({"k": {"lines": ["\"#t# {job},\" she says. again? #t# ok"]}, "symbols": {"t": ["Again?"]}})
    text = grammar.expand("k", random.Random(1), {"job": "hunter"})
    assert text == "\"Again? Hunter,\" she says. Again? Again? Ok"
