"""What people do with their seasons (phase 4a spec 4.3-4.4): marry, raise children, move, avenge, teach.

Each agenda is `(world, person, n, rng) -> list[Event]` and runs in the life clock's
full seasons only. When an agenda needs someone else, that person is first caught
up passively to the same season (spec §2.2).
"""

import systems.lives as lives
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.founding import make_person
from systems.kin import INVERSE, kin_of
from systems.realms import realm_index
from world.body import add_injury
from world.events import Event, Witness, effect, listen
from world.gen.materialize import people_at

MARRY_CHANCE, BIRTH_CHANCE, MOVE_CHANCE = 0.03, 0.08, 0.03
REVENGE_CHANCE, FEUD_DEATH, APPRENTICE_CHANCE = 0.1, 0.2, 0.05
POP_CAP = 1.5
REVENGE_REST = 4  # seasons before the same grudge is acted on again
GRUDGES = frozenset({"wronged", "hatred", "grief"})

INVERSE.setdefault("spouse", "spouse")


def _kin(world, person: int, role: str) -> list[int]:
    return [k for k, r in kin_of(world, person) if r == role]


def spouse_of(world, person: int) -> int | None:
    found = _kin(world, person, "spouse")
    return found[0] if found else None


def children_of(world, person: int) -> list[int]:
    return _kin(world, person, "child")


def parents_of(world, person: int) -> list[int]:
    return _kin(world, person, "parent")


def _age(entity) -> float:
    return float(entity.data.get("age", 30))


def _town(world, person: int) -> int | None:
    place = lives.home(world, person)
    entity = world.entity(place) if place is not None else None
    return place if entity is not None and entity.kind == "town" else None


def _staff(world, person: int) -> bool:
    return any(d.get("status", "member") == "member" and d.get("role") not in (None, "member")
               for _, _, d in F.memberships(world, person))


def population(world, town: int) -> int:
    """Living people of a town who are not faction staff (spec §4.3 cap)."""
    return len([p for p in people_at(world, town) if not p.data.get("is_player") and not _staff(world, p.id)])


def _ready(world, person: int, n: int) -> bool:
    """Catch someone up passively to season n; are they still alive to take part?"""
    lives.catch_up(world, person, until=n, passive=True)
    return lives.simulated(world.entity(person))


def marry_events(world, person: int, n: int, rng) -> list[Event]:
    entity = world.entity(person)
    if not 18 <= _age(entity) <= 50 or spouse_of(world, person) is not None or rng.random() >= MARRY_CHANCE:
        return []
    town = _town(world, person)
    if town is None:
        return []
    kin = {k for k, _ in kin_of(world, person)}
    candidates = sorted(p.id for p in people_at(world, town)
                        if p.id != person and p.id not in kin and lives.simulated(p) and 18 <= _age(p) <= 50
                        and spouse_of(world, p.id) is None)
    partner = next((c for c in candidates if _ready(world, c, n)), None)
    if partner is None:
        partner = make_person(world, f"life:{lives.key(entity)}:spouse:{n}", town, age=int(_age(entity)))
    return [Event("married", (person, partner), town, {"season": n})]


def birth_events(world, person: int, n: int, rng) -> list[Event]:
    spouse = spouse_of(world, person)
    if spouse is None or spouse < person:  # the lower id of a couple rolls for both
        return []
    if not _ready(world, spouse, n):
        return []  # the spouse lives up to this season first (spec §2.2)
    entity, other = world.entity(person), world.entity(spouse)
    if not any(18 <= _age(e) <= 45 for e in (entity, other)) or rng.random() >= BIRTH_CHANCE:
        return []
    town = _town(world, person)
    if town is None:
        return []
    count = population(world, town)
    if count >= POP_CAP * world.entity(town).data.get("npc_count", 10):
        return []
    surname = entity.data.get("surname")
    child = make_person(world, f"life:{lives.key(entity)}:child:{n}", town, age=0, occupation="child",
                        realm="mortal", kin_ready=True, **({"surname": surname} if surname else {}))
    return [Event("born", (person, spouse, child), town, {"season": n, "population": count})]


def move_events(world, person: int, n: int, rng) -> list[Event]:
    if rng.random() >= MOVE_CHANCE:
        return []
    entity = world.entity(person)
    town = _town(world, person)
    if town is None or _age(entity) < 16 or entity.data.get("sworn_to") or _staff(world, person) \
            or lives.in_player_sect(world, person):
        return []
    here = set(world.sources(town, "located_in"))
    if spouse_of(world, person) in here or any(c in here for c in children_of(world, person)):
        return []  # the married and the parents do not leave their family behind
    origin = world.entity(town).data
    options = sorted(t.id for t in world.entities("town")
                     if t.id != town and max(abs(t.data["x"] - origin["x"]), abs(t.data["y"] - origin["y"])) <= 1)
    if not options:
        return []
    return [Event("moved", (person,), town, {"to": rng.choice(options)})]


