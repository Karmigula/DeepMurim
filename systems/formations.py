"""Formations (phase 5d spec 4): patterns learnt and mastered, laid with flags where one stands.

A pattern (`systems/data/formations.toml`) is known through a `knows_formation` relation to the world's pattern
entity (`formation:{key}`), whose value is its mastery; the formation level grows with what is laid. Patterns come
from manuals (items), and now and then from passing an ancient array in a secret realm. Flags are one item that
counts them. Laying spends the flags on one roll; what is laid lives on the place (`formations`), until the next
dawn for a battle array, a month for concealment, a season for a seclusion ward, a year for a sect's defences.
What each does is `systems/arrays.py`.
"""

import math
import tomllib
from pathlib import Path

from systems.bodies import load_body
from world.body import WATCHES_PER_DAY
from world.events import Event, effect, listen
from world.seed import rng_for

PATTERNS = tomllib.loads((Path(__file__).parent / "data" / "formations.toml").read_text(encoding="utf-8"))
FIRST_MASTERY, MASTERY_STEP = 0.1, 0.05
BOUNDS = (0.1, 0.95)
MANUAL_PRICE = 100         # silver x difficulty squared
FLAG_PRICE = 20
TRIAL_LEVEL = 0.05         # a secret realm's formation trial is easier by this a formation level
TRIAL_TEACHES = 0.25       # an ancient array passed now and then teaches a pattern
WATCHES = 2                # laying a formation takes half a day


# --- patterns as knowledge ------------------------------------------------------------------------------------

def pattern_entity(world, key: str) -> int:
    path = f"formation:{key}"
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    return world.add_entity("formation", PATTERNS[key]["name"], {"key": key, **PATTERNS[key]}, path)


def known(world, person: int) -> dict[str, float]:
    """{pattern key: mastery} for what this person knows."""
    return {world.entity(p).data["key"]: value for p, value, _ in world.relations_from(person, "knows_formation")}


def mastery(world, person: int, key: str) -> float | None:
    return known(world, person).get(key)


def learn(world, person: int, key: str, value: float = FIRST_MASTERY) -> None:
    if mastery(world, person, key) is None:
        world.relate(person, pattern_entity(world, key), "knows_formation", value)


def level(world, person: int) -> int:
    return int(math.floor(math.sqrt(world.entity(person).data.get("formation_xp", 0) / 10)))


# --- manuals -----------------------------------------------------------------------------------------------------

def manual_price(key: str) -> int:
    return MANUAL_PRICE * PATTERNS[key]["difficulty"] ** 2


def make_manual(world, owner: int, key: str, how: str) -> int:
    item = world.add_entity("formation_manual", f"a manual of {PATTERNS[key]['name']}", {"pattern": key, "how": how})
    world.relate(owner, item, "owns")
    return item


def manuals_of(world, person: int) -> list:
    return [e for e in (world.entity(i) for i in world.targets(person, "owns"))
            if e is not None and e.kind == "formation_manual"]


def study_block(world, person: int, item_id) -> str | None:
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item.kind != "formation_manual" or item_id not in world.targets(person, "owns"):
        return "You have no such manual."
    if mastery(world, person, item.data["pattern"]) is not None:
        return "You know that pattern already."
    return None


def study_events(world, person: int, item_id: int, place) -> list[Event]:
    return [Event("formation_studied", (person,), place, {"item": item_id,
                                                          "pattern": world.entity(item_id).data["pattern"]})]


@effect("formation_studied")
def _studied(world, event) -> None:
    learn(world, event.actors[0], event.data["pattern"])


# --- flags -------------------------------------------------------------------------------------------------------

def flags_item(world, person: int):
    return next((e for e in (world.entity(i) for i in world.targets(person, "owns"))
                 if e is not None and e.kind == "flags"), None)


def flags_of(world, person: int) -> int:
    found = flags_item(world, person)
    return found.data["count"] if found is not None else 0


def add_flags(world, person: int, count: int) -> None:
    found = flags_item(world, person)
    if found is not None:
        world.update_data(found.id, count=found.data["count"] + count)
        return
    item = world.add_entity("flags", "formation flags", {"count": count})
    world.relate(person, item, "owns")


def spend_flags(world, person: int, count: int) -> None:
    found = flags_item(world, person)
    left = found.data["count"] - count
    if left > 0:
        world.update_data(found.id, count=left)
    else:
        world.unrelate(person, "owns", found.id)
        world.update_data(found.id, count=0, used=True)


# --- laying ------------------------------------------------------------------------------------------------------

def chance(world, person: int, key: str) -> float:
    wit = load_body(world, person).physique.get("comprehension", 10)
    raw = 0.3 + 0.4 * (mastery(world, person, key) or 0.0) + 0.03 * (wit - 10) + 0.05 * level(world, person) \
        - 0.1 * PATTERNS[key]["difficulty"]
    return max(BOUNDS[0], min(BOUNDS[1], raw))


