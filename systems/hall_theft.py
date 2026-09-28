"""Stealing from a sect's garden or pill hall (phase 5c spec 2.4), by night, at its seat.

The chance is `0.5 + 0.1 x (the thief's realm - the guard's realm)`, bounded 0.1-0.9; the guard is the strongest
of the sect standing at its seat, or a seeded watchman. A garden holding a hundred-year herb keeps a guardian
beast, fought first. Caught, the thief is known for it (the 3b crime `stole`) and the goods go back; unseen, the
sect knows only that someone came. A thief sees what a garden or a hall holds only after a look by night.
"""

import systems.encounters as encounters
import systems.herbs as H
import systems.lives as lives
import systems.pill_hall as PH
import systems.recipe_trade as RT
from systems import factions as F
from systems import halls
from systems.facts import make_variant, place_name, record_fact
from systems.realms import realm_index
from world.events import Event, Witness, effect, listen
from world.gen.materialize import region_of
from world.seed import rng_for

NIGHT = 3                  # the fourth watch of the day
BASE, PER_REALM, BOUNDS = 0.5, 0.1, (0.1, 0.9)
HERBS_TAKEN, PILLS_TAKEN = 3, 2
WATCHMAN = (1, 3)          # a seeded guard's realm, where no one of the sect stands
THEFT_WEIGHT = 1.5
TARGETS = ("garden", "hall", "scroll")
GUARDIAN_GONE = 4          # watches a beaten guardian stays away: the fight itself takes one


def night(world) -> bool:
    return world.time % 4 == NIGHT


def nightfall_events(world, person: int, place) -> list[Event]:
    return [Event("waited_for_night", (person,), place, {"watches": (NIGHT - world.time % 4) % 4 or 4})]


@effect("waited_for_night")
def _waited(world, event) -> None:
    from systems.time import advance
    advance(world, event.data["watches"])


def guard_of(world, faction: int) -> tuple[int | None, int]:
    """(the guard, their realm): the strongest of the sect at its seat, else a seeded watchman (None)."""
    seat = world.entity(faction).data.get("seat")
    staff = [p for p in halls.staff_at(world, faction, seat)] if seat is not None else []
    staff = [p for p in staff if not world.entity(p).data.get("is_player")]
    if staff:
        best = min(staff, key=lambda p: (-realm_index(world.entity(p).data.get("realm", "mortal")), p))
        return best, realm_index(world.entity(best).data.get("realm", "mortal"))
    return None, rng_for(world.world_seed, f"watchman:{faction}").randint(*WATCHMAN)


def chance(world, thief: int, faction: int) -> float:
    from systems.arrays import theft_cut  # phase 5d: a sect's ward over its garden and hall
    realm = realm_index(world.entity(thief).data.get("realm", "mortal"))
    return max(BOUNDS[0], min(BOUNDS[1], BASE + PER_REALM * (realm - guard_of(world, faction)[1])
                              - theft_cut(world, faction)))


def at_seat(world, faction: int, place) -> bool:
    return world.entity(faction).data.get("seat") == place


def knows_hall(world, person: int, faction: int) -> bool:
    """A sect's hall and garden are known to its own, and to a thief who has looked (spec 8)."""
    found = F.membership(world, person, faction)
    if found is not None and found[1].get("status", "member") == "member":
        return True
    return faction in (world.entity(person).data.get("surveyed") or [])


# --- a look by night ------------------------------------------------------------------------------------------

def look_block(world, person: int, faction: int, place) -> str | None:
    if not at_seat(world, faction, place) or not (PH.keeps_hall(world, faction) or PH.keeps_garden(world, faction)):
        return "There is nothing of theirs to look at here."
    if not night(world):
        return "Wait for the dark."
    if knows_hall(world, person, faction):
        return "You know what they keep."
    return None


def look_events(world, person: int, faction: int, place) -> list[Event]:
    return [Event("hall_surveyed", (person,), place, {"faction": faction})]


@effect("hall_surveyed")
def _surveyed(world, event) -> None:
    person = event.actors[0]
    world.update_data(person, surveyed=(world.entity(person).data.get("surveyed") or []) + [event.data["faction"]])


# --- the guardian beast ---------------------------------------------------------------------------------------

def needs_guardian(world, person: int, faction: int) -> bool:
    """The garden's guardian stands between the thief and a hundred-year herb, until beaten (for a day)."""
    beaten = world.entity(person).data.get("guardian_beaten") or {}
    return PH.guarded(world, faction) and not (beaten.get("faction") == faction
                                               and world.time < beaten.get("until", 0))


