"""The faction clock (phase 4a spec 3): every materialized faction lives each season, watched or not.

A season runs in phases, each committed before the next reads the world:
clashes, mending, then per faction succession, staffing and power, then new
minor factions. Rolls are seeded by the season number, so the same seeds give
the same world.
"""

from collections import Counter

import systems.lives as lives
from systems import factions as F
from systems import halls, wars
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.realms import REALMS, realm_index
from world.events import Event, commit, effect, listen
from world.gen.materialize import people_at
from world.gen.names import person_name
from world.gen.npc import PORTRAIT_PARTS, TRAITS
from world.seed import rng_for

MAX_WORLD_SEASONS = 8
DRIFT, NOISE = 0.2, 3.0
DESTROY_BELOW = 15
FOUND_CHANCE = 0.02
RECRUITED_ROLES = ("keeper", "disciple")  # leaders and elders are promoted, never hired


def world_tick(world) -> int:
    """The last season the faction clock ran. An old save starts it in the present (spec §6)."""
    found = world.get_meta("world_tick")
    if found is None:
        found = lives.current_season(world)
        world.set_meta("world_tick", found)
    return found


def _role(world, person: int, faction: int) -> str | None:
    found = F.membership(world, person, faction)
    return found[1].get("role") if found else None


def staff_of(world, faction: int) -> list[int]:
    return [p for p in F.members_of(world, faction) if _role(world, p, faction) not in (None, "member")]


def _realm(world, person: int) -> int:
    return realm_index(world.entity(person).data.get("realm", "mortal"))


def staff_by_town(world, faction: int) -> dict[int, list[tuple[int, str]]]:
    """(person, role) of the living staff at each of the faction's halls, from one scan per hall."""
    out = {}
    for town in wars.hall_towns(world, faction):
        here = []
        for person in people_at(world, town):
            found = F.membership(world, person.id, faction)
            if found and found[1].get("status", "member") == "member" and found[1].get("role") not in (None, "member"):
                here.append((person.id, found[1]["role"]))
        out[town] = here
    return out


def power_target(world, faction: int, staff: dict | None = None) -> int:
    staff = staff_by_town(world, faction) if staff is None else staff
    people = [p for here in staff.values() for p, _ in here]
    mean = sum(_realm(world, p) for p in people) / len(people) if people else 0.0
    return max(0, min(100, round(20 + 10 * mean + 5 * len(staff))))


def _table(world, faction: int, seat: bool) -> tuple:
    kind = world.entity(faction).data["type"]
    if seat:
        return halls.SEAT_STAFF if kind in F.STAFFED else () if kind == "alliance" else halls.CAPITAL_STAFF
    return halls.BRANCH_STAFF if kind in F.STAFFED else ()


def _best(world, people: list[int]) -> int | None:
    return min(people, key=lambda p: (-_realm(world, p), p)) if people else None


def _promotion(world, person: int, faction: int, role: str, rank: int, hall) -> Event:
    return Event("succeeded", (person,), lives.home(world, person),
                 {"faction": faction, "role": role, "rank": rank, "hall": hall})


def succession_events(world, faction: int, n: int, staff: dict | None = None) -> list[Event]:
    """A dead or missing leader is replaced by the best elder, then keeper, then disciple; empty elder seats too."""
    seat = world.entity(faction).data.get("seat")
    staff = staff_by_town(world, faction) if staff is None else staff
    if seat not in staff:
        return []
    table = _table(world, faction, True)
    by_role = {r: [p for p, role in staff[seat] if role == r] for r in ("leader", "elder", "keeper", "disciple")}
    anywhere = staff_of(world, faction)  # a leader or elder away from the seat still holds the place
    leaders = [p for p in anywhere if _role(world, p, faction) == "leader"]
    by_role["elder"] = [p for p in anywhere if _role(world, p, faction) == "elder"]
    events = []
    if any(r == "leader" for r, _, _ in table) and not leaders:
        for pool in ("elder", "keeper", "disciple"):
            heir = _best(world, by_role[pool])
            if heir is not None:
                by_role[pool].remove(heir)
                events.append(_promotion(world, heir, faction, "leader", 4, None))
                break
    held = {F.membership(world, p, faction)[1].get("hall") for p in by_role["elder"]}
    for hall in [h for r, _, h in table if r == "elder" and h not in held]:
        for pool in ("keeper", "disciple"):
            heir = _best(world, by_role[pool])
            if heir is not None:
                by_role[pool].remove(heir)
                events.append(_promotion(world, heir, faction, "elder", 3, hall))
                break
    return events


