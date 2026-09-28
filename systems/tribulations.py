"""Tribulations weighed by karma (phase 5f spec 4): how many waves heaven sends, how hard, and of what, and the
minor tribulations of a lesser breakthrough and of a sin grown too heavy; an NPC's fate in the lightning.

A tribulation gathering over the player is person data `tribulation = {realm, minor, strength, waves, wave,
failed}`, played wave by wave (systems/tribulation_waves.py). A great tribulation is still 4d's: its lightning, its
witnesses, its news. A minor one is the player's own.
"""

import systems.demons as D
import systems.karma as K
import systems.lives as lives
import systems.world_clock as world_clock
from systems.facts import make_variant, place_name, record_fact
from world.events import Event, effect, listen
from world.seed import seed_for

WAVE_KINDS = ("lightning", "fire", "demon")
GREAT_REALM, MINOR_REALM, FIRE_REALM = 3, 2, 5
MAX_WAVES = 6
SIN_WAVE = 100             # one wave more for each full 100 of net sin
SIN_STRENGTH, MERIT_STRENGTH = 50, 100
NOTICE_SIN = 150           # net sin at which heaven takes notice, once a year
NPC_DEATH, NPC_DEATH_STEP, NPC_DEATH_MAX = 0.02, 0.001, 0.5


def plan(world, person: int, realm: int, minor: bool) -> dict:
    """The tribulation heaven sends: its waves in order and their strength (spec 4)."""
    bal = K.balance(world, person)
    count = 1 if minor else min(MAX_WAVES, realm - 1)
    count += int(max(0.0, -bal) // SIN_WAVE)
    strength = realm + max(0.0, -bal) / SIN_STRENGTH - (bal / MERIT_STRENGTH if bal > 0 else 0.0)
    waves = ["fire" if realm >= FIRE_REALM and i % 2 else "lightning" for i in range(count)]
    if D.demons(world, person):
        waves.insert(len(waves) // 2, "demon")
    return {"realm": realm, "minor": minor, "strength": round(max(1.0, strength), 2), "waves": waves}


def pending(world, person: int) -> dict | None:
    return world.entity(person).data.get("tribulation")


def gather_events(world, person: int, place, realm: int, minor: bool, why: str) -> list[Event]:
    return [Event("tribulation_gathers", (person,), place, {**plan(world, person, realm, minor), "why": why})]


@effect("tribulation_gathers")
def _gathers(world, event) -> None:
    d = event.data
    world.update_data(event.actors[0], tribulation={"realm": d["realm"], "minor": d["minor"],
                                                    "strength": d["strength"], "waves": d["waves"], "wave": 0,
                                                    "failed": []})


# --- heaven takes notice ------------------------------------------------------------------------------------------

def season_hook(world, n: int) -> list[Event]:
    """A player whose sin outweighs their merit by 150 draws a minor tribulation, at most once a year."""
    player = world.get_meta("player_id")
    entity = world.entity(player) if player is not None else None
    if entity is None or entity.data.get("dead") or entity.data.get("tribulation"):
        return []
    if -K.balance(world, player) < NOTICE_SIN or world.time - entity.data.get("noticed_at", -10 ** 9) < 4 * lives.SEASON:
        return []
    world.update_data(player, noticed_at=world.time)
    from systems.bodies import load_body  # the body comes after the karma in the import graph
    here = next(iter(world.targets(player, "located_in")), None)
    return gather_events(world, player, here, load_body(world, player).realm, True, "notice")


world_clock.SEASON_HOOKS.append(season_hook)


# --- NPCs in the lightning ------------------------------------------------------------------------------------------

def npc_death_chance(world, person: int) -> float:
    return round(min(NPC_DEATH_MAX, NPC_DEATH + NPC_DEATH_STEP * max(0.0, -K.balance(world, person))), 3)


def npc_fate_events(world, person: int, place, season: int | None) -> list[Event]:
    """Whether 4d's lightning over an NPC kills them (one hash of their own)."""
    entity = world.entity(person)
    if entity is None or entity.data.get("dead") or entity.data.get("is_player") or place is None:
        return []
    roll = seed_for(world.world_seed, f"tribulation_fate:{lives.key(entity)}:{season}") / 2 ** 64
    if roll >= npc_death_chance(world, person):
        return []
    return [Event("died", (person, person), place, {"cause": "tribulation", "world": True})]


@listen("died")
def _fell(world, event, event_id: int) -> None:
    if event.data.get("cause") != "tribulation":
        return
    person = event.actors[-1]
    variant = make_variant("fell_to_tribulation", person, None, place=place_name(world, event.place),
                           realm=world.entity(person).data.get("realm", "mortal"))
    record_fact(world, person, "fell_to_tribulation", None, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)
