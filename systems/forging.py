"""Forging and refining (phase 5d spec 3): gear from materials, a grade more on what one holds, and masterworks.

Forging takes a slot, a form and one to three materials: the grade is the materials' mean, rounded down, a grade
more for a master of the form, at most divine. One roll on the form's mastery, strength and the forging level; a
success makes the item and teaches the hand. Refining raises a held piece one grade with a better material, on a
harder roll. A weapon of the treasure grade the player forged may be named once: it becomes a famous weapon.
"""

import math

import systems.famous as FW
import systems.gear as gear
import systems.materials as M
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.body import add_injury
from world.events import Event, effect, listen
from world.seed import rng_for

MIN_MATERIALS, MAX_MATERIALS = 1, 3
FIRST_MASTERY, MASTERY_STEP, MASTER_AT = 0.1, 0.05, 0.8
BOUNDS = (0.1, 0.95)
BURN_SHARE = 0.1           # the worst tenth of failures burns the smith
REFINE_PENALTY, REFINE_CRACK = 0.2, 0.1
MASTERWORK_GRADE = 3
WATCHES = 4                # a day at the forge
FORMS = {"weapon": gear.WEAPON_FORMS, "armour": gear.ARMOURS}


def mastery(world, person: int, form: str) -> float | None:
    return (world.entity(person).data.get("forge_mastery") or {}).get(form)


def level(world, person: int) -> int:
    return int(math.floor(math.sqrt(world.entity(person).data.get("forge_xp", 0) / 10)))


def chance(world, person: int, form: str) -> float:
    strength = load_body(world, person).physique.get("strength", 10)
    raw = 0.35 + 0.4 * (mastery(world, person, form) or FIRST_MASTERY) + 0.03 * (strength - 10) \
        + 0.05 * level(world, person)
    return max(BOUNDS[0], min(BOUNDS[1], raw))


def _learn(world, person: int, form: str, grade: int) -> None:
    masteries = dict(world.entity(person).data.get("forge_mastery") or {})
    masteries[form] = round(min(1.0, (masteries.get(form) or FIRST_MASTERY) + MASTERY_STEP), 3)
    world.update_data(person, forge_mastery=masteries,
                      forge_xp=world.entity(person).data.get("forge_xp", 0) + grade + 1)


def _burn(world, person: int) -> None:
    body = load_body(world, person)
    add_injury(body, "right arm", "burn", 2, world.time, "a forge's fire")
    save_body(world, person, body)


def _materials_block(world, person: int, items) -> str | None:
    if not MIN_MATERIALS <= len(items) <= MAX_MATERIALS or len(set(items)) != len(items):
        return f"Put {MIN_MATERIALS} to {MAX_MATERIALS} materials on the anvil."
    owned = set(world.targets(person, "owns"))
    if any(i not in owned or M.material_info(world.entity(i)) is None for i in items):
        return "You have no such materials."
    return None


# --- forging -------------------------------------------------------------------------------------------------

