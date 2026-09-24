"""The beast tide (phase 4d spec 4.5): beasts pour out of the wilds, towns are attacked, the magistrate pays hunters.

Only regions with beasts in them rise (the 2b `BEASTS` terrains). While it is active the
roads are thick with beasts (the `beasts` knob); each town rolls an attack once; and three
beast kills in the region, before the aftermath ends, pay the bounty (plan ruling 8).
"""

import systems.lives as lives
import systems.price_events as price_events  # a module import: price_events loads the world clock, which loads this
import systems.world_events as W
from systems.encounters import BEASTS
from systems.purse import silver_of
from world.events import Event, effect
from world.gen.materialize import people_at
from world.seed import rng_for

ATTACK_CHANCE = 0.3
KILLS_FOR_BOUNTY = 3


def eligible(world, region: int, n: int) -> bool:
    return world.entity(region).data.get("terrain") in BEASTS


def start_data(world, region: int, n: int, rng) -> dict:
    return {"bounty": rng.randint(30, 80), "hunts": {}, "paid": []}


def on_stage(world, occurrence, stage: str) -> list[Event]:
    if stage != "active":
        return []
    d, events = occurrence.data, []
    for town in sorted(t for t in world.sources(d["place"], "located_in") if world.entity(t).kind == "town"):
        rng = rng_for(world.world_seed, f"beast_tide:{occurrence.id}:{town}")
        if rng.random() >= ATTACK_CHANCE:
            continue
        folk = sorted(p.id for p in people_at(world, town) if lives.simulated(p))
        for victim in rng.sample(folk, min(len(folk), rng.randint(1, 3))):
            events.append(Event("died", (victim, victim), town, {"cause": "beasts", "world": True}))
        price_events.shift(world, "town", town, {"herbs": 1.5}, d["active"][1], "beast tide")
    return events


def _tide_over(world, place: int) -> int | None:
    """The beast tide whose hunting season covers this place now, if any."""
    xy = W.place_xy(world, place)
    for row in W.index(world):
        if row[W.TYPE] == "beast_tide" and row[W.ACTIVE_FROM] <= world.time < row[W.OVER_AT] \
                and W.covers(row, place, xy):
            return row[W.ID]
    return None


def hunt_events(world, player: int, place: int) -> list[Event]:
    """A beast the player killed while a tide was up; the third one pays the bounty."""
    occurrence = _tide_over(world, place)
    if occurrence is None:
        return []
    d = world.entity(occurrence).data["data"]
    if player in d["paid"]:
        return []
    kills = d["hunts"].get(str(player), 0) + 1
    events = [Event("beast_hunted", (player,), place, {"occurrence": occurrence, "kills": kills})]
    if kills >= KILLS_FOR_BOUNTY:
        events.append(Event("bounty_paid", (player,), place, {"occurrence": occurrence, "silver": d["bounty"]}))
    return events


@effect("beast_hunted")
def _hunted(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    d = dict(occurrence.data["data"])
    d["hunts"] = {**d["hunts"], str(event.actors[0]): event.data["kills"]}
    world.update_data(occurrence.id, data=d)


@effect("bounty_paid")
def _paid(world, event) -> None:
    player, occurrence = event.actors[0], world.entity(event.data["occurrence"])
    world.update_data(player, silver=silver_of(world, player) + event.data["silver"])
    d = dict(occurrence.data["data"])
    d["paid"] = d["paid"] + [player]
    world.update_data(occurrence.id, data=d)
