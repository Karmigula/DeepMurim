"""Random play across several worlds. Any crash or invariant violation fails the run.

This is the standing bug-catcher: new systems get exercised here for free.
"""

import random

import pytest

import systems.encounters as encounters
from app import App
from config import Config

TYPED = ["look", "journal", "help", "talk li", "talk zzz", "go north", "go south", "ask work",
         "ask town", "bye", "²", "", "   ", "x" * 300, "go", "talk", "back", "9", "0",
         "cultivate", "meditate week", "meditate month", "meditate season", "rest", "breakthrough",
         "practise", "open governing", "open conception",
         "challenge", "spar", "strike", "feint", "guard", "probe", "flee", "yield", "spare", "rob", "cripple",
         "kill", "news", "rumours", "tell", "wear mask", "remove mask", "ask about li", "ask news"]
FIGHTING = ["strike", "feint", "guard", "probe", "strike", "guard", "flee", "yield", "spare", "rob", "cripple", "kill",
            "1", "2", "3", "4"]
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
    assert app.game.world.time > 4 * 360
    app.shutdown()


@pytest.mark.parametrize("seed", [3, 21])
def test_a_violent_life_stays_clean(tmp_path, seed, monkeypatch):
    """Roads full of bandits and beasts, and fights with everyone in town."""
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 3.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Brawler{seed}", world_seed=seed)
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2"]))
        elif rng.random() < 0.35 and app.choices:
            app.submit(str(rng.randint(1, len(app.choices))))
        else:
            app.submit(rng.choice(["challenge", "go north", "go east", "go south", "go west", "1", "look", "rest"]))
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()


@pytest.mark.parametrize("seed", [5, 13])
def test_a_life_of_rumours_and_masks(tmp_path, seed, monkeypatch):
    """Killing, lying, masks and travel: every knowledge rule must hold throughout."""
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 2.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Gossip{seed}", world_seed=seed)
    world, me = app.game.world, app.game.player.id
    with world.transaction():
        mask = world.add_entity("mask", "plain mask", {"persona": None})
        world.relate(me, mask, "owns")
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["kill", "kill", "1", "2"]))
        elif game.focus is not None:
            app.submit(rng.choice(["news", "tell", "1", "2", "3", "4", "5", "6", "ask about li", "challenge", "bye"]))
        elif rng.random() < 0.3 and app.choices:
            app.submit(str(rng.randint(1, len(app.choices))))
        else:
            app.submit(rng.choice(["1", "2", "look", "rumours", "wear mask", "remove mask", "go north", "go east",
                                   "go south", "go west", "rest", "journal"]))
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()


@pytest.mark.parametrize("seed", [8, 17])
def test_a_sect_life(tmp_path, seed, monkeypatch):
    """Join a sect, take duties, rise, travel, fight, get framed or arrested: every rule holds."""
    from systems import halls
    from systems import factions as F
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 1.5)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Disciple{seed}", world_seed=seed)
    world, me = app.game.world, app.game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    with world.transaction():
        world.unrelate(me, "located_in")
        world.relate(me, seat, "located_in")
        world.update_data(me, silver=300)
    app.submit("look")
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["kill", "1", "2", "3", "4"]))
        elif game.player.data.get("summons") or game.player.data.get("arrest"):
            app.submit(rng.choice(["1", "2", "3", "4"]))
        elif game.focus is not None:
            app.submit(rng.choice(["1", "2", "3", "4", "5", "6", "7", "8", "9", "bye"]))
        else:
            app.submit(rng.choice(["1", "2", "3", "4", "look", "standing", "rest", "go north", "go south",
                                   "go east", "go west", "journal"]))
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()


@pytest.mark.parametrize("seed", [4, 19])
def test_a_sect_founder(tmp_path, seed, monkeypatch):
    """Found a sect, run it, roam for seasons, come home: every rule holds."""
    import tests.test_sect as helpers
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 1.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Founder{seed}", world_seed=seed)
    helpers.found_sect(app.game)
    app.game.world.update_data(app.game.player.id, silver=800)
    app.submit("look")
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif game.player.data.get("summons") or game.player.data.get("arrest"):
            app.submit(rng.choice(["1", "2", "3", "4"]))
        elif game.focus is not None:
            app.submit(rng.choice(["1", "2", "3", "4", "5", "6", "7", "8", "9", "bye"]))
        else:
            app.submit(rng.choice(["1", "2", "3", "look", "ledger", "standing", "meditate season", "rest",
                                   "go north", "go south", "go east", "go west"]))
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()


@pytest.mark.parametrize("seed", [3, 8])
def test_a_long_lived_wanderer(tmp_path, seed):
    """Seclusions by the season and long roads: the world ages around the player and every rule holds."""
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Wanderer{seed}", world_seed=seed)
    for step in range(250):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif game.focus is not None:
            app.submit(rng.choice(["1", "2", "3", "4", "5", "bye"]))
        else:
            app.submit(rng.choice(["meditate season", "meditate season", "meditate month", "look", "journal",
                                   "rumours", "go north", "go south", "go east", "go west", "1", "2", "3"]))
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()