def guardian_events(world, person: int, faction: int, place) -> list[Event]:
    """The guardian comes out of the dark: a beast encounter with it (the engine runs the fight). A garden keeps
    one guardian: the same beast comes back until it is slain (5c minors)."""
    known = world.entity(world.entity(faction).data.get("guardian") or 0)
    if known is not None and not known.data.get("dead"):
        beast = known.id
    else:
        region = region_of(world, place)
        beast = encounters.make_roamer(world, region, "beast", encounters._free_roamer_slot(world, region), 0.7)
        world.update_data(beast, guardian_of=faction)
        world.update_data(faction, guardian=beast)
    return encounters.encounter_events(person, beast, place, "beast", 0)


@listen("duel_ended")
def _guardian_beaten(world, event, event_id: int) -> None:
    player, opponent = event.actors
    faction = world.entity(opponent).data.get("guardian_of")
    if faction is not None and event.data.get("result") == "won":
        world.update_data(player, guardian_beaten={"faction": faction, "until": world.time + GUARDIAN_GONE})


# --- the theft ------------------------------------------------------------------------------------------------

def steal_block(world, person: int, faction: int, target: str, place) -> str | None:
    if target not in TARGETS or not at_seat(world, faction, place):
        return "There is nothing of theirs to take here."
    if not night(world):
        return "Wait for the dark."
    if target == "garden":
        if not any(count > 0 for count, _ in PH.garden(world, faction).values()):
            return "Their garden is bare."
        if needs_guardian(world, person, faction):
            return "Something guards the garden."
    elif target == "hall":
        if not any(v > 0 for v in PH.table(world, faction).values()):
            return "Their pill hall is empty."
    elif not PH.keeps_hall(world, faction):
        return "They keep no pill hall."
    return None


def _loot(world, faction: int, target: str) -> list:
    """What a thief carries off: the oldest herbs, the strongest pills, or a secret scroll."""
    if target == "garden":
        growing = sorted(((grade, name) for name, (count, grade) in PH.garden(world, faction).items() if count > 0),
                         reverse=True)
        out = []
        for grade, name in growing:
            count = PH.garden(world, faction)[name][0]
            out += [[name, grade]] * min(count, HERBS_TAKEN - len(out))
            if len(out) >= HERBS_TAKEN:
                break
        return out
    if target == "hall":
        stocked = sorted(((int(k.split(":")[0]), k.split(":")[1], v) for k, v in PH.table(world, faction).items()
                          if v > 0), key=lambda s: (-s[0], s[1]))
        out = []
        for grade, kind, count in stocked:
            out += [[grade, kind]] * min(count, PILLS_TAKEN - len(out))
        return out[:PILLS_TAKEN]
    return [RT.secret_recipes(world, faction)[0]]


def steal_events(world, person: int, faction: int, target: str, place) -> list[Event]:
    roll = rng_for(world.world_seed, f"theft:{person}:{faction}:{world.time}").random()
    success = roll < chance(world, person, faction)
    guard, _ = guard_of(world, faction)
    witnesses = (Witness(guard, "hatred", 0.8),) if not success and guard is not None else ()
    return [Event("hall_theft", (person,) + ((guard,) if guard is not None else ()), place,
                  {"faction": faction, "target": target, "caught": not success,
                   "loot": _loot(world, faction, target) if success else [],
                   "season": lives.current_season(world)}, witnesses=witnesses)]


@effect("hall_theft")
def _theft(world, event) -> None:
    person, d = event.actors[0], event.data
    if d["caught"]:
        return
    faction = d["faction"]
    if d["target"] == "garden":
        for name, grade in d["loot"]:
            PH.take_from_garden(world, faction, name, d["season"])
            H.make_herb(world, name, grade, person, "stolen")
    elif d["target"] == "hall":
        stocked = PH.table(world, faction)
        for grade, kind in d["loot"]:
            stocked[f"{grade}:{kind}"] -= 1
            PH.make_hall_pill(world, person, faction, grade, kind, "stolen")
        world.update_data(faction, pill_hall={k: v for k, v in stocked.items() if v > 0}, pill_hall_at=d["season"])
    else:
        RT.make_scroll(world, person, d["loot"][0], "stolen", faction)


@listen("hall_theft")
def _theft_news(world, event, event_id: int) -> None:
    person, d = event.actors[0], event.data
    where = place_name(world, event.place)
    if d["caught"]:  # the 3b crime, as the armoury's theft is (5a)
        record_fact(world, person, "stole", d["faction"], place=event.place, source_event=event_id,
                    weight=THEFT_WEIGHT, variant=make_variant("stole", person, d["faction"], place=where))
    else:  # someone came in the night: a deed without a doer
        variant = make_variant("robbed_hall", None, d["faction"], place=where)
        variant.update(what=d["target"])
        record_fact(world, d["faction"], "robbed_hall", None, place=event.place, source_event=event_id, weight=1.0,
                    variant=variant)
