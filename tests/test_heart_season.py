import gc
import time
from pathlib import Path

import pytest

import systems.demons as D
import systems.encounters as encounters
import systems.gear as gear
import systems.heart as HT
import systems.heart_world as HW
import systems.lives as lives
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice
from systems.duel import fighter_for
from systems.techniques import martial_arts
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
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


def test_the_fork_guide_covers_the_heart():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("heart_deeds.toml", "`heart = {steady", "steady", "lean", "demons", "daos", "oaths", "returned_to_origin",
                 "kills", "spirit", "mad_until", "check_heart", "check_spirits"):
        assert word in guide, word


class _Undo(Exception):
    pass


def test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5ds(game, monkeypatch):
    """The same 200 people live the same season again and again, rolled back, with and without the heart agenda."""
    from tests.test_alchemy_world_season import crowd
    world = game.world
    everything = list(lives.AGENDAS)
    before = [a for a in everything if a is not HW.season_events]
    people = crowd(world, game.place.id, "heart")
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

    timings = {"5d": [], "5e": []}
    for n in range(20):  # ten a side: one side's cost sits near the bar, and the machine is noisy (5e minors)
        which = "5d" if n % 2 == 0 else "5e"
        timings[which].append(season(before if which == "5d" else everything))
    total = {k: sum(sorted(v)[:5]) for k, v in timings.items()}  # the fastest five of ten: load only slows (5e minors)
    assert total["5e"] <= 1.10 * total["5d"] + 0.016, timings


def test_a_fighter_with_a_dao_and_a_spirit_is_quick_to_weigh(game):
    world, me, here = game.world, game.player.id, game.place.id
    art = martial_arts(world, me)[0].technique.id
    plain = average(lambda: fighter_for(world, me, art), n=50)
    HT.write(world, me, daos={"spear": 0.6})
    blade = gear.make_item(world, "weapon", "spear", 2, me, "bought")
    world.update_data(blade, spirit={"nature": "loyal", "bond": 0.5, "master": me, "known_by": [me]})
    commit(world, gear.wield_events(world, me, blade, here))
    assert average(lambda: fighter_for(world, me, art), n=50) <= 1.10 * plain + 0.0003


def test_the_heart_page_and_the_oath_menu_are_quick(game):
    world, me = game.world, game.player.id
    for n in range(5):
        D.add_demon(world, me, "grudge", n + 100, 2)
    HT.write(world, me, daos={"spear": 0.5, "fire": 0.2, "yang": 0.9})
    for verb in ("heart", "oath_menu"):
        assert average(lambda: game.perform(Action(verb))) < 0.02, verb
