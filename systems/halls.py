"""Where factions live in a town (phase 3b spec 3.1, 3.3): seats, branch halls, staff, natural members."""

from systems import factions as F
from systems.realms import REALMS
from world.gen.materialize import ensure_town, people_at, populate, region_of
from world.gen.names import person_name
from world.gen.npc import PORTRAIT_PARTS, TRAITS
from world.seed import rng_for

SEAT_STAFF = (("leader", 4, None), ("elder", 3, 0), ("elder", 3, 1), ("keeper", 2, None),
              ("disciple", 0, 0), ("disciple", 0, 1), ("disciple", 1, 0), ("disciple", 1, 1))
CAPITAL_STAFF = (("leader", 4, None), ("keeper", 2, None))
BRANCH_STAFF = (("keeper", 2, None), ("disciple", 0, 0), ("disciple", 1, 1))
REALM_BONUS = {"leader": 2, "elder": 1, "keeper": 0, "disciple": 0}
DARK_TRAITS = ("cunning", "hot-tempered", "proud")
BRANCH_RADIUS, BRANCH_CHANCE = 2, 0.35
NATURAL_OCCUPATION = {kind: job for job, kind in F.NATURAL.items()}
RECRUITERS = frozenset({"leader", "elder", "keeper"})


def _hire(world, faction, town_id: int, staff) -> None:
    kind = faction.data["type"]
    for i, (role, rank, hall) in enumerate(staff):
        path = f"{faction.seed_path}/member:{town_id}:{i}"
        if world.entity_by_seed(path) is not None:
            continue
        rng = rng_for(world.world_seed, path)
        surname, given = person_name(rng)
        realm = REALMS[min(len(REALMS) - 1, F.BASE_REALM.get(kind, 0) + REALM_BONUS[role])].label
        first = rng.choice(DARK_TRAITS) if faction.data["path"] == "ruthless" else rng.choice(TRAITS)
        traits = list(dict.fromkeys([first, rng.choice(TRAITS)]))
        occupation = "hall keeper" if role == "keeper" else F.title(world, faction.id, rank)
        data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": rng.randint(18, 70),
                "occupation": occupation, "traits": traits, "realm": realm,
                "portrait": {part: rng.randrange(count) for part, count in PORTRAIT_PARTS.items()}}
        person = world.add_entity("person", f"{surname} {given}", data, path)
        world.relate(person, town_id, "located_in")
        world.relate(person, faction.id, "member_of", rank,
                     {"role": role, "hall": hall, "merit": 0, "status": "member", "secret": False})


def _natural_present(world, town_id: int, kind: str) -> bool:
    job = NATURAL_OCCUPATION.get(kind)
    return job is not None and any(p.data.get("occupation") == job for p in people_at(world, town_id))


def _has_branch(world, faction, town) -> bool:
    kind = faction.data["type"]
    if kind in F.BRANCHING:
        near = F.gap(faction.data["home"], (town.data["x"], town.data["y"])) <= BRANCH_RADIUS
        return near and rng_for(world.world_seed, f"branch:{faction.id}:{town.id}").random() < BRANCH_CHANCE
    return kind in NATURAL_OCCUPATION and _natural_present(world, town.id, kind)


def _enrol_natural(world, town_id: int, roster: list[int]) -> None:
    by_type = {world.entity(fid).data["type"]: fid for fid in roster}
    for person in people_at(world, town_id):
        kind = F.NATURAL.get(person.data.get("occupation"))
        if kind in by_type and F.membership(world, person.id, by_type[kind]) is None \
                and not person.data.get("is_player"):
            world.relate(person.id, by_type[kind], "member_of", 0,
                         {"role": "member", "hall": None, "merit": 0, "status": "member", "secret": False})


