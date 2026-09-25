"""The delve (phase 4f spec 3): the player's steps through a secret realm, chamber by chamber.

The player's place inside is `delve = {"realm", "floor", "chamber"}` (floors from 1, chambers from 0);
they are `located_in` the realm itself. A floor's chambers lie in a line ending at its stair (or,
on the last floor, the inheritance). A guardian or a band of rivals bars the way on until dealt
with; everything else may be left behind. One leaves only from the first floor.
"""

import systems.realm_gates as G
import systems.secret_realms as SR
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.time import advance
from world.body import max_qi
from world.events import Event, effect, listen
from world.seed import rng_for

STEP, STAIR, REST = 2, 1, 1  # watches
SNEAK_BASE, SNEAK_PER_AGILITY, SNEAK_BOUNDS = 0.2, 0.03, (0.05, 0.6)
BLOCKING = frozenset({"guardian", "rivals"})


# --- where the player is -------------------------------------------------------------------------

def position(world, person: int) -> dict | None:
    return world.entity(person).data.get("delve")


def here(world, person: int):
    """(realm entity, floor, chamber index, the chamber) for someone inside, or None."""
    pos = position(world, person)
    if not pos:
        return None
    realm = world.entity(pos["realm"])
    return realm, pos["floor"], pos["chamber"], realm.data["floors"][pos["floor"] - 1][pos["chamber"]]


def set_chamber(world, realm: int, floor: int, chamber: int, **changes) -> None:
    floors = [list(f) for f in world.entity(realm).data["floors"]]
    floors[floor - 1][chamber] = {**floors[floor - 1][chamber], **changes}
    world.update_data(realm, floors=floors)


def gate_open(world, realm: int) -> int | None:
    occurrence = SR.opening_of(world, realm)
    return occurrence if occurrence is not None and SR.stage_of(world, occurrence) == "active" else None


def days_left(world, occurrence: int) -> int:
    return max(0, (world.entity(occurrence).data["active"][1] - world.time + 3) // 4)


def realms_at(world, town: int) -> list[int]:
    """Realms whose gate stands open in this town now."""
    return [r for r in SR.realms(world) if world.entity(r).data["gate"] == town and gate_open(world, r)]


# --- entering and leaving ----------------------------------------------------------------------------

def entry(world, realm: int, player: int) -> tuple[str | None, str]:
    """(why the gate refuses, or None; and how the player would pass: rule, token, sponsor or sneak)."""
    from systems.tournaments import sponsor_of
    if gate_open(world, realm) is None:
        return "The gate is shut.", ""
    if world.entity(realm).data["gate"] not in world.targets(player, "located_in"):
        return "The gate is not here.", ""
    rule = world.entity(realm).data["rule"]["kind"]
    why = G.admits(world, realm, player)
    if why is None:
        return None, "token" if rule == "token" else "rule"
    if rule == "quota" and G.ceiling_of(world, realm) is None:
        if sponsor_of(world, player) is not None:
            return None, "sponsor"  # a sect that welcomes you lends you a place (4e sponsor)
        return why, "sneak"
    return why, ""


def enter_events(world, realm: int, player: int, how: str) -> list[Event]:
    return [Event("realm_entered", (player,), world.entity(realm).data["gate"],
                  {"realm": realm, "occurrence": gate_open(world, realm), "how": how})]


def sneak_events(world, realm: int, player: int) -> list[Event]:
    """Past the sects' guards: a chance from agility (spec §4.1); caught, the sects hear of it."""
    agility = load_body(world, player).physique["agility"]
    low, high = SNEAK_BOUNDS
    chance = min(high, max(low, SNEAK_BASE + SNEAK_PER_AGILITY * (agility - 10)))
    occurrence = gate_open(world, realm)
    if rng_for(world.world_seed, f"sneak:{occurrence}:{player}:{world.time}").random() < chance:
        return enter_events(world, realm, player, "sneak")
    return [Event("sneak_caught", (player,), world.entity(realm).data["gate"], {"realm": realm})]


@effect("realm_entered")
def _entered(world, event) -> None:
    player, d = event.actors[0], event.data
    if d["how"] == "token":
        token = G.tokens_of(world, player, d["realm"])[0]
        world.unrelate(player, "owns", token)
        world.update_data(token, used=True)
    world.unrelate(player, "located_in")
    world.relate(player, d["realm"], "located_in")
    world.update_data(player, delve={"realm": d["realm"], "floor": 1, "chamber": 0})
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "entered": t["entered"] + [player]})


@listen("sneak_caught")
def _caught(world, event, event_id: int) -> None:
    player = event.actors[0]
    variant = make_variant("trespassed", player, None, place=place_name(world, event.place))
    variant["realm_name"] = world.entity(event.data["realm"]).name
    record_fact(world, player, "trespassed", None, place=event.place, source_event=event_id, weight=1.0,
                variant=variant)


def leave_events(world, player: int) -> list[Event]:
    pos = position(world, player)
    if not pos or pos["floor"] != 1:
        return []
    realm = pos["realm"]
    return [Event("realm_left", (player,), world.entity(realm).data["gate"],
                  {"realm": realm, "occurrence": SR.opening_of(world, realm)})]


