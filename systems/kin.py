"""Families and teachers (phase 3a spec §6): generated only when needed, and heirs to grudges.

Relation kin_of (a -> b, data {"role": r}) reads "b is a's r". A death passes the
victim's indelible memories to their kin, who also grieve; kin hear of anything
done to or by their family at once, wherever they live (channel 3).
"""

from systems.beliefs import CONF_DECAY, appears_as, believe
from systems.facts import on_fact
from systems.realms import REALMS, realm_index
from world.events import effect, listen
from world.gen.materialize import ensure_town, region_of
from world.gen.names import person_name
from world.gen.npc import OCCUPATIONS, PORTRAIT_PARTS, TRAITS
from world.gen.npc import REALMS as NPC_REALMS
from world.gen.region import region_spec
from world.seed import rng_for

KIN_ROLES = ("sibling", "parent", "child", "master", "disciple")
INVERSE = {"sibling": "sibling", "parent": "child", "child": "parent", "master": "disciple", "disciple": "master"}
BLOOD = frozenset({"sibling", "parent", "child"})
NEAR_CHANCE = 0.7
FAR = 2                 # regions
PAUSE_WATCHES = 360     # a spared avenger stops hunting for a season
AGE_SHIFT = {"parent": (18, 30), "child": (-30, -18), "sibling": (-8, 8), "master": (10, 30), "disciple": (-20, -5)}


def _key(npc) -> str:
    return npc.seed_path or f"person:{npc.id}"


def kin_slots(world, npc) -> list[dict]:
    rng = rng_for(world.world_seed, f"{_key(npc)}/kin")
    return [{"i": i, "role": rng.choice(KIN_ROLES), "near": rng.random() < NEAR_CHANCE,
             "dx": rng.randint(-FAR, FAR), "dy": rng.randint(-FAR, FAR), "town": rng.randrange(8)}
            for i in range(rng.randint(1, 3))]


def _home(world, origin_id: int, slot: dict) -> int:
    origin = world.entity(origin_id)
    if slot["near"] and origin.kind == "town":
        return origin.id
    region = origin if origin.kind == "region" else region_of(world, origin.id)
    if slot["near"]:
        return ensure_town(world, region.data["x"], region.data["y"], 0)
    x, y = region.data["x"] + slot["dx"], region.data["y"] + slot["dy"]
    return ensure_town(world, x, y, slot["town"] % region_spec(world.world_seed, x, y).town_count)


def _make_kin(world, npc, slot: dict, path: str, home: int) -> int:
    rng = rng_for(world.world_seed, path)
    surname, given = person_name(rng)
    if slot["role"] in BLOOD and npc.data.get("surname"):
        surname = npc.data["surname"]
    low, high = AGE_SHIFT[slot["role"]]
    age = max(8, min(90, int(npc.data.get("age", 30)) + rng.randint(low, high)))
    realm = rng.choice(NPC_REALMS)
    if slot["role"] == "master":
        realm = REALMS[min(realm_index(npc.data.get("realm", "mortal")) + 1, 3)].label
    data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": age,
            "occupation": rng.choice(OCCUPATIONS), "traits": rng.sample(TRAITS, 2), "realm": realm,
            "portrait": {part: rng.randrange(count) for part, count in PORTRAIT_PARTS.items()},
            "kin_ready": True}  # a relative brings no relatives of their own (phase 4a review)
    person = world.add_entity("person", f"{surname} {given}", data, path)
    world.relate(person, home, "located_in")
    return person


def kin_of(world, npc_id: int) -> list[tuple[int, str]]:
    """Living kin already in the world."""
    out = []
    for kin, _, data in world.relations_from(npc_id, "kin_of"):
        entity = world.entity(kin)
        if entity is not None and not entity.data.get("dead"):
            out.append((kin, data.get("role")))
    return out


