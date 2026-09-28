"""The chambers of a secret realm (phase 4f spec 3.2-3.3): guardians, trials, the inheritance, and what the dead leave.

Guardians, reflections and the master's shade are realm spirits: `person` entities that live inside
(`realm_spirit`, `delve_at`), are not on the life clock, and are fought through the ordinary duel.
"""

import systems.delve as D
import systems.realm_gates as G
from systems.bodies import load_body, save_body
from systems.duel import best_art
from systems.facts import make_variant, record_fact
from systems.realms import REALMS, add_energy
from systems.techniques import set_mastery, teach
from systems.time import advance
from systems.tournaments import realm_of
from world.body import add_injury, max_qi
from world.events import Event, commit, effect, listen
from world.seed import rng_for

SLIP_BASE, SLIP_PER_AGILITY, SLIP_PER_REALM, SLIP_BOUNDS = 0.3, 0.03, 0.1, (0.05, 0.8)
FORMATION_BASE, FORMATION_PER_COMPREHENSION, FORMATION_BOUNDS = 0.2, 0.04, (0.1, 0.9)
PRESSURE_QI = 0.4
MIRROR_MASTERY = 0.05
RESTOCK_CHANCE = 0.3


def _clamp(value: float, bounds) -> float:
    return min(bounds[1], max(bounds[0], value))


def _spirit(world, path: str, home: int, floor: int, c: int, name: str, **data) -> int:
    """A realm spirit at this chamber of the realm `home`: made once per path, refreshed when met again.
    (`data["realm"]` is its cultivation realm, as for anyone.)"""
    found = world.entity_by_seed(path)
    if found is not None:
        world.update_data(found.id, delve_at=[floor, c], **data)
        return found.id
    spirit = world.add_entity("person", name, {"realm_spirit": True, "beast": False, "delve_at": [floor, c],
                                               "arts_ready": True,  # their arts are given, never seeded (a mirror is you)
                                               "traits": ["hot-tempered"], "silver": 0, "age": 300, **data}, path)
    world.relate(spirit, home, "located_in")
    return spirit


def guardian(world, realm: int, floor: int, c: int) -> int:
    room = world.entity(realm).data["floors"][floor - 1][c]
    if room["contents"].get("guardian"):
        return room["contents"]["guardian"]
    openings = len(world.entity(realm).data["history"])
    spirit = _spirit(world, f"realm:{realm}:guardian:{floor}:{c}:{openings}", realm, floor, c,
                     f"a {room['contents']['species']}", beast=True, occupation=room["contents"]["species"],
                     realm=REALMS[room["contents"]["realm"]].label)
    D.set_chamber(world, realm, floor, c, contents={**room["contents"], "guardian": spirit})
    return spirit


def mirror(world, realm: int, floor: int, c: int, player: int) -> int:
    """Your reflection: your own body and your best art."""
    spirit = _spirit(world, f"realm:{realm}:mirror:{floor}:{c}", realm, floor, c, "your reflection",
                     occupation="reflection", realm=REALMS[realm_of(world, player)].label)
    save_body(world, spirit, load_body(world, player))
    art = best_art(world, player)
    if art is not None and all(t != art.technique.id for t, _, _ in world.relations_from(spirit, "knows")):
        teach(world, spirit, art.technique.id, completeness=art.completeness, mastery=art.mastery)
    return spirit


def shade(world, realm: int, player: int) -> int:
    """The master's remnant: their art, one realm above whoever kneels (spec §3.2)."""
    floors = world.entity(realm).data["floors"]
    master = world.entity(realm).data["master"]
    spirit = _spirit(world, f"realm:{realm}:shade", realm, len(floors), len(floors[-1]) - 1,
                     f"the remnant of {master['name']}", occupation="remnant soul",
                     realm=REALMS[G.shade_realm(world, player)].label)
    if all(t != master["art"] for t, _, _ in world.relations_from(spirit, "knows")):
        teach(world, spirit, master["art"], completeness=1.0, mastery=0.9)
    return spirit


# --- guardians -------------------------------------------------------------------------------------

def slip_events(world, player: int) -> list[Event]:
    realm, floor, c, room = D.here(world, player)
    agility = load_body(world, player).physique["agility"]
    gap = room["contents"]["realm"] - realm_of(world, player)
    chance = _clamp(SLIP_BASE + SLIP_PER_AGILITY * (agility - 10) - SLIP_PER_REALM * gap, SLIP_BOUNDS)
    passed = rng_for(world.world_seed, f"slip:{realm.id}:{floor}:{c}:{player}:{world.time}").random() < chance
    return [Event("guardian_slipped", (player,), realm.id, {"realm": realm.id, "floor": floor, "chamber": c,
                                                            "passed": passed})]


@effect("guardian_slipped")
def _slipped(world, event) -> None:
    d = event.data
    if d["passed"]:
        D.set_chamber(world, d["realm"], d["floor"], d["chamber"], state="passed")
    advance(world, D.STEP)


