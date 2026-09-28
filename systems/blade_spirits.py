"""Weapon spirits and cursed blades (phase 5e spec 6): a blade that has killed enough wakes a spirit, loyal or
bloodthirsty as its wielder's heart then leaned; a cursed famous blade hungers from its making.

A weapon counts its `kills`; a woken `spirit` is `{nature, bond, master, known_by}`. A loyal spirit lends its
master strength as the bond grows; a bloodthirsty one lends anyone strength, whispers when unfed a season, and
refuses to be sheathed dry in a troubled hand. A spirit is felt after a season in hand, or told by a smith.
"""

import systems.gear as gear
import systems.heart as HT
import systems.lives as lives
import systems.world_clock as world_clock
from systems.famous import famous_weapons
from world.events import Event, commit, effect, listen
from world.seed import seed_for

WAKE_KILLS, MASTERWORK_KILLS, WAKE_GRADE = 12, 6, 2
NATURES = ("loyal", "bloodthirsty")
BLOODTHIRSTY_LEAN = -30.0
LOYAL_STEP, BOND_STEP = 0.1, 0.1   # a loyal spirit's master fights x (1 + 0.1 x bond); a kill binds 0.1 more
THIRST = 1.15
CURSED_SHARE = 0.2                  # one famous blade in five
HUNGER_STEADY = -5.0
DRY_STEADY = 30.0                   # under this, a bloodthirsty blade will not spare
TELLING_SKILL = 3                   # a smith of this skill reads a blade


def cursed(world, item) -> bool:
    return item.id in famous_weapons(world) and seed_for(world.world_seed, f"curse:{item.id}") / 2 ** 64 < CURSED_SHARE


def spirit_of(world, item_id) -> dict | None:
    """A blade's spirit: woken, or a cursed blade's hunger; none in a broken blade."""
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item.kind != "gear" or item.data.get("broken"):
        return None
    if item.data.get("spirit"):
        return item.data["spirit"]
    if cursed(world, item):
        return {"nature": "bloodthirsty", "bond": 0.0, "master": None, "known_by": [], "cursed": True}
    return None


def wielded(world, person: int):
    """The blade in hand, if it is an item (a carried grade has no spirit): one lookup, no carried gear read."""
    return gear.item_in(world, person, "weapon")


def blade_factor(world, person: int, form: str) -> float:
    """What the spirit in the blade one fights with lends (spec 6)."""
    item = wielded(world, person)
    spirit = spirit_of(world, item.id) if item is not None and item.data["form"] == form else None
    if spirit is None:
        return 1.0
    if spirit["nature"] == "bloodthirsty":
        return THIRST
    return round(1 + LOYAL_STEP * spirit["bond"], 3) if spirit["master"] == person else 1.0


def refuses_spare(world, person: int) -> bool:
    item = wielded(world, person)
    spirit = spirit_of(world, item.id) if item is not None else None
    return spirit is not None and spirit["nature"] == "bloodthirsty" and HT.steady(world, person) < DRY_STEADY


def known(world, person: int, item_id) -> bool:
    spirit = spirit_of(world, item_id)
    return spirit is not None and person in spirit["known_by"]


def _write(world, item, spirit: dict) -> None:
    world.update_data(item.id, spirit=dict(spirit))


# --- kills and waking ------------------------------------------------------------------------------------------------

@listen("died")
def _killed(world, event, event_id: int) -> None:
    killer, victim = event.actors[0], event.actors[-1]
    if killer == victim or world.entity(killer) is None or world.entity(killer).data.get("dead"):
        return
    item = wielded(world, killer)
    if item is None or item.data.get("broken"):
        return
    kills = item.data.get("kills", 0) + 1
    world.update_data(item.id, kills=kills, fed_at=world.time)
    spirit = spirit_of(world, item.id)
    if spirit is not None:
        if spirit["nature"] == "loyal" and spirit["master"] == killer:
            _write(world, item, {**spirit, "bond": round(min(1.0, spirit["bond"] + BOND_STEP), 3)})
        return
    named = item.data.get("forged_by") is not None and item.data.get("famous")
    if item.data["grade"] >= WAKE_GRADE and kills >= (MASTERWORK_KILLS if named else WAKE_KILLS):
        nature = "bloodthirsty" if HT.lean(world, killer) < BLOODTHIRSTY_LEAN else "loyal"
        commit(world, [Event("spirit_woke", (killer, item.id), event.place, {"nature": nature})])


@effect("spirit_woke")
def _woke(world, event) -> None:
    killer, item = event.actors
    world.update_data(item, spirit={"nature": event.data["nature"], "bond": 0.0, "master": killer, "known_by": []})


# --- hunger and feeling it -------------------------------------------------------------------------------------------

def season_hook(world, n: int) -> list[Event]:
    """In the player's hand for a season: its spirit is felt; a bloodthirsty one unfed whispers."""
    player = world.get_meta("player_id")
    item = wielded(world, player) if player is not None and world.entity(player) is not None else None
    spirit = spirit_of(world, item.id) if item is not None else None
    if spirit is None:
        return []
    here = next(iter(world.targets(player, "located_in")), None)
    events = []
    if player not in spirit["known_by"]:
        events.append(Event("spirit_felt", (player, item.id), here, {"nature": spirit["nature"],
                                                                      "cursed": bool(spirit.get("cursed"))}))
    if spirit["nature"] == "bloodthirsty" and item.data.get("fed_at", -1) < world.time - lives.SEASON:
        events.append(Event("blade_whispered", (player, item.id), here, {"steady": HUNGER_STEADY}))
    return events


world_clock.SEASON_HOOKS.append(season_hook)


def _knows(world, person: int, item_id: int) -> None:
    item = world.entity(item_id)
    spirit = spirit_of(world, item_id)
    if spirit is not None and person not in spirit["known_by"]:
        _write(world, item, {**spirit, "known_by": spirit["known_by"] + [person]})


@effect("spirit_felt")
def _felt(world, event) -> None:
    _knows(world, *event.actors)


@effect("blade_whispered")
def _whispered(world, event) -> None:
    HT.shift_steady(world, event.actors[0], event.data["steady"])


def tell_block(world, person: int, smith: int, item_id) -> str | None:
    from systems.craft_world import crafter, skill  # the smiths come after the heart in the import graph
    if crafter(world, smith) != "smith" or skill(world, smith) < TELLING_SKILL:
        return "They cannot read a blade's heart."
    item = world.entity(item_id) if isinstance(item_id, int) else None
    if item is None or item.kind != "gear" or item_id not in world.targets(person, "owns"):
        return "You have no such blade."
    return None


def tell_events(world, person: int, smith: int, item_id: int, place) -> list[Event]:
    spirit = spirit_of(world, item_id)
    return [Event("blade_read", (person, smith, item_id), place,
                  {"nature": spirit["nature"] if spirit else None, "cursed": bool(spirit and spirit.get("cursed"))})]


@effect("blade_read")
def _read(world, event) -> None:
    _knows(world, event.actors[0], event.actors[2])
