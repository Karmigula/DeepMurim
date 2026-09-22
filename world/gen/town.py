from dataclasses import dataclass

from world.gen.names import SETTLEMENT_SUFFIX, place_name
from world.gen.region import region_path, region_spec
from world.seed import rng_for

KINDS = ("village", "village", "town", "town", "city")
NPC_COUNT = {"village": (2, 4), "town": (3, 6), "city": (5, 8)}


@dataclass(frozen=True)
class TownSpec:
    x: int
    y: int
    index: int
    name: str
    kind: str
    terrain: str
    npc_count: int


def town_path(x: int, y: int, i: int) -> str:
    return f"{region_path(x, y)}/town:{i}"


def town_spec(world_seed: int, x: int, y: int, i: int) -> TownSpec:
    region = region_spec(world_seed, x, y)
    if not 0 <= i < region.town_count:
        raise ValueError(f"region {x},{y} has {region.town_count} towns, not index {i}")
    rng = rng_for(world_seed, town_path(x, y, i))
    kind = rng.choice(KINDS)
    low, high = NPC_COUNT[kind]
    return TownSpec(x, y, i, place_name(rng, SETTLEMENT_SUFFIX[kind]), kind, region.terrain, rng.randint(low, high))
