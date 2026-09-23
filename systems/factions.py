"""Factions in the world (phase 3b spec 3): the great roster, minor factions, stances and members.

A faction is an entity; membership is the `member_of` relation (person -> faction,
value = rank, data = {role, merit, hall, sponsor, secret, joined_at, status, ...}).
"""

from systems.techniques import FORMS
from world.gen.materialize import ensure_town
from world.gen.names import person_name
from world.gen.region import region_spec
from world.seed import rng_for

LADDERS = {
    "orthodox_sect": ("outer disciple", "inner disciple", "core disciple", "elder", "sect leader"),
    "school": ("outer disciple", "inner disciple", "core disciple", "elder", "sect leader"),
    "demonic_cult": ("blood servant", "cult follower", "blood envoy", "cult elder", "cult master"),
    "unorthodox_clan": ("apprentice", "poisoner", "master poisoner", "elder", "valley master"),
    "martial_clan": ("retainer", "sworn retainer", "household guard", "clan elder", "clan head"),
    "local_clan": ("retainer", "sworn retainer", "household guard", "clan elder", "clan head"),
    "beggars": ("one-pouch beggar", "three-pouch beggar", "five-pouch beggar", "seven-pouch elder", "nine-pouch chief"),
    "merchant_guild": ("associate", "factor", "senior factor", "master", "guild head"),
    "imperial": ("constable", "senior constable", "inspector", "commander", "bureau chief"),
    "alliance": ("envoy", "warden", "senior warden", "elder", "alliance master"),
    "bandit_fort": ("lackey", "bandit", "lieutenant", "second", "chief"),
}
PATHS = {"orthodox_sect": "righteous", "school": "righteous", "imperial": "righteous", "alliance": "righteous",
         "demonic_cult": "ruthless", "unorthodox_clan": "ruthless", "bandit_fort": "ruthless"}
MARTIAL = frozenset({"orthodox_sect", "school", "demonic_cult", "unorthodox_clan", "bandit_fort"})
STAFFED = frozenset({"orthodox_sect", "school", "demonic_cult", "unorthodox_clan", "martial_clan", "local_clan",
                     "bandit_fort"})
BRANCHING = frozenset({"orthodox_sect", "demonic_cult", "unorthodox_clan", "martial_clan"})
NATURAL = {"constable": "imperial", "beggar": "beggars", "merchant": "merchant_guild"}
FAVOURED = {
    "orthodox_sect": ("sword", "palm", "fist"), "school": ("fist", "sword"), "demonic_cult": ("palm", "saber"),
    "unorthodox_clan": ("palm", "finger"), "martial_clan": ("saber", "spear"), "local_clan": ("saber", "staff"),
    "beggars": ("staff", "palm"), "merchant_guild": ("saber",), "imperial": ("saber", "spear"),
    "alliance": ("sword",), "bandit_fort": ("saber",),
}
BASE_REALM = {"orthodox_sect": 1, "demonic_cult": 1, "unorthodox_clan": 1, "imperial": 1}
ROSTER = (("orthodox_sect", 3), ("demonic_cult", 1), ("unorthodox_clan", 1), ("martial_clan", 1),
          ("beggars", 1), ("merchant_guild", 1), ("imperial", 1), ("alliance", 1))
CAPITAL_TYPES = frozenset({"beggars", "merchant_guild", "imperial", "alliance"})
HOME_RADIUS, FIRST_SECT_RADIUS, CAPITAL_RADIUS = 6, 2, 3
HOSTILE = -0.5
DARK = frozenset({"demonic_cult", "unorthodox_clan"})

SECT_A = ("Azure", "Pure", "Iron", "Jade", "White", "Green", "Golden", "Heavenly")
SECT_B = ("Cloud", "Summit", "Sword", "Pine", "Lotus", "Crane", "Peak", "Spring")
CULT_A = ("Blood", "Night", "Heaven-Devouring", "Black", "Crimson", "Shadow")
CULT_B = ("Lotus", "Moon", "Demon", "Serpent", "Flame")
POISON_A = ("Ten Thousand", "Five", "Black", "Hundred")
POISON_B = ("Valley", "Clan", "Hall")
GUILD_A = ("Golden River", "Jade Road", "Silk Road", "Grand Canal", "Salt Harbour")
SCHOOL_B = ("Fist", "Blade", "Staff", "Willow", "Stone")
FORT_A = ("Black Wind", "Red Cliff", "Tiger Head", "Wolf Fang")
FORT_B = ("Fort", "Stronghold", "Camp")
NAMERS = {
    "orthodox_sect": lambda rng: f"{rng.choice(SECT_A)} {rng.choice(SECT_B)} Sect",
    "demonic_cult": lambda rng: f"{rng.choice(CULT_A)} {rng.choice(CULT_B)} Cult",
    "unorthodox_clan": lambda rng: f"{rng.choice(POISON_A)} Poison {rng.choice(POISON_B)}",
    "martial_clan": lambda rng: f"{person_name(rng)[0]} Clan",
    "local_clan": lambda rng: f"{person_name(rng)[0]} Clan",
    "beggars": lambda rng: "Beggars' Sect",
    "merchant_guild": lambda rng: f"{rng.choice(GUILD_A)} Merchant Guild",
    "imperial": lambda rng: "Imperial Martial Bureau",
    "alliance": lambda rng: "Orthodox Martial Alliance",
    "school": lambda rng: f"{rng.choice(SECT_A)} {rng.choice(SCHOOL_B)} School",
    "bandit_fort": lambda rng: f"{rng.choice(FORT_A)} {rng.choice(FORT_B)}",
}


