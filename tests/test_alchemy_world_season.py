import gc
import time
from pathlib import Path

import pytest

import systems.control as C
import systems.encounters as encounters
import systems.lives as lives
import systems.npc_alchemy as N
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice

JOBS = ("herbalist", "wandering swordsman", "tea seller", "innkeeper")


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


def test_the_fork_guide_covers_the_alchemy_world():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("pill_hall", "garden", "guild_rank", "scroll", "secret_recipes.toml", "physician", "doctors_seen",
                 "CURE_HOOKS", "bound_to", "`bound`", "pills", "check_alchemy_world"):
        assert word in guide, word


def crowd(world, town, tag, n=200):
    """People as a town has them: the world's own occupations and realms, in turn."""
    from world.gen.npc import OCCUPATIONS, REALMS
    out = []
    for i in range(n):
        pid = world.add_entity("person", f"Crowd {tag} {i}", {
            "occupation": OCCUPATIONS[i % len(OCCUPATIONS)], "traits": ["curious"], "age": 30, "silver": 200,
            "realm": REALMS[i % len(REALMS)], "portrait": {"hair": 0, "face": 0, "robe": 0}}, f"test:crowd:{tag}:{i}")
        world.relate(pid, town, "located_in")
        lives.lived_to(world, pid)
        out.append(pid)
    return out


class _Undo(Exception):
    pass


def test_a_season_of_two_hundred_npcs_stays_within_a_tenth_of_5bs(game, monkeypatch):
    """The same 200 people live the same season again and again, each time rolled back, with and without the
    alchemy agendas in turn (5c review: separate crowds and single runs measured only the machine's noise)."""
    world = game.world
    everything = list(lives.AGENDAS)
    before = [a for a in everything if a not in (N.season_events, C.world_events)]
    people = crowd(world, game.place.id, "season")
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

    timings = {"5b": [], "5c": []}
    for n in range(12):
        which = "5b" if n % 2 == 0 else "5c"
        timings[which].append(season(before if which == "5b" else everything))
    total = {k: sum(sorted(v)[:-1]) for k, v in timings.items()}  # the slowest of each dropped
    assert total["5c"] <= 1.10 * total["5b"] + 0.016, timings  # one tick of Windows' CPU clock


def at_the_seat(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.relate(me, sect, "member_of", 2, {"role": "disciple", "hall": 0, "merit": 10000, "status": "member",
                                            "secret": False})
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")


def a_city(world):
    from world.gen.materialize import ensure_town
    from world.gen.region import region_spec
    from world.gen.town import town_spec
    for x in range(-3, 4):
        for y in range(-3, 4):
            for i in range(region_spec(world.world_seed, x, y).town_count):
                if town_spec(world.world_seed, x, y, i).kind == "city":
                    return ensure_town(world, x, y, i)
    raise AssertionError("no city near")


def test_the_hall_guild_and_clinic_menus_are_quick(game):
    import systems.alchemy as A
    world, me = game.world, game.player.id
    at_the_seat(game)
    for verb in ("pill_hall", "clinic", "night"):
        assert average(lambda: game.perform(Action(verb))) < 0.02, verb
    world.unrelate(me, "located_in")
    world.relate(me, a_city(world), "located_in")
    world.update_data(me, guild_rank=3)
    world.relate(me, A.recipe_entity(world, "mending"), "knows_recipe", 0.5)
    assert average(lambda: game.perform(Action("guild"))) < 0.02