@effect("realm_left")
def _left(world, event) -> None:
    player = event.actors[0]
    world.unrelate(player, "located_in")
    world.relate(player, event.place, "located_in")
    world.update_data(player, delve=None)


@listen("realm_left")
def _came_out(world, event, event_id: int) -> None:
    player = event.actors[0]
    variant = make_variant("delved", player, None, place=place_name(world, event.place))
    variant["realm_name"] = world.entity(event.data["realm"]).name
    record_fact(world, player, "delved", None, place=event.place, source_event=event_id, weight=1.0, variant=variant)


# --- moving ------------------------------------------------------------------------------------------

def moves(world, player: int) -> dict[str, bool]:
    found = here(world, player)
    if found is None:
        return {}
    realm, floor, c, room = found
    floors = realm.data["floors"]
    last = c == len(floors[floor - 1]) - 1
    barred = room["kind"] in BLOCKING and room["state"] == "untouched"
    return {"on": not barred and (not last or (room["kind"] == "stair" and floor < len(floors))),
            "back": c > 0 or floor > 1,
            "leave": floor == 1}


def move_events(world, player: int, where: str) -> list[Event]:
    if not moves(world, player).get(where):
        return []
    realm, floor, c, room = here(world, player)
    floors = realm.data["floors"]
    if where == "on" and room["kind"] == "stair" and c == len(floors[floor - 1]) - 1:
        target, watches = (floor + 1, 0), STAIR
    elif where == "on":
        target, watches = (floor, c + 1), STEP
    elif c > 0:
        target, watches = (floor, c - 1), STEP
    else:
        target, watches = (floor - 1, len(floors[floor - 2]) - 1), STAIR  # back up the stair you came down
    return [Event("delve_moved", (player,), realm.id,
                  {"realm": realm.id, "floor": target[0], "chamber": target[1], "watches": watches})]


@effect("delve_moved")
def _moved(world, event) -> None:
    d = event.data
    world.update_data(event.actors[0], delve={"realm": d["realm"], "floor": d["floor"], "chamber": d["chamber"]})
    advance(world, d["watches"])


# --- treasure and rest ------------------------------------------------------------------------------

def take_events(world, player: int) -> list[Event]:
    found = here(world, player)
    if found is None:
        return []
    realm, floor, c, room = found
    if room["kind"] != "treasure" or room["state"] != "untouched":
        return []
    return [Event("chamber_looted", (player,), realm.id,
                  {"realm": realm.id, "floor": floor, "chamber": c, "prize": room["contents"]["prize"]})]


@effect("chamber_looted")
def _looted(world, event) -> None:
    from systems.races import make_prize
    d = event.data
    make_prize(world, event.actors[0], d["prize"], f"realm:{d['realm']}:{d['floor']}:{d['chamber']}:{world.time}")
    set_chamber(world, d["realm"], d["floor"], d["chamber"], state="looted")
    advance(world, STEP)


@listen("chamber_looted")
def _took(world, event, event_id: int) -> None:
    """Known to whoever was there; it leaves the realm only with a survivor (spec §5)."""
    player, d = event.actors[0], event.data
    variant = make_variant("took", player, None, place=world.entity(d["realm"]).name)
    variant.update(realm_name=world.entity(d["realm"]).name, prize=d["prize"]["kind"])
    record_fact(world, player, "took", None, place=d["realm"], source_event=event_id, weight=1.0, variant=variant)


TOKEN_PRICE = 3  # times a token's value: its holder gives up a place inside


def token_offer(world, holder: int, player: int) -> int | None:
    """A jade token this person holds and would part with (spec §4.1: tokens are bought, stolen or robbed)."""
    if holder == player:
        return None
    for item in world.targets(holder, "owns"):
        entity = world.entity(item)
        if entity is not None and entity.kind == "treasure" and entity.data.get("kind") == "token" \
                and not entity.data.get("used"):
            return item
    return None


def buy_events(world, player: int, holder: int) -> list[Event]:
    from systems.purse import silver_of
    token = token_offer(world, holder, player)
    if token is None:
        return []
    price = TOKEN_PRICE * world.entity(token).data["value"]
    if silver_of(world, player) < price:
        return []
    place = world.targets(player, "located_in")[0]
    return [Event("token_bought", (player, holder), place, {"token": token, "silver": price})]


@effect("token_bought")
def _bought(world, event) -> None:
    from systems.purse import silver_of
    player, holder = event.actors
    d = event.data
    world.unrelate(holder, "owns", d["token"])
    world.relate(player, d["token"], "owns")
    world.update_data(player, silver=silver_of(world, player) - d["silver"])
    world.update_data(holder, silver=silver_of(world, holder) + d["silver"])


def rest_events(world, player: int) -> list[Event]:
    pos = position(world, player)
    return [Event("delve_rested", (player,), pos["realm"], {})] if pos else []


@effect("delve_rested")
def _rested(world, event) -> None:
    body = load_body(world, event.actors[0])
    body.qi = min(max_qi(body), body.qi + 0.1 * max_qi(body))
    save_body(world, event.actors[0], body)
    advance(world, REST)
