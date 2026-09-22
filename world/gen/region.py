from dataclasses import dataclass

from world.gen.names import REGION_NOUN, place_name
from world.seed import rng_for

TERRAINS = ("plains", "mountains", "river", "forest", "marsh", "hills")


@dataclass(frozen=True)
class RegionSpec:
    x: int
    y: int
    name: str
    terrain: str
    town_count: int


def region_path(x: int, y: int) -> str:
    return f"region:{x},{y}"


def region_spec(world_seed: int, x: int, y: int) -> RegionSpec:
    rng = rng_for(world_seed, region_path(x, y))
    terrain = rng.choice(TERRAINS)
    return RegionSpec(x, y, "the " + place_name(rng, REGION_NOUN[terrain]), terrain, rng.randint(1, 3))
