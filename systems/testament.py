"""What the late master leaves (phase 4g spec 3.3, 4.2, 4.4, 4.5): a will, the leader's token, a last transmission,
and the Grand Elder in seclusion who may come down the mountain.

The will is a mark on the crisis (who it names, where it is), not an item (plan ruling 5). The token is a
lasting treasure of its faction, made the first time a leader dies: owned by someone, or lying in a place.
"""

import systems.claimants as C
from systems import factions as F
from systems.attitude import attitude
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.realms import REALMS, realm_index
from systems.tournaments import alive, realm_of
from world.events import Event, commit, effect, listen
from world.gen.materialize import region_of
from world.gen.names import person_name
from world.seed import rng_for

WILL_CHANCE = {"natural": 0.7, "other": 0.3}
WILL_STATES = (("read", 0.5), ("hidden", 0.3), ("held", 0.2))
NATURAL = frozenset({"age", "illness"})
TRANSMIT_CHANCE = 0.3
SEARCH_BASE, SEARCH_PER_REALM, CAMP_FIND = 0.35, 0.1, 0.2
EMERGE_CHANCE = 0.25
GRAND_VOTES = 3
TOKEN_PRICE = 5  # silver per point of the faction's power


# --- the leader's token (spec 4.5) ------------------------------------------------------------

def token_of(world, faction: int) -> int | None:
    found = world.entity_by_seed(f"world:{faction}:token")
    return found.id if found is not None else None


def ensure_token(world, faction: int) -> int:
    found = token_of(world, faction)
    if found is not None:
        return found
    name = world.entity(faction).name
    return world.add_entity("treasure", f"the leader's token of the {name}",
                            {"kind": "sect_token", "faction": faction, "used": False}, f"world:{faction}:token")


def holder(world, token: int) -> int | None:
    owners = world.sources(token, "owns")
    return owners[0] if owners else None


def lies_at(world, token: int) -> int | None:
    places = world.targets(token, "located_in")
    return places[0] if places else None


def put(world, token: int, owner: int | None = None, place: int | None = None) -> None:
    """The token changes hands or is set down: always in exactly one place."""
    for old in world.sources(token, "owns"):
        world.unrelate(old, "owns", token)
    world.unrelate(token, "located_in")
    if owner is not None:
        world.relate(owner, token, "owns")
    elif place is not None:
        world.relate(token, place, "located_in")


# --- the leader's death (spec 3.3, 4.5) -------------------------------------------------------

@listen("died")
def _last_breath(world, event, event_id: int) -> None:
    """The token stays where the leader fell; a natural death may pass the leader's strength to the heir."""
    killer, victim = event.actors[0], event.actors[-1]
    for token in world.targets(victim, "owns"):  # the dead hold nothing: a token lies where they fell
        entity = world.entity(token)
        if entity is not None and entity.kind == "treasure" and entity.data.get("kind") == "sect_token":
            seat = world.entity(entity.data["faction"]).data.get("seat")
            put(world, token, place=event.place if event.place is not None else seat)
    for fid, _, data in F.memberships(world, victim):
        faction = world.entity(fid)
        if data.get("role") != "leader" or faction.data.get("type") not in F.STAFFED or faction.data.get("dissolved"):
            continue
        token = ensure_token(world, fid)
        if holder(world, token) in (None, victim):
            seat = faction.data.get("seat")
            if killer != victim and alive(world, killer):
                put(world, token, owner=killer)
            else:
                put(world, token, place=event.place if event.place is not None else seat)
        heir = faction.data.get("heir")
        rng = rng_for(world.world_seed, f"transmit:{fid}:{victim}")
        if event.data.get("cause") in NATURAL and C.fit(world, heir, fid) \
                and world.targets(heir, "located_in") == [event.place] and rng.random() < TRANSMIT_CHANCE:
            commit(world, [Event("transmitted", (victim, heir), event.place, {"faction": fid})])


@effect("transmitted")
def _transmitted(world, event) -> None:
    leader, heir = event.actors
    top = min(len(REALMS) - 1, max(realm_of(world, heir) + 1, 0))
    top = min(top, max(realm_index(world.entity(leader).data.get("realm", "mortal")), realm_of(world, heir)))
    if world.entity(heir).data.get("is_player"):
        body = load_body(world, heir)
        if top > body.realm:
            body.realm, body.energy_years, body.bottleneck = top, REALMS[top].threshold, False
            save_body(world, heir, body)
    else:
        world.update_data(heir, realm=REALMS[top].label)
    world.update_data(event.data["faction"], transmitted=heir)


