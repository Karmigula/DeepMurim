"""Weapons and armour (phase 5a spec 2): grades, gear an NPC carries without it being made, and items with a past.

An NPC's gear is only a seeded grade (`seeded`) until it matters: taken, bought, inherited, looked at, or its
wielder killed by the player. Then `materialize` makes it an item that remembers its maker, its owners and its
deeds. A person wields at most one weapon (`wields`) and wears one armour (`wears`), each an item they own.
"""

from systems import factions as F
from systems.realms import realm_index
from world.events import Event, effect, listen
from world.seed import rng_for

GRADES = ("iron", "fine", "spirit", "treasure", "divine")
GRADE_WORDS = ("iron", "fine steel", "spirit-steel", "treasure", "divine")
POWER = (1.0, 1.15, 1.3, 1.5, 1.8)
ARMOUR_SHARE = (0.10, 0.15, 0.20, 0.25, 0.30)
WEAPON_FORMS = ("sword", "saber", "spear", "staff")
NEAR = {"sword": "saber", "saber": "sword", "spear": "staff", "staff": "spear"}
NEAR_MULT, UNARMED = 0.85, 0.6
ARMOURS = ("robe", "mail", "inner_vest")
ARMOUR_WORDS = {"robe": "padded robe", "mail": "mail vest", "inner_vest": "silk inner vest"}
BREAK_GAP, BREAK_CHANCE = 2, 0.05
MAX_DEEDS = 12
REALM_GRADE = (0, 0, 1, 2, 2, 3, 3, 4)  # by realm index: mortal and third-rate iron ... life-and-death divine
ROLE_GRADE = {"disciple": 0, "keeper": 1, "elder": 2, "leader": 2}
ARMED = frozenset({"keeper", "elder", "leader"})  # those of rank wear armour; others go in cloth
SLOTS = {"weapon": "wields", "armour": "wears"}


# --- what someone carries ----------------------------------------------------------------------------

def seeded(world, person: int) -> dict:
    """What an NPC carries before anyone looks: a weapon grade (its form is their art's) and an armour grade."""
    data = world.entity(person).data
    if data.get("is_player") or data.get("beast"):
        return {"weapon": None, "armour": None}  # the player's own is written at creation
    grade, role_best = REALM_GRADE[min(realm_index(data.get("realm", "mortal")), len(REALM_GRADE) - 1)], None
    for fid, _, d in F.memberships(world, person):
        if d.get("status", "member") != "member" or d.get("role") not in ROLE_GRADE:
            continue
        role_grade = ROLE_GRADE[d["role"]]
        if d["role"] == "leader" and world.entity(fid).data.get("tier") == "great":
            role_grade = 3  # a great sect's master carries a treasure
        grade = max(grade, role_grade)
        role_best = d["role"] if role_best is None or ROLE_GRADE[d["role"]] > ROLE_GRADE[role_best] else role_best
    armour = max(0, grade - 1) if role_best in ARMED else None
    return {"weapon": grade, "armour": armour}


def carried(world, person: int) -> dict:
    """The gear a person carries without an item: their own record once any was made real, else the seeded."""
    data = world.entity(person).data
    return data["gear"] if data.get("gear") is not None else seeded(world, person)


def item_in(world, person: int, slot: str):
    found = world.targets(person, SLOTS[slot])
    return world.entity(found[0]) if found else None


def weapon_of(world, person: int) -> dict | None:
    """{grade, form (None: whatever their art), item, broken}, or None for bare hands."""
    item = item_in(world, person, "weapon")
    if item is not None:
        return {"grade": item.data["grade"], "form": item.data["form"], "item": item.id,
                "broken": bool(item.data.get("broken"))}
    gear = carried(world, person)
    grade = gear.get("weapon")
    return None if grade is None else {"grade": grade, "form": gear.get("form"), "item": None, "broken": False}


def armour_of(world, person: int) -> dict | None:
    item = item_in(world, person, "armour")
    if item is not None:
        return {"grade": item.data["grade"], "item": item.id}
    grade = carried(world, person).get("armour")
    return None if grade is None else {"grade": grade, "item": None}