def slain_events(world, player: int, purpose: dict) -> list[Event]:
    realm, floor, c = purpose["guardian"]
    return [Event("guardian_slain", (player, world.entity(realm).data["floors"][floor - 1][c]["contents"]["guardian"]),
                  realm, {"realm": realm, "floor": floor, "chamber": c})]


@effect("guardian_slain")
def _slain(world, event) -> None:
    d = event.data
    D.set_chamber(world, d["realm"], d["floor"], d["chamber"], state="slain")


# --- trials ------------------------------------------------------------------------------------------

def trial_open(world, player: int) -> bool:
    realm, floor, c, room = D.here(world, player)
    return room["kind"] == "trial" and room["state"] == "untouched" and player not in room["contents"].get("tried", [])


def trial_events(world, player: int) -> list[Event]:
    """Formation and pressure settle at once; the mirror is a spar (the engine starts it)."""
    realm, floor, c, room = D.here(world, player)
    trial = room["contents"]["trial"]
    body = load_body(world, player)
    data = {"realm": realm.id, "floor": floor, "chamber": c, "trial": trial}
    if trial == "formation":
        from systems.formations import trial_bonus  # phase 5d: a formation master reads an ancient array better
        chance = _clamp(FORMATION_BASE + FORMATION_PER_COMPREHENSION * body.physique["comprehension"]
                        + trial_bonus(world, player), FORMATION_BOUNDS)
        passed = rng_for(world.world_seed, f"formation:{realm.id}:{floor}:{c}:{player}:{world.time}").random() < chance
        data.update(passed=passed, insight=round(0.5 + 0.2 * floor, 2) if passed else 0.0)
    elif trial == "pressure":
        passed = body.qi >= PRESSURE_QI * max_qi(body) and realm_of(world, player) >= floor - 1
        data.update(passed=passed, years=round(0.2 * floor, 2) if passed else 0.0)
    else:
        return []
    return [Event("trial_attempted", (player,), realm.id, data)]


@effect("trial_attempted")
def _attempted(world, event) -> None:
    player, d = event.actors[0], event.data
    room = world.entity(d["realm"]).data["floors"][d["floor"] - 1][d["chamber"]]
    contents = {**room["contents"], "tried": room["contents"].get("tried", []) + [player]}
    D.set_chamber(world, d["realm"], d["floor"], d["chamber"], contents=contents,
                  **({"state": "passed"} if d["passed"] else {}))
    body = load_body(world, player)
    if d["trial"] == "formation":
        if d["passed"]:
            body.insight += d["insight"]
        else:
            body.qi = body.qi / 2
            add_injury(body, "torso", "internal", 1, world.time, "an ancient array's backlash")
    elif d["trial"] == "pressure":
        if d["passed"]:
            add_energy(body, d["years"])
        else:
            body.qi = body.qi * 0.75
    save_body(world, player, body)
    advance(world, D.STEP)


def mirror_events(world, player: int, purpose: dict, passed: bool) -> list[Event]:
    realm, floor, c = purpose["mirror"]
    art = best_art(world, player)
    return [Event("trial_attempted", (player,), realm,
                  {"realm": realm, "floor": floor, "chamber": c, "trial": "mirror", "passed": passed,
                   "art": art.technique.id if art and passed else None})]


@listen("trial_attempted")
def _sharpened(world, event, event_id: int) -> None:
    d = event.data
    if d["trial"] == "mirror" and d.get("art") is not None:
        mastery = next(v for t, v, _ in world.relations_from(event.actors[0], "knows") if t == d["art"])
        set_mastery(world, event.actors[0], d["art"], min(1.0, mastery + MIRROR_MASTERY))


# --- the inheritance ------------------------------------------------------------------------------------

def inheritance_open(world, player: int) -> bool:
    realm, floor, c, room = D.here(world, player)
    return room["kind"] == "inheritance" and realm.data["inheritance_claimed_by"] is None \
        and player not in room["contents"].get("failed", [])


def shade_events(world, player: int, purpose: dict, passed: bool) -> list[Event]:
    realm = purpose["inheritance"]
    return [Event("inheritance_claimed" if passed else "inheritance_failed", (player,), realm, {"realm": realm})]


def _master_person(world, realm: int) -> int:
    """The dead master, as a person the lineage can name: dead long ago, buried in their realm."""
    master = world.entity(realm).data["master"]
    path = f"realm:{realm}:master"
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    person = world.add_entity("person", master["name"], {"dead": True, "age": 300, "realm": "profound",
                                                          "death": {"cause": "age", "age": 300, "place": realm},
                                                          "occupation": "ancient master"}, path)
    world.relate(person, realm, "buried_at")
    return person


