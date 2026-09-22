"""Moving between towns: within a region by foot, between regions by road."""

from dataclasses import dataclass

from systems.time import advance
from world.db import Entity, World
from world.events import Event, effect
from world.gen.materialize import ensure_town, region_label, region_of, town_label

DIRECTIONS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
LOCAL_WATCHES = 4   # one day
ROAD_WATCHES = 12   # three days


@dataclass(frozen=True)
class Route:
    label: str
    dest: tuple[int, int, int]
    watches: int


def routes_from(world: World, town: Entity) -> list[Route]:
    x, y, i = town.data["x"], town.data["y"], town.data["index"]
    routes = []
    for j in range(region_of(world, town.id).data["town_count"]):
        if j != i:
            routes.append(Route(f"Walk to {town_label(world, x, y, j)} (1 day)", (x, y, j), LOCAL_WATCHES))
    for name, (dx, dy) in DIRECTIONS.items():
        nx, ny = x + dx, y + dy
        label = f"Take the {name} road to {town_label(world, nx, ny, 0)}, {region_label(world, nx, ny)} (3 days)"
        routes.append(Route(label, (nx, ny, 0), ROAD_WATCHES))
    return routes


def travel_events(traveller: int, origin: int, route: Route) -> list[Event]:
    return [Event("travelled", (traveller,), origin, {"to": list(route.dest), "watches": route.watches})]


def location_of(world: World, entity_id: int) -> Entity:
    return world.entity(world.targets(entity_id, "located_in")[0])


@effect("travelled")
def _arrive(world: World, event: Event) -> None:
    x, y, i = event.data["to"]
    dest = ensure_town(world, x, y, i)
    traveller = event.actors[0]
    world.unrelate(traveller, "located_in")
    world.relate(traveller, dest, "located_in")
    advance(world, event.data["watches"])
