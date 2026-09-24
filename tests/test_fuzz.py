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


def keep_playing(app, step):
    """A death may end in a new world or a newcomer (phase 4b); carry the run on, then insist on play."""
    for _ in range(30):
        if app.state == "game":
            return
        if app.state == "title" and app.game is None:
            app.start_new("Ko Haneul", world_seed=step + 1)  # a real name: "Again" is also a word the prose uses
        else:
            app.handle_key("return", "\r")
    assert app.state == "game", f"left the game at step {step}"


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
        keep_playing(app, step)
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
        keep_playing(app, step)
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
        keep_playing(app, step)
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
        keep_playing(app, step)
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
        keep_playing(app, step)
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
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()


@pytest.mark.parametrize("seed", [6, 17])
def test_a_short_dangerous_life(tmp_path, seed, monkeypatch):
    """Everyone fights to kill and age comes quickly: death, heirs and newcomers again and again, every rule held."""
    import systems.lives as lives
    import systems.mortality as mortality
    for key in mortality.KILL_CHANCE:
        monkeypatch.setitem(mortality.KILL_CHANCE, key, 1.0)
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.08)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 2.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Mayfly{seed}", world_seed=seed)
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2"]))
        elif app.choices and rng.random() < 0.5:
            app.submit(str(rng.randint(1, len(app.choices))))
        else:
            app.submit(rng.choice(["meditate season", "challenge", "go north", "go east", "go south", "go west",
                                   "look", "lineage", "journal", "1", "2"]))
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()


@pytest.mark.parametrize("seed", [9, 31])
def test_a_travelling_trader(tmp_path, seed, monkeypatch):
    """Buying, selling and hauling between towns, robbed now and then: every trade rule holds."""
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 1.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Trader{seed}", world_seed=seed)
    app.game.world.update_data(app.game.player.id, silver=2000)
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3", "4"]))
        elif game.submenu in ("market", "trade_good") and app.choices:
            app.submit(str(rng.randint(1, len(app.choices))))
        else:
            app.submit(rng.choice(["market", "market", "prices", "go north", "go east", "go south", "go west",
                                   "look", "meditate week", "1", "2", "3"]))
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()


@pytest.mark.parametrize("seed", [4, 17])
def test_a_sky_watcher(tmp_path, seed, monkeypatch):
    """Seasons pass under a busy sky: comets, blood moons, tides, races, tribulations and the lists; every rule holds."""
    import systems.world_events as W
    for kind, spec in list(W.TYPES.items()):
        if spec["cycle"] == "season":
            monkeypatch.setitem(W.TYPES, kind, {**spec, "chance": min(1.0, spec["chance"] * 10)})
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 1.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Watcher{seed}", world_seed=seed)
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.3 and app.choices:
            app.submit(str(rng.randint(1, len(app.choices))))
        else:
            app.submit(rng.choice(["sky", "rankings", "seek", "swallow", "look", "meditate season", "meditate month",
                                   "go north", "go east", "go south", "go west", "rest", "journal"]))
        if rng.random() < 0.05:
            app.handle_key("f10", "")
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()
