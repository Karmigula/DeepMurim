"""The faction clock (phase 4a spec 3): every materialized faction lives each season, watched or not.

A season runs in phases, each committed before the next reads the world:
clashes, mending, then per faction succession, staffing and power, then new
minor factions. Rolls are seeded by the season number, so the same seeds give
the same world.
"""

from collections import Counter

import systems.claimants as C
import systems.lives as lives
from systems import factions as F
from systems import halls, wars
from systems.facts import make_variant, place_name, record_fact
from systems.membership import left_events, set_membership
from systems.realms import REALMS, realm_index
from world.events import Event, commit, effect, listen
from world.gen.names import person_name
from world.gen.npc import PORTRAIT_PARTS, TRAITS
from world.seed import rng_for

MAX_WORLD_SEASONS = 8
SEASON_HOOKS: list = []  # (world, n) -> list[Event]; later phases add their seasonal events (4c: famines)
DRIFT, NOISE = 0.2, 3.0
DESTROY_BELOW = 15
FOUND_CHANCE = 0.02
RECRUITED_ROLES = ("keeper", "disciple")  # leaders and elders are promoted, never hired


def world_tick(world) -> int:
    """The last season the faction clock ran. An old save starts it in the present (spec §6)."""
    found = world.get_meta("world_tick")
    if found is None:
        found = lives.current_season(world)
        with world.transaction():
            for person in world.entities("person"):  # an old save: everyone starts living now
                if person.data.get("lived_to") is None and not person.data.get("is_player"):
                    world.update_data(person.id, lived_to=found)
            world.set_meta("world_tick", found)
    return found


def _role(world, person: int, faction: int) -> str | None:
    found = F.membership(world, person, faction)
    return found[1].get("role") if found else None


def _staff_rows(world, faction: int) -> list[tuple[int, str, int | None]]:
    """(person, role, where they are) for the faction's living staff, read from the membership relation.

    One query for the faction and one per staff member; nobody's whole record is parsed.
    The dead hold no location, so they drop out here.
    """
    rows = []
    for person, _, data in world.relations_to(faction, "member_of"):
        if data.get("status", "member") != "member" or data.get("role") in (None, "member"):
            continue
        where = world.targets(person, "located_in")
        if where:
            rows.append((person, data["role"], where[0]))
    return rows


def staff_of(world, faction: int) -> list[int]:
    return [person for person, _, _ in _staff_rows(world, faction)]


def _realm(world, person: int) -> int:
    return realm_index(world.entity(person).data.get("realm", "mortal"))


def staff_by_town(world, faction: int) -> dict[int, list[tuple[int, str]]]:
    """(person, role) of the living staff at each of the faction's halls."""
    out = {town: [] for town in wars.hall_towns(world, faction)}
    for person, role, where in _staff_rows(world, faction):
        if where in out:
            out[where].append((person, role))
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
    anywhere = _staff_rows(world, faction)  # a leader or elder away from the seat still holds the place
    leaders = [p for p, role, _ in anywhere if role == "leader"]
    by_role["elder"] = [p for p, role, _ in anywhere if role == "elder"]
    events = []
    if any(r == "leader" for r, _, _ in table) and not leaders:
        from systems.succession_crisis import leaderless_events  # phase 4g: a seat in doubt waits for its crisis
        held = leaderless_events(world, faction, n)
        chief = world.entity(faction).data.get("heir")
        if held is not None:
            events += held
        elif isinstance(chief, int) and C.fit(world, chief, faction):
            for pool in by_role.values():
                if chief in pool:
                    pool.remove(chief)
            events.append(_promotion(world, chief, faction, "leader", 4, None))  # the chief disciple first (4g)
        else:
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
    staff = staff_by_town(world, faction) if staff is None else staff
    # unseen halls have no staff to count; level of detail must not starve them (phase 4a review)
    target = power_target(world, faction, staff) if staff else data.get("base_power", 60)
    new = max(0, min(100, round(power + DRIFT * (target - power) + rng.uniform(-NOISE, NOISE))))
    events = [Event("faction_season", (faction,), data.get("seat"), {"season": n, "power": new})]
    if data["tier"] == "minor" and new < DESTROY_BELOW:
        player = world.get_meta("player_id")
        mine = F.membership(world, player, faction) if isinstance(player, int) else None
        if mine and mine[1].get("status", "member") == "member":  # 3b's leaving closes the player's duty
            events += left_events(world, player, faction, data.get("seat") or lives.home(world, player), "released")
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
            commit(world, C.name_chief_events(world, faction, n))  # phase 4g: once a year
            staff = staff_by_town(world, faction)  # one scan serves succession, staffing and power
            promotions = succession_events(world, faction, n, staff)
            if promotions:
                commit(world, promotions)
                staff = staff_by_town(world, faction)
            commit(world, staffing_events(world, faction, n, staff))
            commit(world, power_events(world, faction, n, staff))
        commit(world, founding_events(world, n))
        for hook in season_hooks():
            commit(world, hook(world, n))
        world.set_meta("world_tick", n)