def until(world, key: str) -> int:
    days = PATTERNS[key]["days"]
    if days:
        return world.time + days * WATCHES_PER_DAY
    return (world.time // WATCHES_PER_DAY + 1) * WATCHES_PER_DAY  # the next dawn


def laid(world, place, key: str | None = None, owner: int | None = None) -> list[dict]:
    """The formations holding at a place now (read, never written)."""
    entity = world.entity(place) if place is not None else None
    if entity is None:
        return []
    return [f for f in entity.data.get("formations") or [] if f["until"] > world.time
            and (key is None or f["pattern"] == key) and (owner is None or f["owner"] == owner)]


def strength(world, place, key: str, owner: int | None = None) -> float:
    """The strongest of this pattern holding here (for this owner), or 0."""
    return max((f["strength"] for f in laid(world, place, key, owner)), default=0.0)


def site_block(world, person: int, key: str, place) -> str | None:
    """Where a pattern may be laid: a sect's defences at a seat of the layer's sect; anything else in a town."""
    entity = world.entity(place)
    if entity is None or entity.kind != "town":
        return "Formations are laid in a town."
    if PATTERNS[key]["use"] == "defence":
        from systems import factions as F
        mine = [f for f, _, d in F.memberships(world, person) if d.get("status", "member") == "member"]
        if not any(world.entity(f).data.get("seat") == place for f in mine):
            return "A sect's defences are laid at the seat of your own sect."
        if key == "heavenly_gate" and not any(world.entity(f).data.get("type") == "player_sect"
                                              and world.entity(f).data.get("seat") == place for f in mine):
            return "Only your own sect's gate takes the Heavenly Gate array."
    return None


def lay_block(world, person: int, key: str, place) -> str | None:
    if key not in PATTERNS or mastery(world, person, key) is None:
        return "You do not know that pattern."
    why = site_block(world, person, key, place)
    if why:
        return why
    if flags_of(world, person) < PATTERNS[key]["flags"]:
        return f"It takes {PATTERNS[key]['flags']} flags."
    return None


def lay_events(world, person: int, key: str, place) -> list[Event]:
    roll = rng_for(world.world_seed, f"lay:{person}:{key}:{world.time}").random()
    skill = mastery(world, person, key)
    return [Event("formation_laid", (person,), place, {
        "pattern": key, "success": roll < chance(world, person, key), "flags": PATTERNS[key]["flags"],
        "strength": round(0.5 + skill / 2, 3), "until": until(world, key)})]


@effect("formation_laid")
def _laid(world, event) -> None:
    person, place, d = event.actors[0], event.place, event.data
    spend_flags(world, person, d["flags"])
    from systems.time import advance
    advance(world, WATCHES)
    if not d["success"]:
        return
    keep = [f for f in laid(world, place) if not (f["pattern"] == d["pattern"] and f["owner"] == person)]
    world.update_data(place, formations=keep + [{"pattern": d["pattern"], "owner": person, "until": d["until"],
                                                  "strength": d["strength"]}])
    world.relate(person, pattern_entity(world, d["pattern"]), "knows_formation",
                 round(min(1.0, mastery(world, person, d["pattern"]) + MASTERY_STEP), 3))
    world.update_data(person, formation_xp=world.entity(person).data.get("formation_xp", 0)
                      + PATTERNS[d["pattern"]]["difficulty"] + 1)


def place_formation(world, place: int, key: str, owner: int, strength_: float) -> None:
    """A formation laid by another's hand (a master's commission, a sect's own ward): no roll, no flags."""
    keep = [f for f in laid(world, place) if not (f["pattern"] == key and f["owner"] == owner)]
    world.update_data(place, formations=keep + [{"pattern": key, "owner": owner, "until": until(world, key),
                                                  "strength": round(strength_, 3)}])


# --- the ancient arrays of secret realms (4f) ---------------------------------------------------------------------

def trial_bonus(world, person: int) -> float:
    return TRIAL_LEVEL * level(world, person)


@listen("trial_attempted")
def _array_teaches(world, event, event_id: int) -> None:
    """An ancient array passed now and then teaches one of its patterns (spec 4)."""
    d, person = event.data, event.actors[0]
    if d.get("trial") != "formation" or not d.get("passed"):
        return
    rng = rng_for(world.world_seed, f"array_teaches:{d['realm']}:{d['floor']}:{d['chamber']}:{person}")
    unknown = sorted(k for k in PATTERNS if mastery(world, person, k) is None)
    if unknown and rng.random() < TRIAL_TEACHES:
        learn(world, person, rng.choice(unknown))
