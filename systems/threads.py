"""Karmic threads (phase 5f spec 3): the people a life is tied to, saved or wronged, and the road that brings them
back across it.

A thread is `{whom, kind, weight, since}` in the karma's `threads`, at most twelve. Those owed to the player repay
them when fate brings them onto the road; those the player wronged stand in it, to be paid amends or fought. A
thread ends when either one dies.
"""

import systems.encounters as encounters
import systems.karma as K
from systems.beliefs import home_of
from systems.kin import kin_of
from systems.realms import realm_index
from world.events import Event, effect, listen
from world.gen.materialize import region_of
from world.seed import rng_for

OWED_TO_YOU = {"spared": 2, "healed": 1, "freed": 3}
OWED_BY_YOU = {"robbed": 1, "crippled": 2, "bereaved": 3, "accused": 2}
MAX_THREADS, MAX_WEIGHT = 12, 3
FATE_RANGE, FATE_CHANCE = 3, 0.05   # regions from their home; a journey's chance per weight
REPAY = 20                          # silver x weight x (realm + 1)
AMENDS, AMENDS_MERIT = 50, 5        # silver x weight; the merit of amends paid
BEREAVED_KIN = 2                    # the kin of the one killed who take up the thread


def threads(world, person: int) -> list[dict]:
    return list(K.karma_of(world, person)["threads"])


def add_thread(world, person: int, whom: int, kind: str, weight: int | None = None) -> None:
    found = threads(world, person)
    weight = weight or {**OWED_TO_YOU, **OWED_BY_YOU}[kind]
    same = next((t for t in found if t["whom"] == whom and t["kind"] == kind), None)
    if same is not None:
        same["weight"] = min(MAX_WEIGHT, same["weight"] + weight)
    else:
        found.append({"whom": whom, "kind": kind, "weight": min(MAX_WEIGHT, weight), "since": world.time})
        if len(found) > MAX_THREADS:
            found.remove(min(found, key=lambda t: (t["weight"], -t["since"])))
    K.write(world, person, threads=found)


def cut(world, person: int, whom: int, kind: str | None = None) -> None:
    K.write(world, person, threads=[t for t in threads(world, person)
                                    if not (t["whom"] == whom and (kind is None or t["kind"] == kind))])


def owed(thread: dict) -> bool:
    """Whether the other one owes the player (else the player owes them)."""
    return thread["kind"] in OWED_TO_YOU


def _player(world) -> int | None:
    return world.get_meta("player_id")


# --- gathered ---------------------------------------------------------------------------------------------------

@listen("duel_ended")
def _from_duel(world, event, event_id: int) -> None:
    d, (player, foe) = event.data, event.actors
    if d.get("result") != "won" or d.get("by") != "player" or world.entity(foe).data.get("beast"):
        return
    kind = {"spare": "spared", "rob": "robbed", "cripple": "crippled"}.get(d.get("verdict"))
    if kind is not None:
        add_thread(world, player, foe, kind)


@listen("healed")
def _from_healing(world, event, event_id: int) -> None:
    if event.actors[0] == _player(world) and len(event.actors) > 1:
        add_thread(world, event.actors[0], event.actors[1], "healed")


@listen("worms_killed")
def _from_freeing(world, event, event_id: int) -> None:
    if event.actors[0] == _player(world):
        add_thread(world, event.actors[0], event.actors[1], "freed")


@listen("false_accusation")
def _from_accusing(world, event, event_id: int) -> None:
    if event.actors[0] == _player(world):
        add_thread(world, event.actors[0], event.actors[1], "accused")


@listen("died")
def _from_death(world, event, event_id: int) -> None:
    """A thread ends with the one it ties to; a killing ties the player to the dead one's kin."""
    killer, victim, player = event.actors[0], event.actors[-1], _player(world)
    if player is None or victim == player or world.entity(player) is None:
        return
    if any(t["whom"] == victim for t in threads(world, player)):
        cut(world, player, victim)
    if killer == player and not world.entity(victim).data.get("beast"):
        for kin, _ in kin_of(world, victim)[:BEREAVED_KIN]:
            if kin != player:
                add_thread(world, player, kin, "bereaved")


# --- fated meetings on the road ---------------------------------------------------------------------------------

def fated_events(world, player: int, town, rng) -> list[Event] | None:
    """The heaviest thread within reach may cross the road (a 2b road hook; its own seeded draw)."""
    found = sorted(threads(world, player), key=lambda t: (-t["weight"], t["since"]))
    if not found:
        return None
    here = region_of(world, town.id).data
    draw = rng_for(world.world_seed, f"fated:{player}:{world.time}")
    for thread in found:
        other = world.entity(thread["whom"])
        home = home_of(world, thread["whom"]) if other is not None and not other.data.get("dead") else None
        if home is None or home == town.id:
            continue
        there = region_of(world, home).data
        if max(abs(there["x"] - here["x"]), abs(there["y"] - here["y"])) > FATE_RANGE:
            continue
        if draw.random() >= FATE_CHANCE * thread["weight"]:
            return None
        if owed(thread):
            realm = realm_index(other.data.get("realm", "mortal"))
            return [Event("fated_repaid", (player, thread["whom"]), town.id,
                          {"kind": thread["kind"], "weight": thread["weight"],
                           "silver": REPAY * thread["weight"] * (realm + 1)})]
        return encounters.encounter_events(player, thread["whom"], town.id, "wronged", AMENDS * thread["weight"],
                                           {"thread": thread["kind"]})
    return None


encounters.ROAD_HOOKS.append(fated_events)


@effect("fated_repaid")
def _repaid(world, event) -> None:
    player, whom = event.actors
    world.update_data(player, silver=world.entity(player).data.get("silver", 0) + event.data["silver"])
    cut(world, player, whom, event.data["kind"])


@listen("encounter_resolved")
def _amends(world, event, event_id: int) -> None:
    """Amends paid to one the player wronged spend the thread, and heaven counts it."""
    if event.data.get("kind") != "wronged" or event.data.get("how") != "paid":
        return
    player, whom = event.actors
    for t in [t for t in threads(world, player) if t["whom"] == whom and not owed(t)]:
        cut(world, player, whom, t["kind"])
    K.add(world, player, merit=AMENDS_MERIT)
