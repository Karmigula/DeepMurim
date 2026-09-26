"""A sect's armoury (phase 5a spec 4.3): a grade table, drawn from by rank, restocked each season.

The table is counts, not items: a drawn weapon or armour is made then, belongs to the sect (`armoury`) and goes
back to the table when returned. Leaving the sect with one is theft.
"""

import systems.gear as gear
import systems.world_clock as world_clock
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from world.events import Event, effect

SEED = {"great": {0: 6, 1: 4, 2: 2, 3: 1}, "other": {0: 4, 1: 2, 2: 1}}
RANK_GRADE = {1: 0, 2: 1, 3: 2}  # rank 1 draws iron, 2 fine, 3 spirit; an elder a treasure, once
ELDER_GRADE = 3
THEFT_WEIGHT = 1.5
GONE = frozenset({"expelled", "deserter", "spy", "released"})  # the statuses of every road out


def seed_of(world, faction: int) -> dict[int, int]:
    return dict(SEED["great" if world.entity(faction).data.get("tier") == "great" else "other"])


def table(world, faction: int) -> dict[int, int]:
    """What the armoury holds now: {grade: count} (the seed until anything is drawn)."""
    found = world.entity(faction).data.get("armoury")
    return {int(k): v for k, v in found.items()} if found is not None else seed_of(world, faction)


def allowed(world, person: int, faction: int) -> int | None:
    found = F.membership(world, person, faction)
    if found is None:
        return None
    rank, data = found
    if data.get("status", "member") != "member" or rank < 1:
        return None
    if data.get("role") in ("elder", "leader") and not world.entity(person).data.get("drew_treasure"):
        return ELDER_GRADE
    return RANK_GRADE.get(min(rank, 3))


def drawn_from(world, person: int, faction: int, slot: str) -> int | None:
    return next((i.id for i in gear.gear_items(world, person)
                 if i.data.get("armoury") == faction and i.data["slot"] == slot), None)


def draw_block(world, person: int, faction: int, slot: str, place: int) -> str | None:
    if world.entity(faction).data.get("seat") != place:
        return "The armoury is at the sect's seat."
    best = allowed(world, person, faction)
    if best is None:
        return "Only a disciple of rank may draw from the armoury."
    if drawn_from(world, person, faction, slot) is not None:
        return "You already hold one from the armoury."
    if not any(table(world, faction).get(g, 0) > 0 for g in range(best + 1)):
        return "The armoury has nothing left for you."
    return None


def draw_events(world, person: int, faction: int, slot: str, place: int, form: str | None = None) -> list[Event]:
    best = allowed(world, person, faction)
    stocked = table(world, faction)
    grade = max(g for g in range(best + 1) if stocked.get(g, 0) > 0)
    if slot == "weapon":
        form = form or gear.best_weapon_form(world, person) or "sword"
    else:
        form = form or "mail"
    return [Event("armoury_drawn", (person,), place, {"faction": faction, "slot": slot, "grade": grade,
                                                       "form": form})]


@effect("armoury_drawn")
def _drawn(world, event) -> None:
    person, d = event.actors[0], event.data
    stocked = table(world, d["faction"])
    stocked[d["grade"]] -= 1
    world.update_data(d["faction"], armoury={str(k): v for k, v in stocked.items()})
    if d["grade"] == ELDER_GRADE:
        world.update_data(person, drew_treasure=True)
    item = gear.make_item(world, d["slot"], d["form"], d["grade"], person, "drawn",
                          maker=d["faction"], armoury=d["faction"])
    world.unrelate(person, gear.SLOTS[d["slot"]])
    world.relate(person, item, gear.SLOTS[d["slot"]])


def return_events(world, person: int, item_id: int, place: int) -> list[Event]:
    return gear.pass_events(world, person, None, item_id, place, "returned") + [
        Event("armoury_returned", (person,), place, {"item": item_id, "faction": world.entity(item_id).data["armoury"]})]


@effect("armoury_returned")
def _returned(world, event) -> None:
    d = event.data
    stocked = table(world, d["faction"])
    grade = world.entity(d["item"]).data["grade"]
    stocked[grade] = min(seed_of(world, d["faction"]).get(grade, 0), stocked.get(grade, 0) + 1)
    world.update_data(d["faction"], armoury={str(k): v for k, v in stocked.items()})
    world.update_data(d["item"], in_armoury=True)


def left_with(world, person: int, faction: int, status: str) -> None:
    """Out of the sect by any road (spec 4.3): a release hands its armoury's gear back; any other road steals it."""
    taken = [i for i in gear.gear_items(world, person) if i.data.get("armoury") == faction
             and i.data.get("claimed_by") is None]
    if not taken:
        return
    if status == "released":
        for item in taken:
            gear._passed(world, Event("gear_passed", (person,), None,
                                      {"item": item.id, "giver": person, "taker": None, "how": "returned"}))
            _returned(world, Event("armoury_returned", (person,), None, {"item": item.id, "faction": faction}))
        return
    for item in taken:
        world.update_data(item.id, claimed_by=faction)
    here = world.targets(person, "located_in")
    place = here[0] if here else None
    variant = make_variant("stole", person, faction, place=place_name(world, place) if place else None)
    record_fact(world, person, "stole", faction, place=place, weight=THEFT_WEIGHT, variant=variant)


def season_hook(world, n: int) -> list:
    """Each season an armoury drawn from gets one more of its lowest grade back, up to its seed."""
    for faction in world.entities_after("faction", "armoury", 0):
        stocked, seed = table(world, faction.id), seed_of(world, faction.id)
        low = min(seed)
        if stocked.get(low, 0) < seed[low]:
            stocked[low] = stocked.get(low, 0) + 1
            world.update_data(faction.id, armoury={str(k): v for k, v in stocked.items()})
    return []


world_clock.SEASON_HOOKS.append(season_hook)
