"""The world's crafts (phase 5d spec 6): smiths and formation masters, their skill, their wares, their commissions.

Blacksmiths and fortune tellers by trade carry a seeded skill 1-5 (`craft_skill` once written) that rises now and
then in their seasons (a lives agenda: one hash, no Random, no entities). A master smith lifts their town's stall.
A formation master sells flags and the manuals of patterns their skill reaches, and lays a pattern on commission;
a smith forges on commission, ready in ten days.
"""

import math

import systems.control  # noqa: F401  5c's agendas run before this one, whatever is imported first
import systems.formations as FM
import systems.gear as gear
import systems.lives as lives
from systems.purse import silver_of
from world.events import Event, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for, seed_for

CRAFTS = {"blacksmith": "smith", "fortune teller": "formation master"}
SKILLS = (1, 5)
RISE_CHANCE = 0.1
MASTER_SMITH = 4           # a town's best smith of this skill lifts its stall a grade
FORGE_SHARE = 2            # a commission costs twice the stall's price
FORGE_DAYS = 10
LAY_PRICE = 100            # silver x difficulty
FLAG_LOT = 5


def crafter(world, person: int) -> str | None:
    entity = world.entity(person)
    return CRAFTS.get(entity.data.get("occupation")) if entity is not None and not entity.data.get("dead") else None


def skill(world, person: int) -> int | None:
    """A smith's or formation master's skill: written once it has risen, else seeded."""
    if crafter(world, person) is None:
        return None
    entity = world.entity(person)
    if "craft_skill" in entity.data:
        return entity.data["craft_skill"]
    return rng_for(world.world_seed, f"craft:{lives.key(entity)}").randint(*SKILLS)


def title(world, person: int) -> str:
    words = ("", "an apprentice", "a journeyman", "a skilled", "a master", "a grandmaster")
    return f"{words[skill(world, person)]} {crafter(world, person)}"


def season_events(world, person: int, n: int, rng) -> list[Event]:
    """A smith's or formation master's skill rises one step, one season in ten (its own hash, spec 6)."""
    entity = world.entity(person)
    if entity.data.get("occupation") not in CRAFTS:
        return []
    if seed_for(world.world_seed, f"craft_rise:{lives.key(entity)}:{n}") / 2 ** 64 >= RISE_CHANCE:
        return []
    now = skill(world, person)
    return [] if now >= SKILLS[1] else [Event("craft_rose", (person,), lives.home(world, person),
                                              {"skill": now + 1, "season": n})]


lives.AGENDAS.append(season_events)


@effect("craft_rose")
def _rose(world, event) -> None:
    world.update_data(event.actors[0], craft_skill=event.data["skill"])


def town_smith(world, town: int) -> int | None:
    """The best smith living in a town, if any."""
    smiths = [p.id for p in people_at(world, town) if crafter(world, p.id) == "smith"]
    return max(smiths, key=lambda p: (skill(world, p), -p)) if smiths else None


def stall_lift(world, town: int) -> int:
    """A master smith lifts the town's stall a grade (5a's cap)."""
    best = town_smith(world, town)
    return 1 if best is not None and skill(world, best) >= MASTER_SMITH else 0


# --- a formation master's wares -----------------------------------------------------------------------------

def teaches(world, master: int) -> list[str]:
    """The patterns a formation master knows and sells: those of a difficulty their skill reaches."""
    if crafter(world, master) != "formation master":
        return []
    top = math.ceil(skill(world, master) / 2)
    return sorted(k for k, row in FM.PATTERNS.items() if row["difficulty"] <= top)


def manual_block(world, person: int, master: int, key: str) -> str | None:
    if key not in teaches(world, master):
        return "They sell no such manual."
    if silver_of(world, person) < FM.manual_price(key):
        return f"The manual costs {FM.manual_price(key)} silver."
    return None


def manual_events(world, person: int, master: int, key: str, place) -> list[Event]:
    return [Event("manual_bought", (person, master), place, {"pattern": key, "price": FM.manual_price(key)})]


@effect("manual_bought")
def _manual(world, event) -> None:
    person, master = event.actors
    _pay(world, person, master, event.data["price"])
    FM.make_manual(world, person, event.data["pattern"], "bought")


def flags_block(world, person: int, master: int) -> str | None:
    if crafter(world, master) != "formation master":
        return "They sell no flags."
    if silver_of(world, person) < FLAG_LOT * FM.FLAG_PRICE:
        return f"Five flags cost {FLAG_LOT * FM.FLAG_PRICE} silver."
    return None


def flags_events(world, person: int, master: int, place) -> list[Event]:
    return [Event("flags_bought", (person, master), place, {"count": FLAG_LOT, "price": FLAG_LOT * FM.FLAG_PRICE})]