@effect("inheritance_claimed")
def _claimed(world, event) -> None:
    from systems.agendas import _pair
    player, realm = event.actors[0], event.data["realm"]
    G.inherit(world, player, realm)
    floors = world.entity(realm).data["floors"]
    D.set_chamber(world, realm, len(floors), len(floors[-1]) - 1, state="passed")
    _pair(world, _master_person(world, realm), player, "disciple")  # their last disciple (spec §3.2)


@listen("inheritance_claimed")
def _claimed_news(world, event, event_id: int) -> None:
    player, realm = event.actors[0], world.entity(event.data["realm"])
    variant = make_variant("inherited", player, None, place=realm.name)
    variant.update(realm_name=realm.name, realm_id=realm.id, master=realm.data["master"]["name"])
    record_fact(world, player, "inherited", None, place=realm.id, source_event=event_id, weight=3.0, variant=variant)


@effect("inheritance_failed")
def _failed(world, event) -> None:
    player, realm = event.actors[0], event.data["realm"]
    floors = world.entity(realm).data["floors"]
    room = floors[-1][-1]
    D.set_chamber(world, realm, len(floors), len(floors[-1]) - 1,
                  contents={**room["contents"], "failed": room["contents"].get("failed", []) + [player]})
    world.update_data(player, delve={"realm": realm, "floor": len(floors), "chamber": 0})  # thrown back


# --- the dead, and what they carried -------------------------------------------------------------------------

@listen("died")
def _fell_inside(world, event, event_id: int) -> None:
    """Whoever dies in a realm leaves what they carried where they fell (spec §3.3)."""
    victim = event.actors[-1]
    person = world.entity(victim)
    where = person.data.get("delve") or ({"realm": None, "floor": person.data["delve_at"][0],
                                          "chamber": person.data["delve_at"][1]} if person.data.get("delve_at") else None)
    realms = world.get_meta("secret_realms") or []
    realm = (where or {}).get("realm") or (event.place if event.place in realms else None)
    if where is None or realm is None:
        return
    items = [i for i in world.targets(victim, "owns") if world.entity(i).kind in ("treasure", "manual")]
    if items:
        commit(world, [Event("remains_left", (victim,), realm, {"realm": realm, "floor": where["floor"],
                                                               "chamber": where["chamber"], "items": items})])
    world.update_data(victim, delve=None, delve_at=None)


@effect("remains_left")
def _remains_left(world, event) -> None:
    d = event.data
    room = world.entity(d["realm"]).data["floors"][d["floor"] - 1][d["chamber"]]
    for item in d["items"]:
        world.unrelate(event.actors[0], "owns", item)
        world.relate(d["realm"], item, "owns")
    D.set_chamber(world, d["realm"], d["floor"], d["chamber"],
                  contents={**room["contents"], "remains": room["contents"].get("remains", []) + d["items"]})


def remains_events(world, player: int, item: int) -> list[Event]:
    realm, floor, c, room = D.here(world, player)
    if item not in room["contents"].get("remains", []):
        return []
    return [Event("remains_taken", (player,), realm.id, {"realm": realm.id, "floor": floor, "chamber": c, "item": item})]


@effect("remains_taken")
def _remains_taken(world, event) -> None:
    d = event.data
    room = world.entity(d["realm"]).data["floors"][d["floor"] - 1][d["chamber"]]
    world.unrelate(d["realm"], "owns", d["item"])
    world.relate(event.actors[0], d["item"], "owns")
    D.set_chamber(world, d["realm"], d["floor"], d["chamber"],
                  contents={**room["contents"], "remains": [i for i in room["contents"]["remains"] if i != d["item"]]})


# --- each opening renews the chambers ------------------------------------------------------------------------

def renew_events(world, occurrence) -> list[Event]:
    """Slain guardians rise again, trials reset, and a looted treasure returns with chance 0.3 (spec §3.2)."""
    import systems.secret_realms as SR
    realm = world.entity(occurrence.data["data"]["realm"])
    rng = rng_for(world.world_seed, f"realm:{occurrence.id}:renew")
    floors = []
    for f, chambers in enumerate(realm.data["floors"], 1):
        renewed = []
        for room in chambers:
            if room["kind"] == "guardian" and room["state"] != "untouched":
                room = {**room, "state": "untouched", "contents": {**room["contents"], "guardian": None}}
            elif room["kind"] == "trial":
                room = {**room, "state": "untouched", "contents": {**room["contents"], "tried": []}}
            elif room["kind"] == "inheritance":
                room = {**room, "contents": {**room["contents"], "failed": []}}
            elif room["kind"] == "treasure" and room["state"] == "looted" and rng.random() < RESTOCK_CHANCE:
                room = {**room, "state": "untouched", "contents": {**room["contents"], "prize": SR.prize_at(rng, f)}}
            renewed.append(room)
        floors.append(renewed)
    return [Event("chambers_renewed", (), occurrence.data["place"], {"realm": realm.id, "floors": floors})]


@effect("chambers_renewed")
def _renewed(world, event) -> None:
    world.update_data(event.data["realm"], floors=event.data["floors"])