def grade_of(world, person: int, form: str, items) -> int:
    grades = [M.material_info(world.entity(i))[1] for i in items]
    bonus = 1 if (mastery(world, person, form) or 0.0) >= MASTER_AT else 0
    return min(4, sum(grades) // len(grades) + bonus)


def forge_block(world, person: int, place, slot: str, form: str, items) -> str | None:
    if form not in FORMS.get(slot, ()):
        return "Nothing of that shape is forged."
    return _materials_block(world, person, items) or M.forge_block(world, person, place)


def forge_events(world, person: int, place, slot: str, form: str, items) -> list[Event]:
    odds = chance(world, person, form)
    roll = rng_for(world.world_seed, f"forge:{person}:{world.time}").random()
    return [Event("forged", (person,), place, {
        "slot": slot, "form": form, "materials": list(items), "grade": grade_of(world, person, form, items),
        "success": roll < odds, "burned": roll > 1 - (1 - odds) * BURN_SHARE, "rent": M.rent(world, person, place)})]


@effect("forged")
def _forged(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["rent"])
    M.spend(world, person, d["materials"])
    from systems.time import advance
    advance(world, WATCHES)
    if d["success"]:
        item = gear.make_item(world, d["slot"], d["form"], d["grade"], person, "forged", maker=person,
                              forged_by=person)
        world.update_data(person, last_forged=item)
        _learn(world, person, d["form"], d["grade"])
    elif d["burned"]:
        _burn(world, person)


# --- refining -------------------------------------------------------------------------------------------------

def refine_block(world, person: int, place, item_id, material_id) -> str | None:
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item.kind != "gear" or item_id not in world.targets(person, "owns"):
        return "You hold no such piece."
    if item.data.get("broken"):
        return "A broken piece is past refining."
    if item.data["grade"] >= 4:
        return "Nothing is finer than divine."
    why = _materials_block(world, person, [material_id])
    if why:
        return why
    if M.material_info(world.entity(material_id))[1] < item.data["grade"] + 1:
        return "Only a finer material lifts a piece a grade."
    return M.forge_block(world, person, place)


def refine_events(world, person: int, place, item_id: int, material_id: int) -> list[Event]:
    item = world.entity(item_id)
    odds = max(BOUNDS[0], chance(world, person, item.data["form"]) - REFINE_PENALTY)
    roll = rng_for(world.world_seed, f"refine_gear:{person}:{item_id}:{world.time}").random()
    return [Event("gear_refined", (person,), place, {
        "item": item_id, "material": material_id, "success": roll < odds, "grade": item.data["grade"] + 1,
        "cracked": roll > 1 - (1 - odds) * REFINE_CRACK, "rent": M.rent(world, person, place)})]


@effect("gear_refined")
def _refined(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["rent"])
    M.spend(world, person, [d["material"]])
    from systems.time import advance
    advance(world, WATCHES)
    item = world.entity(d["item"])
    if d["success"]:
        world.update_data(item.id, grade=d["grade"])
        if not item.data.get("famous"):  # a plain piece is called by its grade; a famous one keeps its name
            world.rename(item.id, gear.gear_name(item.data["slot"], item.data["form"], d["grade"]))
        _learn(world, person, item.data["form"], d["grade"])
    elif d["cracked"]:
        world.update_data(item.id, broken=True)


# --- masterworks ------------------------------------------------------------------------------------------------

def masterwork_block(world, person: int, item_id) -> str | None:
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item.kind != "gear" or item_id not in world.targets(person, "owns"):
        return "You hold no such piece."
    if item.data["slot"] != "weapon" or item.data.get("forged_by") != person:
        return "Only a weapon of your own forging can be named by you."
    if item.data.get("famous"):
        return "It has a name already."
    if item.data["grade"] < MASTERWORK_GRADE or item.data.get("broken"):
        return "Only a treasure is worth a name."
    return None


def names_for(world, item_id: int) -> list[str]:
    """Three names the smith might give their masterwork, none a famous weapon's already (seeded)."""
    item = world.entity(item_id)
    used = {world.entity(i).name for i in FW.famous_weapons(world)}
    rng = rng_for(world.world_seed, f"masterwork:{item_id}")
    out: list[str] = []
    for _ in range(40):
        name = f"the {rng.choice(FW.NAMES)} {FW.FORM_WORDS[item.data['form']]}"
        if name not in used and name not in out:
            out.append(name)
        if len(out) == 3:
            break
    return out


def masterwork_events(world, person: int, item_id: int, name: str, place) -> list[Event]:
    return [Event("masterwork_named", (person,), place, {"item": item_id, "name": name})]


@effect("masterwork_named")
def _named(world, event) -> None:
    person, d = event.actors[0], event.data
    world.rename(d["item"], d["name"])
    world.update_data(d["item"], famous=True)
    world.set_meta("famous_weapons", FW.famous_weapons(world) + [d["item"]])


@listen("masterwork_named")
def _legend(world, event, event_id: int) -> None:
    person, item = event.actors[0], event.data["item"]
    variant = make_variant("blade_legend", item, person, place=place_name(world, event.place))
    variant.update(legend=f"forged by {world.entity(person).name}")
    record_fact(world, item, "blade_legend", person, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)