@effect("flags_bought")
def _flags(world, event) -> None:
    person, master = event.actors
    _pay(world, person, master, event.data["price"])
    FM.add_flags(world, person, event.data["count"])


def _pay(world, person: int, to: int, amount: int) -> None:
    world.update_data(person, silver=silver_of(world, person) - amount)
    world.update_data(to, silver=silver_of(world, to) + amount)


# --- commissions ---------------------------------------------------------------------------------------------

def lay_price(key: str) -> int:
    return LAY_PRICE * FM.PATTERNS[key]["difficulty"]


def lay_strength(world, master: int) -> float:
    return round(min(1.0, 0.5 + skill(world, master) / 10), 3)


def commission_lay_block(world, person: int, master: int, key: str, place) -> str | None:
    if key not in teaches(world, master):
        return "They do not know that pattern."
    why = FM.site_block(world, person, key, place)
    if why:
        return why
    if silver_of(world, person) < lay_price(key):
        return f"They ask {lay_price(key)} silver."
    return None


def commission_lay_events(world, person: int, master: int, key: str, place) -> list[Event]:
    return [Event("formation_commissioned", (person, master), place, {
        "pattern": key, "price": lay_price(key), "strength": lay_strength(world, master)})]


@effect("formation_commissioned")
def _laid_for(world, event) -> None:
    person, master = event.actors
    _pay(world, person, master, event.data["price"])
    FM.place_formation(world, event.place, event.data["pattern"], person, event.data["strength"])


def forge_grade(world, smith: int) -> int:
    return max(0, min(4, skill(world, smith) - 1))


def forge_price(world, smith: int, town: int, slot: str) -> int:
    from systems.smithy import price  # the smith's stall comes after the crafts in the import graph
    return FORGE_SHARE * price(world, town, slot, forge_grade(world, smith))


def pending(world, person: int) -> list[dict]:
    return list(world.entity(person).data.get("commissions") or [])


def commission_forge_block(world, person: int, smith: int, slot: str, form: str, town: int) -> str | None:
    if crafter(world, smith) != "smith":
        return "They are no smith."
    if form not in (gear.WEAPON_FORMS if slot == "weapon" else gear.ARMOURS):
        return "Nothing of that shape is forged."
    if any(c["smith"] == smith for c in pending(world, person)):
        return "They are forging for you already."
    if silver_of(world, person) < forge_price(world, smith, town, slot):
        return f"They ask {forge_price(world, smith, town, slot)} silver."
    return None


def commission_forge_events(world, person: int, smith: int, slot: str, form: str, town: int) -> list[Event]:
    return [Event("forge_commissioned", (person, smith), town, {
        "slot": slot, "form": form, "grade": forge_grade(world, smith),
        "price": forge_price(world, smith, town, slot), "ready_at": world.time + FORGE_DAYS * 4})]


@effect("forge_commissioned")
def _commissioned(world, event) -> None:
    person, smith = event.actors
    d = event.data
    _pay(world, person, smith, d["price"])
    world.update_data(person, commissions=pending(world, person) + [
        {"smith": smith, "slot": d["slot"], "form": d["form"], "grade": d["grade"], "ready_at": d["ready_at"],
         "price": d["price"]}])


@listen("died")
def _smith_dies(world, event, event_id: int) -> None:
    """A smith who dies with a commission unforged: their estate returns the silver (phase 5f closes 5d's)."""
    smith, player = event.actors[-1], world.get_meta("player_id")
    if player is None or world.entity(player) is None:
        return
    from systems.smithy import price  # the smith's stall comes after the crafts in the import graph
    from world.events import commit
    for c in [c for c in pending(world, player) if c["smith"] == smith]:
        paid = c.get("price") or FORGE_SHARE * price(world, event.place, c["slot"], c["grade"])  # older saves
        commit(world, [Event("commission_refunded", (player, smith), event.place,
                             {"slot": c["slot"], "form": c["form"], "grade": c["grade"], "silver": paid})])


@effect("commission_refunded")
def _refunded(world, event) -> None:
    person, smith = event.actors
    world.update_data(person, silver=silver_of(world, person) + event.data["silver"],
                      commissions=[c for c in pending(world, person) if c["smith"] != smith])


def ready(world, person: int, smith: int) -> dict | None:
    return next((c for c in pending(world, person) if c["smith"] == smith and c["ready_at"] <= world.time), None)


def collect_events(world, person: int, smith: int, place) -> list[Event]:
    return [Event("commission_collected", (person, smith), place, dict(ready(world, person, smith)))]


@effect("commission_collected")
def _collected(world, event) -> None:
    person, smith = event.actors
    d = event.data
    world.update_data(person, commissions=[c for c in pending(world, person) if c["smith"] != smith])
    gear.make_item(world, d["slot"], d["form"], d["grade"], person, "commissioned", maker=world.entity(smith).name)