def settle_town(world, town_id: int) -> None:
    """Put every faction that lives here into the town: seat, branch hall, staff, natural members. Once."""
    town = world.entity(town_id)
    if town is None or town.kind != "town" or town.data.get("factions_ready"):
        return
    populate(world, town_id)
    roster = F.ensure_roster(world)
    minors = F.minor_factions(world, region_of(world, town_id))
    here, seats = [], []
    with world.transaction():
        for fid in roster + minors:
            faction = world.entity(fid)
            if faction.data.get("dissolved"):
                continue  # a destroyed faction is never re-staffed (phase 4a ruling 8)
            kind = faction.data["type"]
            if faction.data["tier"] == "minor":
                is_seat = faction.data["seat"] == town_id
            else:
                is_seat = tuple(faction.data["home"]) == (town.data["x"], town.data["y"]) and town.data["index"] == 0
            if is_seat:
                here.append(fid)
                seats.append(fid)
                world.update_data(fid, seat=town_id)
                staff = SEAT_STAFF if kind in F.STAFFED else () if kind == "alliance" else CAPITAL_STAFF
                _hire(world, world.entity(fid), town_id, staff)
            elif _has_branch(world, faction, town):
                here.append(fid)
                world.update_data(fid, branches=[*faction.data["branches"], town_id])
                if kind in F.STAFFED:
                    _hire(world, world.entity(fid), town_id, BRANCH_STAFF)
        _enrol_natural(world, town_id, roster)
        world.update_data(town_id, factions_ready=True, halls=here, seats=seats)


def seat_of(world, faction_id: int) -> int:
    """The faction's seat town, created and settled if nobody has been there yet."""
    faction = world.entity(faction_id)
    seat = faction.data.get("seat")
    if seat is None:
        x, y = faction.data["home"]
        seat = ensure_town(world, x, y, 0)
    settle_town(world, seat)
    return world.entity(faction_id).data["seat"] or seat


def halls_here(world, town_id: int) -> list[int]:
    town = world.entity(town_id)
    return list(town.data.get("halls", [])) if town is not None else []


def staff_at(world, faction_id: int, town_id: int, roles=None) -> list[int]:
    out = []
    for person in people_at(world, town_id):
        found = F.membership(world, person.id, faction_id)
        if found and found[1].get("status", "member") == "member" and found[1].get("role") != "member" \
                and (roles is None or found[1].get("role") in roles):
            out.append(person.id)
    return out


def keeper_at(world, faction_id: int, town_id: int) -> int | None:
    """Who keeps this faction's hall here: its hall keeper, else a natural member standing in."""
    keepers = staff_at(world, faction_id, town_id, roles=("keeper",))
    if keepers:
        return keepers[0]
    if faction_id not in halls_here(world, town_id):
        return None
    natural = [p.id for p in people_at(world, town_id)
               if (F.membership(world, p.id, faction_id) or (0, {}))[1].get("role") == "member"
               and not p.data.get("is_player")]
    return natural[0] if natural else None


def elders(world, faction_id: int) -> dict[int, int]:
    seat = seat_of(world, faction_id)
    out = {}
    for person in staff_at(world, faction_id, seat, roles=("elder",)):
        out[F.membership(world, person, faction_id)[1]["hall"]] = person
    return out


def recruits_for(world, npc_id: int) -> list[int]:
    """Factions this person can speak for here: staff above disciple, or the keeper of a natural hall."""
    town = next(iter(world.targets(npc_id, "located_in")), None)
    out = []
    for fid, _, data in F.memberships(world, npc_id):
        if data.get("status", "member") != "member" or world.entity(fid).data["type"] == "player_sect":
            continue  # the player's own sect has its own business (phase 3c)
        if data.get("role") in RECRUITERS or (town is not None and keeper_at(world, fid, town) == npc_id):
            out.append(fid)
    return out


def faction_tag(world, person_id: int, town_id: int) -> str | None:
    """The faction someone visibly belongs to here (staff and hall members wear its insignia)."""
    for fid in halls_here(world, town_id):
        found = F.membership(world, person_id, fid)
        if found and found[1].get("status", "member") == "member":
            return world.entity(fid).name
    return None
