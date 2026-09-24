"""A treasure light (phase 4d spec 5): a pillar of light marks where a treasure has been born. A race."""

from systems.races import race_stage, race_start_data


def start_data(world, site: int, n: int, rng) -> dict:
    return race_start_data("treasure_light", rng)


def on_stage(world, occurrence, stage: str) -> list:
    return race_stage(world, occurrence, stage)
