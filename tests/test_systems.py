import pytest

from systems.talk import conversations_with, greet_events
from systems.travel import location_of, routes_from, travel_events
from world.db import World
from world.events import commit
from world.gen.materialize import ensure_town, populate


@pytest.fixture
def setup(tmp_path):
    world = World.create(tmp_path / "t.world", 42)
    town = ensure_town(world, 0, 0, 0)
    player = world.add_entity("person", "Hero", {"is_player": True})
    world.relate(player, town, "located_in")
    yield world, town, player
    world.close()


def test_routes_cover_local_towns_and_four_roads(setup):
    world, town, _ = setup
    routes = routes_from(world, world.entity(town))
    local = world.entity(world.targets(town, "located_in")[0]).data["town_count"] - 1
    assert len(routes) == local + 4
    assert sum("road" in r.label for r in routes) == 4


def test_travel_moves_and_takes_time(setup):
    world, town, player = setup
    north = next(r for r in routes_from(world, world.entity(town)) if "north" in r.label)
    commit(world, travel_events(player, town, north))
    here = location_of(world, player)
    assert (here.data["x"], here.data["y"], here.data["index"]) == north.dest
    assert world.time == north.watches


def test_greeting_is_remembered(setup):
    world, town, player = setup
    npc = populate(world, town)[0].id
    [first] = greet_events(world, player, npc, town)
    assert first.kind == "met"
    commit(world, [first])
    [second] = greet_events(world, player, npc, town)
    assert second.kind == "conversed" and second.data["times"] == 1
    commit(world, [second])
    assert len(conversations_with(world, npc, player)) == 2
    assert world.time == 2