def weapon_mult(world, person: int, form: str) -> float:
    """How a weapon art fares with what they hold (spec 2.2); arts of the hand need nothing."""
    if form not in WEAPON_FORMS:
        return 1.0
    w = weapon_of(world, person)
    if w is None or w["broken"]:
        return UNARMED
    if w["form"] is None or w["form"] == form:
        return POWER[w["grade"]]
    if NEAR.get(w["form"]) == form:
        return round(POWER[w["grade"]] * NEAR_MULT, 4)
    return UNARMED


def armour_share(world, person: int) -> float:
    a = armour_of(world, person)
    return 0.0 if a is None else ARMOUR_SHARE[a["grade"]]


def fighting(world, person: int, form: str) -> tuple[float, int | None]:
    """(weapon_mult, weapon_grade) for a fighter of this form, from one look at what they hold."""
    if form not in WEAPON_FORMS:
        return 1.0, None
    w = weapon_of(world, person)
    if w is None or w["broken"]:
        return UNARMED, None
    if w["form"] is None or w["form"] == form:
        return POWER[w["grade"]], w["grade"]
    if NEAR.get(w["form"]) == form:
        return round(POWER[w["grade"]] * NEAR_MULT, 4), w["grade"]
    return UNARMED, w["grade"]


def weapon_grade(world, person: int, form: str) -> int | None:
    """The grade of the weapon a weapon art strikes with, for breakage; None with bare hands or a hand art."""
    if form not in WEAPON_FORMS:
        return None
    w = weapon_of(world, person)
    return None if w is None or w["broken"] else w["grade"]


# --- items ---------------------------------------------------------------------------------------------

def gear_name(slot: str, form: str | None, grade: int) -> str:
    word = GRADE_WORDS[grade]
    what = form if slot == "weapon" else ARMOUR_WORDS[form]
    return f"{'an' if word[0] in 'aeiou' else 'a'} {word} {what}"


def make_item(world, slot: str, form: str, grade: int, owner: int | None, how: str, maker=None,
              name: str | None = None, path: str | None = None, **extra) -> int:
    """A gear item owned by `owner` (or by no one), its history begun."""
    data = {"slot": slot, "form": form, "grade": grade, "maker": maker, "made_at": world.time,
            "owners": [{"person": owner, "since": world.time, "how": how}] if owner is not None else [],
            "deeds": [], "famous": False, "epithet": None, "armoury": None, "broken": False, **extra}
    item = world.add_entity("gear", name or gear_name(slot, form, grade), data, path)
    if owner is not None:
        world.relate(owner, item, "owns")
    return item


def gear_items(world, person: int) -> list:
    return [e for e in (world.entity(i) for i in world.targets(person, "owns")) if e is not None and e.kind == "gear"]


def best_weapon_form(world, person: int) -> str | None:
    from systems.duel import best_art, ensure_npc_arts  # the duel module builds on this one
    ensure_npc_arts(world, person)
    art = best_art(world, person)
    return art.form if art is not None and art.form in WEAPON_FORMS else None


def materialize(world, person: int, slot: str) -> int | None:
    """Make what an NPC carries real (spec 2.5): an item with its history begun, which they now wield or wear."""
    item = item_in(world, person, slot)
    if item is not None:
        return item.id
    gear = dict(carried(world, person))
    grade = gear.get(slot)
    if grade is None:
        return None
    if slot == "weapon":
        form = gear.get("form") or best_weapon_form(world, person)
        if form is None:
            return None  # a hand art: whatever they carried was not a weapon for it
    else:
        form = ARMOURS[rng_for(world.world_seed, f"gear:{person}:armour").randrange(len(ARMOURS))]
    made = make_item(world, slot, form, grade, person, "carried", path=f"gear:{person}:{slot}",
                     deeds=list(gear.get("deeds", [])) if slot == "weapon" else [])
    world.relate(person, made, SLOTS[slot])
    gear[slot] = None  # now the item, not the grade
    if slot == "weapon":
        gear.pop("deeds", None)
        gear.pop("form", None)
    world.update_data(person, gear=gear)
    return made