def ensure_kin(world, npc_id: int, origin: int | None = None) -> list[tuple[int, str]]:
    """Materialize this person's seeded kin once (at a death, a question, a rumour)."""
    npc = world.entity(npc_id)
    if npc is None or npc.kind != "person" or npc.data.get("beast") or npc.data.get("is_player"):
        return []
    if npc.data.get("kin_ready"):
        return kin_of(world, npc_id)
    origin = origin or next(iter(world.targets(npc_id, "located_in")), None)
    with world.transaction():
        if origin is not None:
            for slot in kin_slots(world, npc):
                path = f"{_key(npc)}/kin:{slot['i']}"
                found = world.entity_by_seed(path)
                person = found.id if found else _make_kin(world, npc, slot, path, _home(world, origin, slot))
                world.relate(npc_id, person, "kin_of", data={"role": slot["role"]})
                world.relate(person, npc_id, "kin_of", data={"role": INVERSE[slot["role"]]})
        world.update_data(npc_id, kin_ready=True)
    return kin_of(world, npc_id)


@effect("died")
def _died(world, event) -> None:
    _killer, victim = event.actors
    world.update_data(victim, dead=True, died_at=world.time)
    world.unrelate(victim, "located_in")
    if event.place is not None:
        world.relate(victim, event.place, "buried_at")


@listen("died")
def _inherit(world, event, event_id: int) -> None:
    killer, victim = event.actors
    # the living world's deaths grieve only the family already in the world; conjuring
    # new relatives at every natural death made the population explode (phase 4a review)
    family = kin_of(world, victim) if event.data.get("world") else ensure_kin(world, victim, origin=event.place)
    for relative, _role in family:
        if relative == killer:
            continue
        for memory in world.memories(victim):
            if memory.indelible:
                world.add_memory(relative, memory.event.id, memory.feeling, memory.intensity, True,
                                 inherited_from=victim, ignore_existing=True)
        world.add_memory(relative, event_id, "grief", 1.0, True, ignore_existing=True)


@on_fact
def _kin_hear(world, fact) -> None:
    """Channel 3: kin hear of what was done to or by their family, wherever they are."""
    if fact.predicate == "killed" and fact.object is not None:
        ensure_kin(world, fact.object, origin=fact.place)
    for someone in (fact.subject, fact.object):
        entity = world.entity(someone) if someone is not None else None
        if entity is None or entity.kind != "person":
            continue
        for relative, _role in kin_of(world, someone):
            if relative in (fact.subject, fact.object):
                continue
            believe(world, relative, fact.id, fact.variant, someone, CONF_DECAY, 1, "kin")


def avengers_for(world, player_id: int) -> list[int]:
    """Living people grieving a killing they know the player did, and not resting from the hunt."""
    now, found = world.time, []
    for memory in world.memories_with_feeling("grief"):
        if memory.event.kind != "died" or memory.event.actors[0] != player_id or memory.owner in found:
            continue
        person = world.entity(memory.owner)
        if person is None or person.kind != "person" or person.data.get("dead"):
            continue
        if float(person.data.get("age", 30)) < 12:
            continue  # a child grieves but does not hunt (phase 4a review)
        if person.data.get("pursuit_paused_until", -1) > now:
            continue
        if appears_as(world, memory.owner, memory.event, player_id) != player_id:
            continue  # they grieve, but do not know it was you
        found.append(memory.owner)
    return found


def grief_role(world, avenger: int, player_id: int) -> str | None:
    """Who the player killed, as this avenger would say it: 'my brother' -> 'sibling'."""
    for memory in world.memories(avenger, about=player_id):
        if memory.feeling == "grief" and memory.event.kind == "died":
            for kin, _, data in world.relations_from(avenger, "kin_of"):
                if kin == memory.event.actors[1]:
                    return data.get("role")
    return None


@listen("duel_ended")
def _avenger_spared(world, event, event_id: int) -> None:
    d = event.data
    if d.get("result") == "won" and d.get("verdict") == "spare":
        opponent = event.actors[1]
        if opponent in avengers_for(world, event.actors[0]):
            world.update_data(opponent, pursuit_paused_until=world.time + PAUSE_WATCHES)
