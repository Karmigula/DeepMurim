"""A treasure light (phase 4d spec 5): a pillar of light marks where a treasure has been born. A race."""

from systems.races import race_stage, race_start_data
from world.seed import rng_for


def start_data(world, site: int, n: int, rng) -> dict:
    import systems.secret_realms as SR  # a light may mark a realm's gate, not a treasure (phase 4f spec 4.6)
    cracked = rng_for(world.world_seed, f"crack:{site}:{n}").random() < SR.CRACK_CHANCE
    return {**race_start_data("treasure_light", rng), "cracked": cracked}


def on_stage(world, occurrence, stage: str) -> list:
    return race_stage(world, occurrence, stage)
