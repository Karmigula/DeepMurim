"""Deterministic randomness keyed by a path through the world.

The same (world_seed, path) gives the same numbers in every process and every
run, which is what lets an unvisited town exist without being stored.
"""

import hashlib
import random


def seed_for(world_seed: int, path: str) -> int:
    digest = hashlib.blake2b(f"{world_seed}/{path}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def rng_for(world_seed: int, path: str) -> random.Random:
    return random.Random(seed_for(world_seed, path))
