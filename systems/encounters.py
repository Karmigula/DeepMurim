"""Road encounters and grudge challenges (phase 2 spec §10).

Bandits, beasts and rival wanderers are real people of their region: they are
materialized once, live in the region (not a town), and remember you.
"""

from systems.duel import fighter_for
from systems.combat_core import flee_chance
from systems.items import create_manual
from systems.purse import silver_of
from systems.realms import realm_index
from systems.techniques import create_technique, generate
from world.events import Event, Witness, effect  # noqa: F401  (Witness re-exported for callers)
from world.gen.materialize import people_at, region_of
from world.gen.names import person_name
from world.gen.npc import PORTRAIT_PARTS, TRAITS
from world.gen.region import region_path
from world.seed import rng_for

ENCOUNTER_CHANCE = 0.35
CHALLENGE_CHANCE = 0.3
BANDIT_MANUAL_CHANCE = 0.25
GRUDGE_FEELINGS = frozenset({"annoyed", "humiliated", "hatred"})  # spec §10; contempt is theirs, not a grudge
BEASTS = {"forest": ("grey wolf", "wild boar"), "mountains": ("mountain tiger", "grey wolf"), "marsh": ("marsh crocodile",)}
FRIENDLY = frozenset({"kind", "lazy", "cheerful", "honest"})


def region_danger(world_seed: int, x: int, y: int) -> float:
    if (x, y) == (0, 0):
        return 0.1  # the starting region is gentle
    return round(rng_for(world_seed, f"{region_path(x, y)}/danger").random() ** 1.5, 3)


def _realm_for(danger: float, rng) -> str:
    roll = danger + rng.uniform(-0.15, 0.15)
    return "mortal" if roll < 0.35 else "third-rate" if roll < 0.65 else "second-rate" if roll < 0.9 else "first-rate"


def roamers(world, region_id: int) -> list[int]:
    return [p for p in world.sources(region_id, "located_in") if world.entity(p).data.get("roamer")]


def make_roamer(world, region, kind: str, index: int, danger: float) -> int:
    path = f"{region.seed_path}/roamer:{index}"
    existing = world.entity_by_seed(path)
    if existing is not None:
        return existing.id
    rng = rng_for(world.world_seed, path)
    realm = _realm_for(danger, rng)
    if kind == "beast":
        species = rng.choice(BEASTS.get(region.data["terrain"], ("grey wolf",)))
        name = f"a {species}"
        data = {"beast": True, "occupation": species, "traits": ["hot-tempered"], "realm": realm,
                "roamer": True, "roamer_kind": kind, "silver": 0}
    else:
        surname, given = person_name(rng)
        occupation = "bandit" if kind == "bandit" else "wandering swordsman"
        traits = list(dict.fromkeys(["greedy", rng.choice(TRAITS)])) if kind == "bandit" else rng.sample(TRAITS, 2)
        name = f"{surname} {given}"
        data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": rng.randint(18, 55),
                "occupation": occupation, "traits": traits, "realm": realm, "roamer": True, "roamer_kind": kind,
                "portrait": {part: rng.randrange(count) for part, count in PORTRAIT_PARTS.items()}}
    with world.transaction():
        person = world.add_entity("person", name, data, path)
        world.relate(person, region.id, "located_in")
        if kind == "bandit" and rng.random() < BANDIT_MANUAL_CHANCE:
            art_name, art = generate(rng, "martial", grade=1 + realm_index(realm))
            create_manual(world, person, create_technique(world, art_name, art), rng.uniform(0.4, 1.0))
    return person


def encounter_events(player: int, person: int, place: int, kind: str, toll: int) -> list[Event]:
    return [Event("encounter", (player, person), place, {"kind": kind, "toll": int(toll)})]


def road_encounter_events(world, player: int, town) -> list[Event]:
    region = region_of(world, town.id)
    danger = region_danger(world.world_seed, region.data["x"], region.data["y"])
    rng = rng_for(world.world_seed, f"road:{player}:{world.time}")
    if rng.random() >= danger * ENCOUNTER_CHANCE:
        return []
    kinds = ["bandit", "wanderer"] + (["beast"] if region.data["terrain"] in BEASTS else [])
    kind = rng.choice(kinds)
    known = [p for p in roamers(world, region.id) if world.entity(p).data.get("roamer_kind") == kind]
    if known and rng.random() < 0.5:
        person = rng.choice(known)
    else:
        person = make_roamer(world, region, kind, len(roamers(world, region.id)), danger)
    toll = max(5, int(silver_of(world, player) * 0.2)) if kind == "bandit" else 0
    return encounter_events(player, person, town.id, kind, toll)


def encounter_state(event) -> dict:
    return {"person": event.actors[1], "kind": event.data["kind"], "toll": event.data["toll"]}


def resolved_events(player: int, person: int, place: int, how: str, kind: str) -> list[Event]:
    feeling = {"paid": "contempt", "fled": "contempt", "talked": "amused"}.get(how)
    witnesses = (Witness(person, feeling, 0.3),) if feeling else ()
    return [Event("encounter_resolved", (player, person), place, {"how": how, "kind": kind}, witnesses=witnesses)]


def talk_succeeds(world, person: int, player: int) -> bool:
    entity = world.entity(person)
    if entity.data.get("beast"):
        return False
    rng = rng_for(world.world_seed, f"roadtalk:{person}:{world.time}")
    if entity.data.get("roamer_kind") == "wanderer":
        return rng.random() < 0.8
    friendly = 0.3 if FRIENDLY & set(entity.data.get("traits", ())) else 0.0
    return rng.random() < 0.25 + friendly


def flee_succeeds(world, player: int, person: int) -> bool:
    rng = rng_for(world.world_seed, f"roadflee:{person}:{world.time}")
    return rng.random() < flee_chance(fighter_for(world, player, None), fighter_for(world, person, None), 0.0)


def challenge_from(world, player: int, place: int) -> int | None:
    rng = rng_for(world.world_seed, f"challenge:{player}:{place}:{world.time}")
    settled = {e.actors[1] for e in world.chronicle_about(player, limit=20)
               if e.kind in ("challenge_issued", "declined_challenge") and e.time == world.time}
    for person in people_at(world, place, exclude=player):
        if person.id in settled:
            continue  # already challenged you this very moment
        if not set(person.data.get("traits", ())) & {"proud", "hot-tempered"}:
            continue
        grudges = [m for m in world.memories(person.id, about=player) if m.feeling in GRUDGE_FEELINGS]
        if grudges and rng.random() < CHALLENGE_CHANCE:
            return person.id
    return None


def challenge_events(player: int, npc: int, place: int) -> list[Event]:
    return [Event("challenge_issued", (player, npc), place, {})]


def decline_events(player: int, npc: int, place: int) -> list[Event]:
    return [Event("declined_challenge", (player, npc), place, {}, witnesses=(Witness(npc, "contempt", 0.4),))]


def pending_encounter(world, player: int) -> dict | None:
    for entry in world.chronicle_about(player, limit=30):  # newest first
        if entry.kind in ("encounter_resolved", "travelled", "duel_started"):
            return None
        if entry.kind == "encounter":
            return {"person": entry.actors[1], "kind": entry.data["kind"], "toll": entry.data["toll"]}
    return None


def pending_challenge(world, player: int) -> int | None:
    for entry in world.chronicle_about(player, limit=30):
        if entry.kind in ("declined_challenge", "duel_started", "travelled"):
            return None
        if entry.kind == "challenge_issued":
            return entry.actors[1]
    return None
