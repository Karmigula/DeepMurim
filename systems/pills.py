"""Pills and what they do (phase 5b spec 4.1): swallowed, a coat of venom on a blade, and the residue they leave.

A pill is an item (`kind = "pill"`) with its `effect`, `grade` (1-5) and `purity`. It works at
`grade x (1 - residue / 150)` and leaves `grade x (1 - purity) x 10` residue behind. 4d's treasure pills
(`qi_years`) are qi pills of grade 2, swallowed the same way. Poisons are slipped or taken; venom is put on a
blade; a tempering draught is for a bath.
"""

import systems.gear as gear
import systems.toxins as toxins
from systems.bodies import load_body, save_body
from systems.realms import add_energy
from world.body import heal_watches
from world.events import Event, effect

LEGACY_GRADE, LEGACY_PURITY = 2, 0.7
SWALLOWED = frozenset({"qi", "bottleneck", "purity", "healing", "mending", "calming", "cleansing", "antidote",
                       "poison"})
VENOM_STRIKES = 3
POISON_STRENGTH = 4        # a swallowed or slipped poison lasts grade x 4 watches


def pills_of(world, person: int) -> list:
    """The pills someone carries: made ones, and 4d's treasure pills."""
    out = []
    for item in (world.entity(i) for i in world.targets(person, "owns")):
        if item is None or item.data.get("used"):
            continue
        if item.kind == "pill" or (item.kind == "treasure" and item.data.get("kind") == "pill"):
            out.append(item)
    return out


def effect_of(item) -> str:
    return item.data.get("effect", "qi")


def grade_of(item) -> int:
    return item.data.get("grade", LEGACY_GRADE)


def swallow_block(world, person: int, item_id: int) -> str | None:
    item = world.entity(item_id)
    if item is None or item not in pills_of(world, person):
        return "You have no such pill."
    if effect_of(item) not in SWALLOWED:
        return "That is not taken by mouth." if effect_of(item) != "venom" else "Venom goes on a blade, not down the throat."
    return None


def swallow_events(world, person: int, place, item_id: int) -> list[Event]:
    item = world.entity(item_id)
    return [Event("pill_taken", (person,), place, {
        "item": item_id, "effect": effect_of(item), "grade": grade_of(item),
        "purity": item.data.get("purity", LEGACY_PURITY), "qi_years": item.data.get("qi_years")})]


@effect("pill_taken")
def _taken(world, event) -> None:
    person, d = event.actors[0], event.data
    world.unrelate(person, "owns", d["item"])
    world.update_data(d["item"], used=True)
    body = load_body(world, person)
    potency = d["grade"] * toxins.dulling(body)
    kind = d["effect"]
    if kind in ("healing", "mending") and body.constitution == "Myriad Poison Body":
        potency *= 0.5  # a poison body takes healing hard (spec 4.4)
    if kind == "qi":  # a treasure pill keeps its own years, dulled like any other
        add_energy(body, d["qi_years"] * toxins.dulling(body) if d["qi_years"] is not None else 0.5 * potency)
    elif kind == "bottleneck":
        body.breakthrough_aid = round(body.breakthrough_aid + 0.1 * potency, 3)
    elif kind == "purity":
        body.purity = round(min(1.0, body.purity + 0.02 * potency), 3)
    elif kind == "healing":
        worst = sorted((i for i in body.injuries if not i.permanent and i.heals_at and i.heals_at > world.time),
                       key=lambda i: (-i.severity, i.id))[:max(1, round(potency))]
        for injury in worst:
            injury.heals_at = world.time + (injury.heals_at - world.time) // 2
    elif kind == "mending":
        damaged = sorted(n for n, m in body.meridians.items() if m.state == "damaged")
        severed = sorted(n for n, m in body.meridians.items() if m.state == "severed")
        if damaged:
            body.meridians[damaged[0]].state, body.meridians[damaged[0]].heals_at = "open", None
        elif severed and d["grade"] >= 4:
            body.meridians[severed[0]].state = "damaged"
            body.meridians[severed[0]].heals_at = world.time + heal_watches(3, body)
    elif kind == "calming":
        body.deviation = max(0.0, body.deviation - 10 * potency)
    elif kind == "cleansing":
        body.residue = max(0.0, body.residue - 10 * potency)
    if kind != "poison":
        toxins.leave_residue(body, d["grade"], d["purity"], toxins.residue_rng(world, person, event.data["item"]))
    save_body(world, person, body)
    if kind == "antidote":
        toxins.cure(world, person, d["grade"])
    elif kind == "poison":
        toxins.poison(world, person, d["grade"], d["grade"] * POISON_STRENGTH, "a swallowed poison")


# --- venom on a blade --------------------------------------------------------------------------------------

def coat_block(world, person: int, item_id: int) -> str | None:
    item = world.entity(item_id)
    if item is None or item not in pills_of(world, person) or effect_of(item) != "venom":
        return "You have no venom."
    if gear.weapon_of(world, person) is None:
        return "You carry no blade to coat."
    return None


def coat_events(world, person: int, place, item_id: int) -> list[Event]:
    return [Event("blade_coated", (person,), place, {"item": item_id, "grade": grade_of(world.entity(item_id))})]


@effect("blade_coated")
def _coated(world, event) -> None:
    person, d = event.actors[0], event.data
    world.unrelate(person, "owns", d["item"])
    world.update_data(d["item"], used=True)
    world.update_data(person, venom_coat={"grade": d["grade"], "strikes": VENOM_STRIKES})


def _venom_strikes(world, hitter: int, target: int, form: str, hitter_body, target_body) -> None:
    """A coated blade's wound poisons (spec 4.1); the coat wears off after three."""
    coat = world.entity(hitter).data.get("venom_coat")
    if not coat or form not in gear.WEAPON_FORMS:
        return
    toxins.add_poison(world, target, target_body, coat["grade"], coat["grade"] * 2, "a venomed blade")
    left = coat["strikes"] - 1
    world.update_data(hitter, venom_coat={**coat, "strikes": left} if left > 0 else None)


toxins.WOUND_HOOKS.append(_venom_strikes)
