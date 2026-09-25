"""Secret realms (phase 4f spec 2): sealed pocket worlds that open for a few days.

A realm is a lasting `secret_realm` entity at a gate town: its master and their art, its entry
rule, its period, its floors of chambers, and its history. Each opening is a 4d world-event
occurrence (`realm_opening`; `realm_awakening` for a newborn realm's first). Three ancient realms
are seeded into every world the first time anything asks (old saves too, never backdated); newborn
realms are cracked open by treasure lights.
"""

import systems.world_events as W
from systems.techniques import create_technique, generate
from world.events import Event, commit, listen
from world.gen.materialize import ensure_town
from world.gen.region import region_spec
from world.seed import rng_for

ANCIENT = 3
ANCIENT_PERIOD = (12, 40)
NEWBORN_PERIOD = (8, 20)
ONE_OFF_CHANCE = 0.6
CRACK_CHANCE = 0.25
GATE_RADIUS = 6
OPENINGS = ("realm_opening", "realm_awakening")
PLACES = ("Sunken Palace", "Cloud-Veiled Cave", "Nine Dragon Tomb", "Jade Valley", "Bronze Pagoda", "Frozen Abyss",
          "Moonlit Garden", "Thousand-Sword Mound")
EPITHETS = ("Azure Sage", "Crimson Emperor", "White Crane Immortal", "Iron-Blood Tyrant", "Silent Moon Nun",
            "Nine-Fingered Demon", "Wandering Sword Saint", "Jade Maiden")
WEAPONS = ("sword", "saber", "spear", "staff", "fan", "pair of gauntlets")
GUARDIANS = ("bronze puppet", "stone lion", "jade serpent", "iron-feathered roc", "ghost-fire wolf")
TRIALS = ("formation", "pressure", "mirror")
RULES_ANCIENT = (("ceiling", 0.5), ("token", 0.3), ("quota", 0.2))
RULES_NEWBORN = (("open", 0.6), ("token", 0.4))
CHAMBER_WEIGHTS = (("treasure", 3), ("guardian", 3), ("trial", 2), ("rivals", 2))


def _pick(rng, table) -> str:
    roll, total = rng.random(), 0.0
    for name, chance in table:
        total += chance
        if roll < total:
            return name
    return table[-1][0]


# --- the layout ---------------------------------------------------------------------------------