def _recruit(world, faction, town: int, role: str, rank: int, path: str) -> int:
    """A new member of staff, made the way 3b's halls make them."""
    rng = rng_for(world.world_seed, path)
    surname, given = person_name(rng)
    realm = REALMS[min(len(REALMS) - 1, F.BASE_REALM.get(faction.data["type"], 0) + halls.REALM_BONUS[role])].label
    first = rng.choice(halls.DARK_TRAITS) if faction.data["path"] == "ruthless" else rng.choice(TRAITS)
    data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": rng.randint(16, 30),
            "occupation": "hall keeper" if role == "keeper" else F.title(world, faction.id, rank),
            "traits": list(dict.fromkeys([first, rng.choice(TRAITS)])), "realm": realm,
            "portrait": {part: rng.randrange(count) for part, count in PORTRAIT_PARTS.items()}}
    person = world.add_entity("person", f"{surname} {given}", data, path)
    world.relate(person, town, "located_in")
    return person


def staffing_events(world, faction: int, n: int, staff: dict | None = None) -> list[Event]:
    """Empty keeper and disciple places at each hall are filled by seeded recruits (spec §3.3)."""
    entity = world.entity(faction)
    staff = staff_by_town(world, faction) if staff is None else staff
    events, i = [], 0
    for town, here in sorted(staff.items()):
        table = _table(world, faction, town == entity.data.get("seat"))
        have = Counter(role for _, role in here)
        for role in RECRUITED_ROLES:
            slots = [(rank, hall) for r, rank, hall in table if r == role]
            for rank, hall in slots[have[role]:]:
                person = _recruit(world, entity, town, role, rank, f"world:{faction}:recruit:{n}:{i}")
                i += 1
                events.append(Event("recruited", (person,), town,
                                    {"faction": faction, "role": role, "rank": rank, "hall": hall, "season": n}))
    return events


def power_events(world, faction: int, n: int, staff: dict | None = None) -> list[Event]:
    data = world.entity(faction).data
    rng = rng_for(world.world_seed, f"world:{n}:{faction}")
    power = data.get("power", 50)
    target = power_target(world, faction, staff)
    new = max(0, min(100, round(power + DRIFT * (target - power) + rng.uniform(-NOISE, NOISE))))
    events = [Event("faction_season", (faction,), data.get("seat"), {"season": n, "power": new})]
    if data["tier"] == "minor" and new < DESTROY_BELOW:
        events.append(Event("faction_destroyed", (faction,), data.get("seat"), {"season": n}))
    return events


def founding_events(world, n: int) -> list[Event]:
    """Now and then a new school or bandit fort rises in a settled town of a region (spec §3.4)."""
    towns: dict = {}
    for town in world.entities("town"):
        if town.data.get("factions_ready"):
            towns.setdefault((town.data["x"], town.data["y"]), []).append(town.id)
    events = []
    for region in world.entities("region"):
        if not region.data.get("minors_ready"):
            continue
        rng = rng_for(world.world_seed, f"world:{n}:region:{region.id}")
        if rng.random() >= FOUND_CHANCE:
            continue
        x, y = region.data["x"], region.data["y"]
        free = [t for t in towns.get((x, y), [])
                if not any(world.entity(f).data["tier"] == "minor" for f in halls.halls_here(world, t))]
        if not free:
            continue
        town = rng.choice(free)
        kind = rng.choice(("school", "bandit_fort"))
        used = {world.entity(f).name for f in region.data.get("minors", [])}
        fid = F._make(world, rng, kind, "minor", (x, y), f"world:{n}:minor:{region.id}", used)
        events.append(Event("faction_founded", (fid,), town, {"season": n, "region": region.id}))
    return events