@listen("transmitted")
def _transmitted_news(world, event, event_id: int) -> None:
    leader, heir = event.actors
    variant = make_variant("transmitted", leader, heir, place=place_name(world, event.place))
    record_fact(world, leader, "transmitted", heir, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


@listen("succeeded")
def _takes_up_the_token(world, event, event_id: int) -> None:
    """A new leader picks up a token that lies at the seat, or that they hold; a transmission is spent."""
    d = event.data
    if d["role"] != "leader":
        return
    token = token_of(world, d["faction"])
    seat = world.entity(d["faction"]).data.get("seat")
    held = holder(world, token) if token is not None else None
    of_them = held is not None and held != event.actors[0] and C.role_in(world, held, d["faction"]) is not None
    if token is not None and ((held is None and lies_at(world, token) == seat) or of_them):
        put(world, token, owner=event.actors[0])  # a member hands it over to the new leader (spec 4.5, 4.9)
    world.update_data(d["faction"], transmitted=None)


# --- a crisis begins (spec 4.2, 4.4, 4.5) -----------------------------------------------------

def at_mourning(world, crisis: dict, rng, far: bool = False) -> dict:
    """The will read or not, the token picked up at the seat, the transmission counted, the Grand Elder's choice."""
    faction = crisis["faction"]
    data = world.entity(faction).data
    fallen = data.get("fallen") or {}
    claimants = crisis["claimants"]
    crisis = {**crisis, "transmitted": data.get("transmitted")}
    chance = WILL_CHANCE["natural" if fallen.get("cause") in NATURAL else "other"]
    if rng.random() < chance and claimants:
        chief = next((c["person"] for c in claimants if c["kind"] == "chief"), None)
        names = chief if chief is not None else _favourite(world, crisis["leader"], claimants)
        roll, state = rng.random(), "read"
        for option, share in WILL_STATES:
            if roll < share:
                state = option
                break
            roll -= share
        others = [c["person"] for c in claimants if c["person"] != names]
        if state == "held" and not others:
            state = "hidden"
        crisis["will"] = {"state": state, "names": names, "holder": others[0] if state == "held" else None}
    else:
        crisis["will"] = {"state": "none", "names": None, "holder": None}
    token = ensure_token(world, faction)
    if holder(world, token) is None and lies_at(world, token) is None:
        put(world, token, place=data.get("seat"))  # made now (no leader fell with it): it rests in the hall
    if holder(world, token) is None and lies_at(world, token) == data.get("seat") and claimants:
        chief = next((c["person"] for c in claimants if c["kind"] == "chief"), claimants[0]["person"])
        put(world, token, owner=chief)
    crisis["token"] = token
    return crisis if far else _grand_elder(world, crisis, rng)  # far away no Grand Elder is made (spec 2.4)


def _favourite(world, leader, claimants: list[dict]) -> int | None:
    if leader is None:
        return claimants[0]["person"]
    return max(claimants, key=lambda c: (attitude(world, leader, c["person"]).score, -c["person"]))["person"]


def _grand_elder(world, crisis: dict, rng) -> dict:
    faction = world.entity(crisis["faction"])
    if faction.data.get("tier") != "great" or rng.random() >= EMERGE_CHANCE:
        return crisis
    elder = ensure_grand_elder(world, faction.id, crisis["leader"])
    if C.ambitious(world, elder):
        claimants = list(crisis["claimants"])
        if len(claimants) >= C.MAX_CLAIMANTS:
            claimants = claimants[:-1]
        return {**crisis, "claimants": claimants + [{"person": elder, "kind": "grand_elder"}], "grand_elder": elder}
    best = max(crisis["claimants"], key=lambda c: (C.lean(world, crisis, elder, c, full=False), -c["person"]))
    return {**crisis, "grand_elder": elder, "grand_elder_backs": best["person"]}


def ensure_grand_elder(world, faction: int, leader: int | None) -> int:
    """The elder in closed-door seclusion on the sect's mountain: made once, seeded (spec 4.2)."""
    path = f"world:{faction}:grand_elder"
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    rng = rng_for(world.world_seed, path)
    surname, given = person_name(rng)
    base = realm_index(world.entity(leader).data.get("realm", "mortal")) if leader is not None else 3
    realm = REALMS[min(len(REALMS) - 1, base + 1)].label
    traits = [rng.choice(("proud", "cautious", "loyal", "secretive", "cunning", "kind"))]
    data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": rng.randint(90, 140),
            "occupation": "grand elder", "traits": traits, "realm": realm, "secluded": True,
            "portrait": {"hair": 3, "face": rng.randrange(4), "robe": rng.randrange(4)}}
    person = world.add_entity("person", f"{surname} {given}", data, path)
    seat = world.entity(faction).data["seat"]
    world.relate(person, region_of(world, seat).id, "located_in")  # the back mountain: in no town's scene
    world.relate(person, faction, "member_of", 4, {"role": "grand_elder", "hall": None, "merit": 0,
                                                   "status": "member", "secret": False})
    return person


# --- the hidden will (spec 4.4) ---------------------------------------------------------------

def search_chance(world, person: int) -> float:
    return SEARCH_BASE + SEARCH_PER_REALM * max(0, realm_of(world, person) - 1)


def camps_search(world, crisis: dict, rng) -> dict:
    """At a stage's change, each camp may turn up a hidden will: read if it names them, kept if not."""
    will = crisis.get("will") or {}
    if will.get("state") != "hidden":
        return crisis
    for c in crisis["claimants"]:
        if alive(world, c["person"]) and rng.random() < CAMP_FIND:
            return {**crisis, "will": found_by(will, c["person"])}
    return crisis


def found_by(will: dict, person: int) -> dict:
    if will.get("names") == person:
        return {**will, "state": "read", "holder": None}
    return {**will, "state": "held", "holder": person}