def gap(a, b) -> int:
    """Regions between two (x, y) homes (Chebyshev)."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def base_stance(a: str, b: str) -> float:
    pair = {a, b}
    if a == b == "orthodox_sect":
        return 0.6
    if pair == {"orthodox_sect", "alliance"}:
        return 0.8
    if pair & {"orthodox_sect", "alliance"} and pair & DARK and len(pair) == 2:
        return -0.8
    if pair == {"imperial", "demonic_cult"}:
        return -0.6
    if pair == {"imperial", "orthodox_sect"}:
        return 0.2
    if pair == {"demonic_cult", "unorthodox_clan"}:
        return 0.2
    if "bandit_fort" in pair and pair & {"orthodox_sect", "school", "imperial"}:
        return -0.5
    return 0.0


def _name(rng, kind: str, used: set) -> str:
    for _ in range(30):
        name = NAMERS[kind](rng)
        if name not in used:
            used.add(name)
            return name
    name = f"{NAMERS[kind](rng)} of the {len(used)}th Gate"
    used.add(name)
    return name


def _make(world, rng, kind: str, tier: str, home, path: str, used: set) -> int:
    wealth = rng.randint(30, 90)
    data = {"type": kind, "tier": tier, "home": list(home), "seat": None, "path": PATHS.get(kind, "neutral"),
            "ranks": list(LADDERS[kind]), "power": rng.randint(40, 90), "wealth": wealth, "treasury": wealth * 10,
            "forms": [f for f in FAVOURED[kind] if f in FORMS] or list(FORMS[:1]), "arts": [], "branches": []}
    return world.add_entity("faction", _name(rng, kind, used), data, path)


def _capital(world) -> tuple[int, int]:
    """The most populous region near the start: where the empire and the great guilds sit."""
    options = [(x, y) for x in range(-CAPITAL_RADIUS, CAPITAL_RADIUS + 1) for y in range(-CAPITAL_RADIUS, CAPITAL_RADIUS + 1)]
    return min(options, key=lambda c: (-region_spec(world.world_seed, *c).town_count, abs(c[0]) + abs(c[1]), c))


def _set_stances(world, ids: list[int], others: list[int]) -> None:
    for a in ids:
        for b in others:
            if a == b:
                continue
            value = base_stance(world.entity(a).data["type"], world.entity(b).data["type"])
            if value:
                world.relate(a, b, "stance", value)
                world.relate(b, a, "stance", value)


def ensure_roster(world) -> list[int]:
    """The world's ten great factions, created once from the world seed."""
    found = world.get_meta("roster")
    if found:
        return list(found)
    rng = rng_for(world.world_seed, "world/factions")
    capital = _capital(world)
    used: set = set()
    ids: list[int] = []
    first_sect = True
    with world.transaction():
        for kind, count in ROSTER:
            for _ in range(count):
                if kind in CAPITAL_TYPES:
                    home = capital
                elif kind == "orthodox_sect" and first_sect:
                    home, first_sect = (rng.randint(-FIRST_SECT_RADIUS, FIRST_SECT_RADIUS),
                                        rng.randint(-FIRST_SECT_RADIUS, FIRST_SECT_RADIUS)), False
                else:
                    home = (rng.randint(-HOME_RADIUS, HOME_RADIUS), rng.randint(-HOME_RADIUS, HOME_RADIUS))
                ids.append(_make(world, rng, kind, "great", home, f"world/faction:{len(ids)}", used))
        _set_stances(world, ids, ids)
        world.set_meta("roster", ids)
    return ids


def minor_factions(world, region) -> list[int]:
    """0-2 small local factions of a region, seeded and created the first time it is settled."""
    if region.data.get("minors_ready"):
        return list(region.data.get("minors", []))
    roster = ensure_roster(world)
    rng = rng_for(world.world_seed, f"{region.seed_path}/minor")
    x, y = region.data["x"], region.data["y"]
    ids: list[int] = []
    with world.transaction():
        for i in range(rng.choice((0, 1, 1, 2))):
            kind = rng.choice(("school", "bandit_fort", "local_clan"))
            seat = ensure_town(world, x, y, rng.randrange(region.data["town_count"]))
            fid = _make(world, rng, kind, "minor", (x, y), f"{region.seed_path}/minor:{i}", set())
            world.update_data(fid, seat=seat)
            ids.append(fid)
        _set_stances(world, ids, roster + ids)
        world.update_data(region.id, minors_ready=True, minors=ids)
    return ids


def stance(world, a: int, b: int) -> float:
    if a == b:
        return 1.0
    for other, value, _ in world.relations_from(a, "stance"):
        if other == b:
            return value
    return 0.0


def memberships(world, person_id) -> list[tuple[int, int, dict]]:
    if not isinstance(person_id, int):
        return []
    return [(fid, int(rank), data) for fid, rank, data in world.relations_from(person_id, "member_of")]


def membership(world, person_id, faction_id) -> tuple[int, dict] | None:
    return next(((rank, data) for fid, rank, data in memberships(world, person_id) if fid == faction_id), None)


def members_of(world, faction_id: int) -> list[int]:
    """Living members in good standing."""
    out = []
    for person in world.sources(faction_id, "member_of"):
        entity = world.entity(person)
        found = membership(world, person, faction_id)
        if entity is not None and not entity.data.get("dead") and found and found[1].get("status", "member") == "member":
            out.append(person)
    return out


def is_martial(world, faction_id: int) -> bool:
    return world.entity(faction_id).data["type"] in MARTIAL


def title(world, faction_id: int, rank: int) -> str:
    ranks = world.entity(faction_id).data["ranks"]
    return ranks[max(0, min(rank, len(ranks) - 1))]
