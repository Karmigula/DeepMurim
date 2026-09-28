"""Dao resonance (phase 4d spec 4.6): a master's enlightenment makes a town hum; practice there comes twice as fast."""

import systems.lives as lives
from systems.facts import make_variant, place_name, record_fact
from systems.realms import realm_index
from world.gen.materialize import people_at

MASTER_REALM = 3  # First-rate


def _master(world, town: int):
    found = [p for p in people_at(world, town)
             if lives.simulated(p) and realm_index(p.data.get("realm", "mortal")) >= MASTER_REALM]
    return max(found, key=lambda p: (realm_index(p.data["realm"]), -p.id), default=None)


def eligible(world, town: int, n: int) -> bool:
    return _master(world, town) is not None


def start_data(world, town: int, n: int, rng) -> dict | None:
    master = _master(world, town)
    return {"master": master.id} if master is not None else None


def on_stage(world, occurrence, stage: str) -> list:
    if stage != "active":
        return []
    d = occurrence.data
    master, town = world.entity(d["data"]["master"]), d["place"]
    variant = make_variant("enlightened", master.id, None, place=place_name(world, town),
                           realm=master.data.get("realm", "mortal"))
    variant["age"] = int(master.data.get("age", 30))
    record_fact(world, master.id, "enlightened", None, place=town, weight=1.5, variant=variant)
    from systems.heart_world import enlighten  # phase 5e: the enlightened open the dao of their art
    enlighten(world, master.id)
    return []