def grudge(world, person: int, n: int) -> tuple[int, int] | None:
    """(someone this person means to strike back at, the event they remember), or None."""
    if _age(world.entity(person)) < 12:
        return None  # children carry grudges but do not act on them
    rest = world.entity(person).data.get("revenge_rest", {})
    for memory in world.memories(person):
        if memory.feeling not in GRUDGES or not memory.event.actors:
            continue
        doer = memory.event.actors[0]
        if doer == person:
            continue
        if memory.feeling == "grief" and (memory.event.kind != "died" or memory.event.actors[-1] == doer):
            continue  # grief over a natural death blames no one
        target = world.entity(doer)
        if target is None or not lives.simulated(target) or _age(target) < 12:
            continue  # never the player, the dead, a beast or a child (spec §4.4)
        if n - rest.get(str(memory.event.id), -REVENGE_REST) < REVENGE_REST:
            continue
        return doer, memory.event.id
    return None


def revenge_events(world, person: int, n: int, rng) -> list[Event]:
    found = grudge(world, person, n)
    if found is None or rng.random() >= REVENGE_CHANCE:
        return []
    target, cause = found
    if not _ready(world, target, n):
        return []
    gap = realm_index(world.entity(person).data.get("realm", "mortal")) \
        - realm_index(world.entity(target).data.get("realm", "mortal"))
    won = rng.random() < max(0.1, min(0.9, 0.5 + 0.15 * gap))
    winner, loser = (person, target) if won else (target, person)
    killed = rng.random() < FEUD_DEATH
    place = _town(world, loser) or lives.home(world, loser)
    if place is None:
        return []
    feud = Event("feud", (person, target), place, {"won": won, "killed": killed, "cause": cause, "season": n},
                 witnesses=() if killed else (Witness(loser, "hatred", 0.8),))
    if killed:
        return [feud, Event("died", (winner, loser), place, {"cause": "feud", "world": True})]
    return [feud]


def apprentice_events(world, person: int, n: int, rng) -> list[Event]:
    entity = world.entity(person)
    if realm_index(entity.data.get("realm", "mortal")) < 2 or _kin(world, person, "disciple") \
            or rng.random() >= APPRENTICE_CHANCE:
        return []
    town = _town(world, person)
    if town is None:
        return []
    youths = sorted(p.id for p in people_at(world, town)
                    if p.id != person and lives.simulated(p) and 12 <= _age(p) <= 20 and not _kin(world, p.id, "master"))
    youth = next((y for y in youths if _ready(world, y, n)), None)
    return [] if youth is None else [Event("apprenticed", (person, youth), town, {"season": n})]


lives.AGENDAS.extend([marry_events, birth_events, move_events, revenge_events, apprentice_events])


def _pair(world, a: int, b: int, role_of_b: str) -> None:
    world.relate(a, b, "kin_of", data={"role": role_of_b})
    world.relate(b, a, "kin_of", data={"role": INVERSE[role_of_b]})


@effect("married")
def _married(world, event) -> None:
    a, b = event.actors
    _pair(world, a, b, "spouse")
    if world.entity(b).data.get("lived_to") is None:
        world.update_data(b, lived_to=event.data["season"])  # a newcomer starts living now (ruling 9)


@effect("born")
def _born(world, event) -> None:
    a, b, child = event.actors
    for parent in (a, b):
        for sibling in children_of(world, parent):
            if sibling != child:
                _pair(world, sibling, child, "sibling")
        _pair(world, parent, child, "child")
    world.update_data(child, lived_to=event.data["season"])


@effect("moved")
def _moved(world, event) -> None:
    person = event.actors[0]
    world.unrelate(person, "located_in")
    world.relate(person, event.data["to"], "located_in")


@effect("feud")
def _feud(world, event) -> None:
    person, target = event.actors
    d = event.data
    rest = dict(world.entity(person).data.get("revenge_rest", {}))
    rest[str(d["cause"])] = d["season"]
    world.update_data(person, revenge_rest=rest)
    if not d["killed"]:
        loser = target if d["won"] else person
        body = load_body(world, loser)
        add_injury(body, "torso", "cut", 2, min(world.time, d["season"] * lives.SEASON), "a feud")  # when it happened
        save_body(world, loser, body)


@effect("apprenticed")
def _apprenticed(world, event) -> None:
    master, youth = event.actors
    _pair(world, master, youth, "disciple")


def _news(world, event, event_id: int, subject: int, predicate: str, obj, weight: float, **extra) -> None:
    record_fact(world, subject, predicate, obj, place=event.place, source_event=event_id, weight=weight,
                variant=make_variant(predicate, subject, obj, place=place_name(world, event.place)),
                extra=extra or None)


@listen("married")
def _married_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "married", event.actors[1], 1.0)


@listen("born")
def _born_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "born", event.actors[2], 0.5, population=event.data["population"])


@listen("moved")
def _moved_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "moved", event.data["to"], 0.5)


@listen("feud")
def _feud_news(world, event, event_id: int) -> None:
    if event.data["killed"]:
        return  # the death writes `killed`
    person, target = event.actors
    winner, loser = (person, target) if event.data["won"] else (target, person)
    _news(world, event, event_id, winner, "defeated", loser, 0.5)


@listen("apprenticed")
def _apprenticed_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, event.actors[0], "apprenticed", event.actors[1], 0.5)
