"""Centuries of history, headless: the world keeps its rules, its great factions and a sane size."""

import random
import time

import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.rumours as rumours
import systems.world_clock as clock
from debug.invariants import check_world
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.gen.materialize import ensure_town, people_at
from world.gen.region import region_spec


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def history(tmp_path, years: int, step: int = 5):
    path = tmp_path / "soak.world"
    game = Game.new(path, "Chronicler", world_seed=21, creation=CreationChoice("origin", "hunter"))
    game.start()
    world = game.world
    towns = []
    for x in range(-1, 2):
        for y in range(-1, 2):
            for i in range(region_spec(world.world_seed, x, y).town_count):
                town = ensure_town(world, x, y, i)
                halls.settle_town(world, town)
                towns.append(town)
    rng = random.Random(21)
    clock.world_tick(world)
    for n in range(years // step):
        world.set_time(world.time + step * 4 * lives.SEASON)
        while clock.run_due(world):
            pass
        town = rng.choice(towns)
        for person in people_at(world, town, exclude=game.player.id):
            lives.catch_up(world, person.id)
        rumours.catch_up(world, town)
        if n % 8 == 7:
            assert check_world(world) == [], f"year {(n + 1) * step}"
    assert check_world(world) == []
    assert not any(world.entity(f).data.get("dissolved") for f in F.ensure_roster(world))
    import systems.world_events as W
    assert len(W.index(world)) < 300, "the sky index keeps only what still matters (phase 4d)"
    # a long-lived world stays quick: one faction season, and the per-turn check once warm (4a minors)
    world.set_time(world.time + lives.SEASON)
    start = time.perf_counter()
    clock.run_due(world)
    season = time.perf_counter() - start
    check_world(world)
    start = time.perf_counter()
    check_world(world)
    check = time.perf_counter() - start
    assert season < 0.1 and check < 0.3, f"season {season * 1000:.0f} ms, check {check * 1000:.0f} ms"
    game.close()
    return path


def test_two_hundred_years_of_history(tmp_path):
    path = history(tmp_path, 200)
    assert path.stat().st_size < 60 * 2 ** 20


@pytest.mark.slow
def test_five_hundred_years_of_history(tmp_path):
    path = history(tmp_path, 500)
    assert path.stat().st_size < 150 * 2 ** 20
