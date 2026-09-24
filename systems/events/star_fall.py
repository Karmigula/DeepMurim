"""A star fall (phase 4d spec 4.8): a meteor comes down and leaves star iron for whoever gets there. A race."""

from systems.races import race_stage, race_start_data


def start_data(world, site: int, n: int, rng) -> dict:
    return race_start_data("star_fall", rng)


def on_stage(world, occurrence, stage: str) -> list:
    return race_stage(world, occurrence, stage)