def run_season(world, n: int) -> None:
    with world.transaction():
        clashes = wars.clash_events(world, n)
        commit(world, clashes)
        clashed = {tuple(sorted(e.actors)) for e in clashes if e.kind == "clash"}
        commit(world, wars.mend_events(world, n, clashed))
        for faction in wars.clock_factions(world):
            staff = staff_by_town(world, faction)  # one scan serves succession, staffing and power
            promotions = succession_events(world, faction, n, staff)
            if promotions:
                commit(world, promotions)
                staff = staff_by_town(world, faction)
            commit(world, staffing_events(world, faction, n, staff))
            commit(world, power_events(world, faction, n, staff))
        commit(world, founding_events(world, n))
        world.set_meta("world_tick", n)


def run_due(world, limit: int = MAX_WORLD_SEASONS) -> int:
    """Run the seasons the world is owed, at most `limit` of them. Returns how many ran."""
    done = 0
    while done < limit and world_tick(world) < lives.current_season(world):
        run_season(world, world_tick(world) + 1)
        done += 1
    return done


@effect("succeeded")  # not "promoted": 3b ranks owns that kind for the player
def _succeeded(world, event) -> None:
    person, d = event.actors[0], event.data
    set_membership(world, person, d["faction"], rank=d["rank"], role=d["role"], hall=d["hall"])
    world.update_data(person, occupation=F.title(world, d["faction"], d["rank"]))


@effect("recruited")
def _recruited(world, event) -> None:
    person, d = event.actors[0], event.data
    world.relate(person, d["faction"], "member_of", d["rank"],
                 {"role": d["role"], "hall": d["hall"], "merit": 0, "status": "member", "secret": False})
    world.update_data(person, lived_to=d["season"])


@effect("faction_season")
def _faction_season(world, event) -> None:
    world.update_data(event.actors[0], power=event.data["power"])


@effect("faction_destroyed")
def _destroyed(world, event) -> None:
    faction = event.actors[0]
    for person in world.sources(faction, "member_of"):
        found = F.membership(world, person, faction)
        if found and found[1].get("status", "member") == "member":
            set_membership(world, person, faction, status="released")
    for town in {t for t in [world.entity(faction).data.get("seat"), *world.entity(faction).data.get("branches", [])] if t}:
        data = world.entity(town).data
        world.update_data(town, halls=[f for f in data.get("halls", []) if f != faction],
                          seats=[f for f in data.get("seats", []) if f != faction])
    world.update_data(faction, dissolved=True)


@effect("faction_founded")
def _founded(world, event) -> None:
    fid, town = event.actors[0], event.place
    region = world.entity(event.data["region"])
    minors = list(region.data.get("minors", []))
    world.update_data(fid, seat=town)
    F._set_stances(world, [fid], F.ensure_roster(world) + minors)
    world.update_data(region.id, minors=[*minors, fid])
    data = world.entity(town).data
    world.update_data(town, halls=[*data.get("halls", []), fid], seats=[*data.get("seats", []), fid])
    halls._hire(world, world.entity(fid), town, halls.SEAT_STAFF)


@listen("died")
def _dead_leave(world, event, event_id: int) -> None:
    """The dead hold no place in any faction (ruling 7); 3c handles the player's own sect."""
    victim = event.actors[-1]
    for fid, _, data in F.memberships(world, victim):
        if world.entity(fid).data.get("type") != "player_sect" and data.get("status", "member") == "member":
            set_membership(world, victim, fid, status="dead")


def _news(world, event, event_id: int, subject: int, predicate: str, obj, weight: float) -> None:
    record_fact(world, subject, predicate, obj, place=event.place, source_event=event_id, weight=weight,
                variant=make_variant(predicate, subject, obj, place=place_name(world, event.place)))


@listen("succeeded")
def _succeeded_news(world, event, event_id: int) -> None:
    d = event.data
    _news(world, event, event_id, event.actors[0], "promoted", d["faction"], 2.0 if d["role"] == "leader" else 1.5)


@listen("faction_destroyed")
def _destroyed_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "faction_destroyed", None, 2.5)


@listen("faction_founded")
def _founded_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "faction_founded", None, 2.0)
