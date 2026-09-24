"""Trade goods (phase 4c spec 3): what exists, where it is made, and what a pack can hold."""

from systems.bodies import load_body
from world.seed import rng_for

GOODS = {  # good: (base price, weight, category)
    "rice": (2, 2, "staple"), "salt": (4, 2, "staple"), "tea": (8, 1, "luxury"), "wine": (10, 2, "luxury"),
    "iron": (12, 3, "war"), "herbs": (15, 1, "medicine"), "silk": (30, 1, "luxury"), "jade": (80, 1, "luxury"),
}
ORDER = tuple(sorted(GOODS, key=lambda g: (-GOODS[g][0], g)))
PRODUCED, LACKED = 0.6, 1.6
PACK_BASE, PACK_PER_STRENGTH = 20, 2
MULE_CAPACITY, MULE_PRICE = 40, 60


def region_goods(world, region) -> tuple[list[str], list[str]]:
    """The two goods a region makes cheaply and the two it lacks, seeded by the region."""
    picked = rng_for(world.world_seed, f"goods:{region.seed_path}").sample(sorted(GOODS), 4)
    return picked[:2], picked[2:]


def carried(world, person: int) -> dict[str, int]:
    return {g: int(n) for g, n in world.entity(person).data.get("goods", {}).items() if n}


def pack_weight(goods: dict) -> int:
    return sum(GOODS[g][1] * n for g, n in goods.items())


def capacity(world, person: int) -> int:
    strength = load_body(world, person).physique.get("strength", 10)
    mule = MULE_CAPACITY if world.entity(person).data.get("mule") else 0
    return int(PACK_BASE + PACK_PER_STRENGTH * strength) + mule