def prize_at(rng, floor: int) -> dict:
    """A treasure for a chamber on this floor (1 is the first): 4d's prizes, richer the deeper (spec §3.2)."""
    from systems.races import prize_for
    prize = prize_for(rng.choice(("treasure_light", "treasure_light", "star_fall")), rng)
    scale = 1 + 0.5 * floor
    if "value" in prize:
        prize["value"] = int(prize["value"] * scale)
    if "qi_years" in prize:
        prize["qi_years"] = round(prize["qi_years"] * scale, 2)
    if prize["kind"] == "manual":
        prize["grade"] = min(4, prize["grade"] + floor // 2)
        prize["completeness"] = round(min(1.0, prize["completeness"] + 0.05 * floor), 2)
    return prize


def chamber(rng, kind: str, floor: int) -> dict:
    contents: dict = {}
    if kind == "treasure":
        contents = {"prize": prize_at(rng, floor)}
    elif kind == "guardian":
        contents = {"species": rng.choice(GUARDIANS), "realm": min(4, floor + 1), "guardian": None}
    elif kind == "trial":
        contents = {"trial": rng.choice(TRIALS)}
    return {"kind": kind, "state": "untouched", "contents": contents}


def layout(rng, floors: int) -> list[list[dict]]:
    """Floors of 2-4 chambers: each ends in its stair down, the last in the inheritance."""
    out = []
    kinds = [k for k, _ in CHAMBER_WEIGHTS]
    weights = [w for _, w in CHAMBER_WEIGHTS]
    for f in range(1, floors + 1):
        chambers = [chamber(rng, rng.choices(kinds, weights=weights)[0], f) for _ in range(rng.randint(1, 3))]
        chambers.append(chamber(rng, "inheritance" if f == floors else "stair", f))
        out.append(chambers)
    return out


# --- making realms ----------------------------------------------------------------------------------

def make_realm(world, gate: int, path: str, ancient: bool, n: int) -> int:
    rng = rng_for(world.world_seed, path)
    epithet = rng.choice(EPITHETS)
    art_name, art = generate(rng, "martial", grade=4 if ancient else 3)
    art_id = create_technique(world, art_name, art)
    floors = rng.randint(3, 6) if ancient else rng.randint(3, 4)
    rule = _pick(rng, RULES_ANCIENT if ancient else RULES_NEWBORN)
    value = rng.choice(("second-rate", "first-rate")) if rule == "ceiling" else None
    if ancient:
        period = rng.randint(*ANCIENT_PERIOD)
        next_opening = n + rng.randint(2, period)  # ahead, never backdated (an old save's too)
    else:
        period = None if rng.random() < ONE_OFF_CHANCE else rng.randint(*NEWBORN_PERIOD)
        next_opening = None  # its first opening is the awakening
    data = {"gate": gate, "ancient": ancient,
            "master": {"name": f"the {epithet}", "art": art_id, "weapon": f"the {epithet}'s {rng.choice(WEAPONS)}"},
            "rule": {"kind": rule, "value": value}, "period": period, "next_opening": next_opening,
            "floors": layout(rng, floors), "history": [], "inheritance_claimed_by": None, "sealed": []}
    return world.add_entity("secret_realm", f"the {rng.choice(PLACES)} of the {epithet}", data, path)


def realms(world) -> list[int]:
    """The realms made so far, without making any: a read (a look, a page) must never write."""
    return list(world.get_meta("secret_realms") or [])


def ensure_realms(world) -> list[int]:
    """Every realm, ancient first; the three ancient ones are seeded the first time anyone asks."""
    found = world.get_meta("secret_realms")
    if found is not None:
        return list(found)
    n = world.time // W.SEASON
    rng = rng_for(world.world_seed, "realms:ancient")
    made = []
    for k in range(ANCIENT):
        x, y = rng.randint(-GATE_RADIUS, GATE_RADIUS), rng.randint(-GATE_RADIUS, GATE_RADIUS)
        gate = ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))
        made.append(make_realm(world, gate, f"realm:ancient:{k}", True, n))
    world.set_meta("secret_realms", made)
    return made


# --- openings ------------------------------------------------------------------------------------

def due(world, n: int) -> list[int]:
    """Realms opening in season `n`. An opening missed (a long catch-up passed it) rolls on to its next turn."""
    found = []
    for realm in ensure_realms(world):
        data = world.entity(realm).data
        nxt, period = data["next_opening"], data["period"]
        if nxt is not None and nxt < n:
            nxt = nxt + period * ((n - nxt + period - 1) // period) if period else None
            world.update_data(realm, next_opening=nxt)
        if nxt == n:
            found.append(realm)
    return found


def opening_data(realm: int) -> dict:
    return {"realm": realm, "delvers": [], "teams": [], "tokens": [], "entered": [], "closed": False}


def stage_of(world, occurrence: int) -> str:
    return W.stage_at(world.entity(occurrence).data, world.time)


def opening_of(world, realm: int) -> int | None:
    """The live opening of this realm, if one is under way."""
    for row in W.index(world):
        if row[W.TYPE] in OPENINGS and not row[W.DONE] and world.entity(row[W.ID]).data["data"]["realm"] == realm:
            return row[W.ID]
    return None


def on_stage(world, occurrence, stage: str) -> list[Event]:
    return []


def on_observe(world, occurrence) -> list[Event]:
    return []


@listen("sky_started")
def _started(world, event, event_id: int) -> None:
    """An opening moves its realm's clock on; a treasure light that cracks a realm open makes it (spec §4.6)."""
    import systems.sky as sky
    d = event.data
    n = d["starts"] // W.SEASON
    if d["type"] in OPENINGS:
        realm = world.entity(d["data"]["realm"])
        period = realm.data["period"]
        world.update_data(realm.id, next_opening=n + period if period else None)
    elif d["type"] == "treasure_light" and d["data"].get("cracked"):
        realms = ensure_realms(world)
        realm = make_realm(world, d["place"], f"realm:newborn:{event_id}", False, n)
        world.set_meta("secret_realms", realms + [realm])
        commit(world, sky.start_events(world, "realm_awakening", d["place"], d["starts"], opening_data(realm)))
