"""Leaving a faction (phase 3b spec 7): release, desertion, hunters, and spies found out."""

import systems.encounters as encounters
from systems import factions as F
from systems import halls
from systems.membership import left_events
from systems.purse import payment_events
from systems.standing import believed_factions
from world.events import listen
from world.gen.materialize import ensure_region
from world.seed import rng_for

NEVER_RELEASE = frozenset({"demonic_cult", "unorthodox_clan", "bandit_fort"})
RELEASE_PER_RANK = 50
HUNTER_CHANCE = 0.2
HUNT_RANGE = 2
GONE = frozenset({"expelled", "deserter", "spy"})


def release_price(world, player: int, faction: int) -> int:
    return RELEASE_PER_RANK * (F.membership(world, player, faction)[0] + 1)


def release_events(world, player: int, faction: int, keeper: int, place: int) -> list:
    return payment_events(player, keeper, place, release_price(world, player, faction), "release") + \
        left_events(world, player, faction, place, "released")


def gone_from(world, player: int) -> list[int]:
    return [fid for fid, _, data in F.memberships(world, player) if data.get("status") in GONE]


def _staff_everywhere(world, faction: int) -> list[int]:
    data = world.entity(faction).data
    out = []
    for town in [data.get("seat"), *data.get("branches", [])]:
        if town:
            out += halls.staff_at(world, faction, town)
    return out


def _wrong_them(world, event, event_id: int) -> None:
    for person in _staff_everywhere(world, event.data["faction"]):
        world.add_memory(person, event_id, "wronged", 0.8, ignore_existing=True)


for _kind in ("expelled", "deserted", "spy_exposed"):
    listen(_kind)(_wrong_them)


def town_hunters(world, player: int) -> set[int]:
    """Members of factions the player betrayed: in town they call the player out like avengers."""
    out: set[int] = set()
    for faction in gone_from(world, player):
        out |= set(F.members_of(world, faction))
    return out


def hunter_encounter(world, player: int, town, rng):
    """A disciple sent after a deserter or spy, on the roads near the faction's home."""
    for faction in gone_from(world, player):
        home = world.entity(faction).data["home"]
        if F.gap(home, (town.data["x"], town.data["y"])) > HUNT_RANGE:
            continue
        if rng_for(world.world_seed, f"hunter:{faction}:{player}:{world.time}").random() >= HUNTER_CHANCE:
            continue
        pool = halls.staff_at(world, faction, halls.seat_of(world, faction), roles=("disciple", "elder"))
        if not pool:
            continue
        hunter = rng_for(world.world_seed, f"hunter-who:{faction}:{world.time}").choice(sorted(pool))
        return encounters.encounter_events(player, hunter, town.id, "sect_hunter", 0,
                                           {"faction_name": world.entity(faction).name})
    return None


def spy_checks(world, player: int, place: int) -> list:
    """A faction that hears the player belongs to a rival martial faction casts them out as a spy."""
    mine = [fid for fid, _, data in F.memberships(world, player) if data.get("status", "member") == "member"]
    events = []
    for faction in mine:
        kind = world.entity(faction).data["type"]
        if kind not in F.MARTIAL and kind != "imperial":
            continue
        heard = believed_factions(world, faction, player)
        for other in mine:
            if other == faction or other not in heard:
                continue
            other_kind = world.entity(other).data["type"]
            if (kind in F.MARTIAL and other_kind in F.MARTIAL) or (kind == "imperial" and other_kind in F.DARK):
                events += left_events(world, player, faction, place, "spy")
                break
    return events


encounters.HUNTER_HOOKS.append(town_hunters)
encounters.ROAD_HOOKS.append(hunter_encounter)