def season_hooks() -> list:
    """The hooks by module, each module's in the order it added them: the same whatever was imported first."""
    return sorted(SEASON_HOOKS, key=lambda hook: hook.__module__)


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
    if F.membership(world, person, d["faction"]) is None:  # a claimant who was never of them (4g final review)
        world.relate(person, d["faction"], "member_of", d["rank"],
                     {"role": d["role"], "hall": d["hall"], "merit": 0, "status": "member", "secret": False})
    else:
        set_membership(world, person, d["faction"], rank=d["rank"], role=d["role"], hall=d["hall"], status="member")
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


import systems.sky  # noqa: E402,F401  phase 4d: the sky's season hooks
import systems.rankings  # noqa: E402,F401  phase 4d: the Pavilion's informants and yearly lists
import systems.schism  # noqa: E402,F401  phase 4g: strife between a crisis's camps, season by season
import systems.regency  # noqa: E402,F401  phase 4g: regents, usurpers, and heirs who must hold the seat
import systems.murder  # noqa: E402,F401  phase 4h: plots, and the poisoned master
import systems.puppets  # noqa: E402,F401  phase 4h: puppets and cult spies
import systems.frames  # noqa: E402,F401  phase 4h: forged wills, framed heirs and their return
import systems.legitimacy  # noqa: E402,F401  phase 4h: the supreme art, the founder's test, marriage, arbiters
import systems.scheming  # noqa: E402,F401  phase 4h: the player's own plots
import systems.famous  # noqa: E402,F401  phase 5a: famous weapons, how they pass, the Hundred Weapons Chronicle
import systems.smithy  # noqa: E402,F401  phase 5a: the smith's stall
import systems.armoury  # noqa: E402,F401  phase 5a: a sect's armoury, drawn from and restocked
import systems.spoils  # noqa: E402,F401  phase 5a: what the fallen carried
import systems.toxins  # noqa: E402,F401  phase 5b: residue, and the poisons that kill the NPCs who carry them
import systems.herbs  # noqa: E402,F401  phase 5b: herbs, tasting, gathering, the herbalist
import systems.alchemy  # noqa: E402,F401  phase 5b: experiments and refining
import systems.pills  # noqa: E402,F401  phase 5b: pills, residue, venom on a blade
import systems.poison_path  # noqa: E402,F401  phase 5b: the poison path, venomous beasts, tempering baths
import systems.pill_hall  # noqa: E402,F401  phase 5c: sects' pill halls and herb gardens
import systems.guild  # noqa: E402,F401  phase 5c: the Alchemists' Guild
import systems.recipe_trade  # noqa: E402,F401  phase 5c: recipe scrolls bought, given, taught and sold
import systems.hall_theft  # noqa: E402,F401  phase 5c: gardens and halls robbed by night
import systems.physic  # noqa: E402,F401  phase 5c: physicians, famous doctors, healers and poisoners for hire
import systems.npc_alchemy  # noqa: E402,F401  phase 5c: NPCs refine and take pills in their seasons
import systems.control  # noqa: E402,F401  phase 5c: control pills, their masters and their bound
import systems.materials  # noqa: E402,F401  phase 5d: materials and the forge
import systems.forging  # noqa: E402,F401  phase 5d: forging, refining and masterworks
import systems.formations  # noqa: E402,F401  phase 5d: formation patterns, flags and laying
import systems.arrays  # noqa: E402,F401  phase 5d: what formations do
import systems.craft_world  # noqa: E402,F401  phase 5d: smiths and formation masters, and their commissions
import systems.meet  # noqa: E402,F401  phase 5d: the Meet of Hammer and Furnace
import systems.heart  # noqa: E402,F401  phase 5e: the dao heart, and the deeds that move it
