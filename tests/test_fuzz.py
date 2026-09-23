"""Random play across several worlds. Any crash or invariant violation fails the run.

This is the standing bug-catcher: new systems get exercised here for free.
"""

import random

import pytest

from app import App
from config import Config

TYPED = ["look", "journal", "help", "talk li", "talk zzz", "go north", "go south", "ask work",
         "ask town", "bye", "²", "", "   ", "x" * 300, "go", "talk", "back", "9", "0",
         "cultivate", "meditate week", "meditate month", "meditate season", "rest", "breakthrough",
         "practise", "open governing", "open conception"]
HOTKEYS = ["f2", "f3", "f4", "f12", "page up", "page down"]


@pytest.mark.parametrize("seed", [1, 7, 42, 1234])
def test_random_play_is_clean(tmp_path, seed):
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Fuzz{seed}", world_seed=seed)
    for step in range(250):
        roll = rng.random()
        if roll < 0.72 and app.choices:
            n = rng.randint(1, len(app.choices))
            app.handle_key(str(n), str(n))
        elif roll < 0.9:
            for ch in rng.choice(TYPED):
                app.handle_key(ch, ch)
            app.handle_key("return", "\r")
        elif roll < 0.95:
            app.handle_key(rng.choice(HOTKEYS), "")
        else:
            app.handle_key("escape", "\x1b")
            app.handle_key("escape", "\x1b")
            if app.state == "title":
                app.handle_key("return", "\r")  # Continue
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()


def test_years_of_cultivation_stay_clean(tmp_path):
    rng = random.Random(99)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Hermit", world_seed=99)
    for _ in range(150):
        app.submit(rng.choice(["meditate season", "meditate month", "rest", "breakthrough", "open governing",
                               "open conception", "cultivate", "1", "2", "3"]))
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    assert app.game.world.time > 4 * 360  # more than a year passed
    app.shutdown()