def fits(world, person: int, item_id: int, slot: str) -> str | None:
    item = world.entity(item_id)
    if item is None or item.kind != "gear" or item_id not in world.targets(person, "owns"):
        return "You do not have that."
    if item.data["slot"] != slot:
        return "That is not " + ("a weapon." if slot == "weapon" else "armour.")
    return None


def wield_events(world, person: int, item_id: int, place: int) -> list[Event]:
    slot = world.entity(item_id).data["slot"]
    return [Event("gear_taken_up", (person,), place, {"item": item_id, "slot": slot})]


def put_away_events(world, person: int, slot: str, place: int) -> list[Event]:
    item = item_in(world, person, slot)
    return [] if item is None else [Event("gear_put_away", (person,), place, {"item": item.id, "slot": slot})]


@effect("gear_taken_up")
def _taken_up(world, event) -> None:
    person, d = event.actors[0], event.data
    world.unrelate(person, SLOTS[d["slot"]])
    world.relate(person, d["item"], SLOTS[d["slot"]])


@effect("gear_put_away")
def _put_away(world, event) -> None:
    world.unrelate(event.actors[0], SLOTS[event.data["slot"]], event.data["item"])


def pass_events(world, giver: int | None, taker: int | None, item_id: int, place, how: str) -> list[Event]:
    """An item changes hands (taken, bought, sold, drawn, returned, inherited, won, given, found)."""
    actors = tuple(p for p in (taker, giver) if p is not None)
    return [Event("gear_passed", actors, place, {"item": item_id, "giver": giver, "taker": taker, "how": how})]


@effect("gear_passed")
def _passed(world, event) -> None:
    d = event.data
    item = world.entity(d["item"])
    for owner in world.sources(item.id, "owns"):
        world.unrelate(owner, "owns", item.id)
        for rel in SLOTS.values():
            world.unrelate(owner, rel, item.id)
    owners = list(item.data["owners"])
    if d["taker"] is not None:
        world.relate(d["taker"], item.id, "owns")
        owners.append({"person": d["taker"], "since": world.time, "how": d["how"]})
    lost = d["how"] == "lost"  # dropped where they fell; a thing sold or returned goes to the stall or the armoury
    world.update_data(item.id, owners=owners, lost_at=event.place if lost else None)


def break_events(world, person: int, place) -> list[Event]:
    return [Event("weapon_broke", (person,), place, {})]


@effect("weapon_broke")
def _broke(world, event) -> None:
    """The lesser blade gives way: an item stays, broken, with its past; a carried grade is simply gone."""
    person = event.actors[0]
    item = item_in(world, person, "weapon")
    if item is not None:
        world.update_data(item.id, broken=True)
        return
    gear = dict(carried(world, person))
    gear["weapon"] = None
    world.update_data(person, gear=gear)


def starting_weapon(world, person: int, form: str) -> None:
    """A new hero's plain weapon for their first art, carried until it matters, as an NPC's is (plan ruling 2)."""
    if form in WEAPON_FORMS:
        world.update_data(person, gear={"weapon": 0, "armour": None, "form": form})


import systems.provenance  # noqa: E402,F401  (what a weapon has done: registers its listeners)


@listen("succession")
def _heir_takes_up(world, event, event_id: int) -> None:
    """The heir takes up what the one before them wielded and wore, and their plain carried gear (4b, spec 4.4)."""
    old, heir = event.actors
    for slot, rel in SLOTS.items():
        for item in world.targets(old, rel):
            world.unrelate(old, rel, item)
            world.unrelate(heir, rel)
            world.relate(heir, item, rel)
    for item in gear_items(world, heir):
        owners = item.data["owners"]
        if owners and owners[-1]["person"] == old:
            world.update_data(item.id, owners=owners + [{"person": heir, "since": world.time, "how": "inherited"}])
    carried_by_old = world.entity(old).data.get("gear")
    if carried_by_old is not None:
        world.update_data(heir, gear=dict(carried_by_old))
