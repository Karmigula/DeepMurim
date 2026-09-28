import gc
import time
from pathlib import Path

import pytest

import systems.encounters as encounters
import systems.karma_world as KW
import systems.lives as lives
import systems.threads as TH
import systems.tribulations as TR
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice
from world.events import Event, commit


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


def test_the_fork_guide_covers_karma():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("karma_deeds.toml", "`karma = {merit", "threads", "ROAD_HOOKS", "`tribulation = {",
                 "tribulation_waves", "tribulation\"", "struck_down", "alms", "check_karma"):
        assert word in guide, word


class _Undo(Exception):
    pass


def test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5es(game, monkeypatch):
    """The same 200 people live the same season again and again, rolled back, with and without the karma agenda."""
    from tests.test_alchemy_world_season import crowd
    world = game.world
    everything = list(lives.AGENDAS)
    before = [a for a in everything if a is not KW.season_events]
    people = crowd(world, game.place.id, "karma")
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

    timings = {"5e": [], "5f": []}
    for n in range(20):  # ten a side: one side's cost sits near the bar, and the machine is noisy (5e minors)
        which = "5e" if n % 2 == 0 else "5f"
        timings[which].append(season(before if which == "5e" else everything))
    total = {k: sum(sorted(v)[:5]) for k, v in timings.items()}  # the fastest five of ten: load only slows
    assert total["5f"] <= 1.10 * total["5e"] + 0.016, timings


def test_a_journey_with_twelve_threads_is_quick(game, monkeypatch):
    world, me = game.world, game.player.id
    from world.gen.materialize import ensure_town
    import systems.travel as travel
    town = world.entity(ensure_town(world, *travel.routes_from(world, game.place)[0].dest))
    plain = average(lambda: encounters.road_encounter_events(world, me, town), n=50)
    for n in range(12):
        pid = world.add_entity("person", f"Thread {n}", {"occupation": "tea seller", "realm": "mortal", "age": 30})
        world.relate(pid, game.place.id, "located_in")
        TH.add_thread(world, me, pid, "robbed")
    monkeypatch.setattr(TH, "FATE_CHANCE", 0.0)  # every thread weighed, none met
    assert average(lambda: encounters.road_encounter_events(world, me, town), n=50) <= 1.10 * plain + 0.0003


def test_the_tribulation_scene_and_the_temple_are_quick(game):
    world, me = game.world, game.player.id
    commit(world, TR.gather_events(world, me, game.place.id, 6, False, "breakthrough"))
    assert average(lambda: game.perform(Action("look"))) < 0.02
    commit(world, [Event("tribulation_passed", (me,), game.place.id,
                         {"realm": 6, "minor": False, "outcome": "scarred", "died": False})])
    assert average(lambda: game.perform(Action("temple"))) < 0.02
