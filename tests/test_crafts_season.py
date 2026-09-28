import gc
import time
from pathlib import Path

import pytest

import systems.craft_world as CW
import systems.encounters as encounters
import systems.formations as FM
import systems.lives as lives
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice
from systems.duel import fighter_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=100000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def average(fn, n=10) -> float:
    """CPU time per call, averaged: Windows' CPU clock ticks in 15.6 ms steps (4e ruling 19)."""
    fn()
    gc.collect()
    start = time.process_time()
    for _ in range(n):
        fn()
    return (time.process_time() - start) / n


def test_the_fork_guide_covers_the_crafts():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("materials.toml", "formations.toml", "forge_mastery", "knows_formation", "formations", "flags",
                 "craft_skill", "commissions", "`meet`", "check_crafts"):
        assert word in guide, word


class _Undo(Exception):
    pass


def test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5cs(game, monkeypatch):
    """The same 200 people live the same season again and again, rolled back, with and without the craft agenda."""
    from tests.test_alchemy_world_season import crowd
    world = game.world
    everything = list(lives.AGENDAS)
    before = [a for a in everything if a is not CW.season_events]
    people = crowd(world, game.place.id, "crafts")
    world.set_time(world.time + lives.SEASON)

    def season(agendas) -> float:
        monkeypatch.setattr(lives, "AGENDAS", agendas)
        gc.collect()
        start = time.process_time()
        try:
            with world.transaction():
                for person in people:
                    lives.catch_up(world, person)
                spent = time.process_time() - start
                raise _Undo
        except _Undo:
            return spent

    timings = {"5c": [], "5d": []}
    for n in range(20):  # ten a side: one side's cost sits near the bar, and the machine is noisy (5e minors)
        which = "5c" if n % 2 == 0 else "5d"
        timings[which].append(season(before if which == "5c" else everything))
    total = {k: sum(sorted(v)[:5]) for k, v in timings.items()}  # the fastest five of ten: load only slows (5e minors)
    assert total["5d"] <= 1.10 * total["5c"] + 0.016, timings


def test_a_fighter_inside_an_array_is_quick_to_weigh(game):
    world, me = game.world, game.player.id
    plain = average(lambda: fighter_for(world, me, None), n=50)
    FM.place_formation(world, game.place.id, "killing", me, 1.0)
    FM.place_formation(world, game.place.id, "confusion", me, 1.0)
    assert average(lambda: fighter_for(world, me, None), n=50) <= 1.10 * plain + 0.0003


def test_the_crafts_anvil_and_meet_menus_are_quick(game):
    import systems.materials as M
    world, me = game.world, game.player.id
    for name in ("iron ingot", "black steel", "spirit iron"):
        M.make_material(world, name, me)
    for key in FM.PATTERNS:
        FM.learn(world, me, key)
    FM.add_flags(world, me, 50)
    for verb in ("crafts", "anvil", "smith"):
        assert average(lambda: game.perform(Action(verb))) < 0.02, verb
