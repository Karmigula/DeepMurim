"""Sealed in (phase 4f spec 4.4): when the gate closes with the player inside.

An opening the player entered closes from what really happened: whoever is still inside is sealed,
the player too. Sealed, the player may cultivate a season at a time in the dense qi, search the
floors for another way out, or let their heir carry on (their tale ends: plan ruling 17). When the
realm opens again, the sealed player walks on through the open gate.
"""

import systems.lives as lives
import systems.realm_gates as G
from systems.bodies import load_body, save_body
from systems.factions import memberships
from systems.membership import set_membership
from systems.realms import add_energy
from systems.time import advance
from systems.tournaments import alive
from world.events import Event, effect
from world.seed import rng_for

SEARCH_BASE, SEARCH_PER_COMPREHENSION, SEARCH_BOUNDS = 0.05, 0.01, (0.02, 0.4)
SEASON_GROWTH = 0.75  # energy-years: three times a season's meditation


def sealed_realm(world, player: int) -> int | None:
    found = world.entity(player).data.get("sealed_in")
    return found["realm"] if found else None


def inside_closing_events(world, occurrence) -> list[Event]:
    """The gate closes on an opening the player entered: fates from what happened, not a roll (spec §4.4)."""
    t = occurrence.data["data"]
    if t["closed"]:
        return []
    realm = t["realm"]
    fates = {}
    for person in dict.fromkeys(t["delvers"] + t["entered"]):
        if not alive(world, person):
            fates[str(person)] = "dead"
        elif world.targets(person, "located_in") == [realm]:
            fates[str(person)] = "sealed"
    return [Event("realm_closed", (), occurrence.data["place"], {"occurrence": occurrence.id, "realm": realm,
                                                                "fates": fates, "loot": {}, "inherited": None})]


def unseal_events(world, occurrence) -> list[Event]:
    """The realm opens again: the sealed player is free to walk on (their place inside is where they left it)."""
    realm = world.entity(occurrence.data["data"]["realm"])
    player = world.get_meta("player_id")
    if player not in realm.data["sealed"] or not alive(world, player):
        return []
    return [Event("unsealed", (player,), realm.id, {"occurrence": occurrence.id, "realm": realm.id})]


def _free(world, player: int, realm: int) -> None:
    world.update_data(player, sealed_in=None)
    entity = world.entity(realm)
    world.update_data(realm, sealed=[p for p in entity.data["sealed"] if p != player])


@effect("unsealed")
def _unsealed(world, event) -> None:
    player, d = event.actors[0], event.data
    _free(world, player, d["realm"])
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "entered": t["entered"] + [player]})


def season_events(world, player: int) -> list[Event]:
    realm = sealed_realm(world, player)
    if realm is None or world.entity(realm).data["period"] is None:
        return []
    return [Event("sealed_season", (player,), realm, {"years": SEASON_GROWTH})]


@effect("sealed_season")
def _season(world, event) -> None:
    body = load_body(world, event.actors[0])
    add_energy(body, event.data["years"])
    save_body(world, event.actors[0], body)
    advance(world, lives.SEASON)


def search_events(world, player: int) -> list[Event]:
    realm = sealed_realm(world, player)
    if realm is None:
        return []
    comprehension = load_body(world, player).physique["comprehension"]
    chance = min(SEARCH_BOUNDS[1], max(SEARCH_BOUNDS[0], SEARCH_BASE + SEARCH_PER_COMPREHENSION * comprehension))
    found = rng_for(world.world_seed, f"search:{realm}:{player}:{world.time}").random() < chance
    return [Event("exit_searched", (player,), realm, {"realm": realm, "found": found})]


@effect("exit_searched")
def _searched(world, event) -> None:
    player, d = event.actors[0], event.data
    advance(world, lives.SEASON)
    if d["found"]:
        _free(world, player, d["realm"])
        world.unrelate(player, "located_in")
        world.relate(player, world.entity(d["realm"]).data["gate"], "located_in")
        world.update_data(player, delve=None)


def lost_events(world, player: int) -> list[Event]:
    """Let the heir carry on: the sealed one's tale ends here (plan ruling 17)."""
    from systems.mortality import death_events
    if sealed_realm(world, player) is None:
        return []
    return death_events(world, player, "sealed", None)
