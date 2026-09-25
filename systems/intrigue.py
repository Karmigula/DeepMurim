"""Dark interventions (phase 4e spec 5.4): at most one per tournament, seeded at the draw.

- A demonic raid breaks up the final: it is fought again the next day, or is void if a finalist
  falls. A player at the venue may join the defence.
- A fixed match: one entrant is poisoned or bribed and fights at 0.6 of their strength in one bout.
  The fix is a fact nobody holds until it comes out: the bookmaker lets it slip, the player watches
  the bout, or a rumour gets out. Whoever knows may expose it, and is known for it.
- A vanished favourite disappears the night before their round and forfeits. Where they went is
  left open (spec §9).
"""

import dataclasses

import systems.tournaments as T
import systems.world_events as W
from systems.beliefs import CONF_DECAY, believe
from systems.facts import ON_FACT, make_variant, place_name, record_fact
from systems import factions as F
from systems.founding import make_person
from systems.membership import set_membership
from systems.reputation import reputation
from world.events import Event, effect, listen
from world.seed import rng_for

CHANCES = {"grand_assembly": (("raid", 0.10), ("fixed", 0.15), ("vanished", 0.05)),
           "dragon_phoenix": (("raid", 0.05), ("fixed", 0.10), ("vanished", 0.05)),
           "sect_contest": (("fixed", 0.05),)}
FIX_FACTOR = 0.6
RAID_DEATH = 0.15  # each NPC finalist's chance to fall to the cultists
RUMOUR_CHANCE = 0.25  # a fix gets out by itself once its bout is fought
ASK_BASE, ASK_PER_RENOWN, ASK_MAX = 0.2, 0.05, 0.8
CULTIST_REALM = {"grand_assembly": "first-rate", "dragon_phoenix": "second-rate"}


def _is_player(world, person) -> bool:
    return person is not None and bool(world.entity(person).data.get("is_player"))


# --- the plot ---------------------------------------------------------------------------------------

def plot(world, occurrence, rounds: list, ordered: list[int]) -> dict | None:
    """The one dark intervention this draw carries, if any: seeded by the occurrence."""
    rng = rng_for(world.world_seed, f"intrigue:{occurrence.id}")
    roll, total, kind = rng.random(), 0.0, None
    for name, chance in CHANCES.get(occurrence.data["data"]["kind"], ()):
        total += chance
        if roll < total:
            kind = name
            break
    if kind == "raid":
        return {"kind": "raid", "done": False, "day": None, "cultist": None, "defenders": []}
    if kind == "fixed":
        fair = [i for i, m in enumerate(rounds[0]) if None not in (m["a"], m["b"])
                and not _is_player(world, m["a"]) and not _is_player(world, m["b"])]
        if fair:
            i = rng.choice(fair)
            m = rounds[0][i]
            return {"kind": "fixed", "round": 0, "match": i, "victim": m["a"], "against": m["b"],  # a: the higher seed
                    "how": rng.choice(("poisoned", "bribed")), "fact": None, "exposed": False}
    if kind == "vanished" and len(rounds) > 1:
        favourites = [p for p in ordered if not _is_player(world, p)]
        if favourites:
            return {"kind": "vanished", "victim": favourites[0], "round": rng.randint(1, len(rounds) - 1),
                    "done": False}
    return None


def weakened(occurrence, r: int, i: int):
    """The fighter the fix weakens in this match, or None."""
    p = occurrence.data["data"].get("intrigue") or {}
    return p["victim"] if p.get("kind") == "fixed" and (p["round"], p["match"]) == (r, i) else None


def weaken(fighter):
    return dataclasses.replace(fighter, realm_mult=fighter.realm_mult * FIX_FACTOR)


def due_events(world, occurrence, now_day: int, over: bool) -> list[Event]:
    """A raid on the final's day, or a disappearance the night before the favourite's round."""
    t = occurrence.data["data"]
    p = t.get("intrigue")
    if not p or p["kind"] == "fixed" or p["done"]:
        return []
    if p["kind"] == "raid":
        final = t["rounds"][-1][0]
        if final["how"] is None and None not in (final["a"], final["b"]) and (over or now_day >= final["day"]):
            return raid_events(world, occurrence, max(now_day, final["day"]))
        return []
    for i, m in enumerate(t["rounds"][p["round"]]):
        if m["how"] is None and p["victim"] in (m["a"], m["b"]) and None not in (m["a"], m["b"]) \
                and (over or now_day >= m["day"] - 1) and T.alive(world, p["victim"]):
            return [Event("vanished", (p["victim"],), occurrence.data["place"],
                          {"occurrence": occurrence.id, "round": p["round"], "match": i})]
    return []


@effect("vanished")
def _vanished(world, event) -> None:
    person = event.actors[0]
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    world.update_data(person, vanished={"occurrence": occurrence.id, "time": world.time})
    world.unrelate(person, "located_in")  # gone from the town; where to is left open (spec §9)
    for faction, _, data in F.memberships(world, person):  # their sect counts them missing, and fills their post
        if data.get("status", "member") == "member":
            set_membership(world, person, faction, status="missing")
    world.update_data(occurrence.id, data={**t, "intrigue": {**t["intrigue"], "done": True}})


@listen("vanished")
def _vanished_news(world, event, event_id: int) -> None:
    person = event.actors[0]
    variant = make_variant("vanished", person, None, place=place_name(world, event.place))
    variant["kind"] = world.entity(event.data["occurrence"]).data["data"]["kind"]
    record_fact(world, person, "vanished", None, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


# --- the raid ---------------------------------------------------------------------------------------

def raid_events(world, occurrence, on: int) -> list[Event]:
    t = occurrence.data["data"]
    town, final = occurrence.data["place"], t["rounds"][-1][0]
    rng = rng_for(world.world_seed, f"intrigue:{occurrence.id}:raid")
    fallen = [p for p in (final["a"], final["b"]) if not _is_player(world, p) and rng.random() < RAID_DEATH]
    cultist = None
    if T.watched(world, occurrence):  # someone to fight only where the player can join the defence
        cultist = make_person(world, f"tournament:{occurrence.id}:cultist", town, occupation="demonic cultist",
                              age=rng.randint(25, 50), realm=CULTIST_REALM.get(t["kind"], "second-rate"))
    events = [Event("raided", (), town, {"occurrence": occurrence.id, "fallen": fallen, "cultist": cultist,
                                         "day": final["day"]})]
    events += [Event("died", (p, p), town, {"cause": "raid", "world": True}) for p in fallen]
    if fallen:  # a finalist fell: the final is void
        events.append(T.match_event(occurrence, len(t["rounds"]) - 1, 0, None, None, "void", on))
    return events


@effect("raided")
def _raided(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    rounds = [list(r) for r in t["rounds"]]
    extra = {}
    if not d["fallen"]:  # the final is fought again the next day
        rounds[-1][0] = dict(rounds[-1][0], day=d["day"] + 1)
        extra["until"] = max(occurrence.data["active"][1], T.day_start(occurrence, d["day"] + 2))
    world.update_data(occurrence.id, data={**t, **extra, "rounds": rounds,
                                           "intrigue": {**t["intrigue"], "done": True, "day": d["day"],
                                                        "cultist": d["cultist"]}})


@listen("raided")
def _raided_news(world, event, event_id: int) -> None:
    kind = world.entity(event.data["occurrence"]).data["data"]["kind"]
    variant = make_variant("raided", event.place, None, place=place_name(world, event.place))
    variant["kind"] = kind
    record_fact(world, event.place, "raided", None, place=event.place, source_event=event_id, weight=3.0,
                variant=variant)


def defence_open(world, occurrence_id: int, player: int) -> int | None:
    """The cultist to fight, if a raid is on at this venue today and the player has not fought yet."""
    occurrence = world.entity(occurrence_id)
    p = occurrence.data["data"].get("intrigue") or {}
    if p.get("kind") != "raid" or not p["done"] or p["cultist"] is None or player in p["defenders"]:
        return None
    if T.day(occurrence, world.time) != p["day"] or occurrence.data["place"] not in world.targets(player, "located_in"):
        return None
    return p["cultist"] if T.alive(world, p["cultist"]) else None


def defended_events(world, occurrence_id: int, player: int, cultist: int, won: bool) -> list[Event]:
    return [Event("defended", (player, cultist), world.entity(occurrence_id).data["place"],
                  {"occurrence": occurrence_id, "won": won})]


@effect("defended")
def _defended(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    p = t["intrigue"]
    world.update_data(occurrence.id, data={**t, "intrigue": {**p, "defenders": p["defenders"] + [event.actors[0]]}})


@listen("defended")
def _defended_news(world, event, event_id: int) -> None:
    if not event.data["won"]:
        return
    player = event.actors[0]
    variant = make_variant("defended", player, None, place=place_name(world, event.place))
    variant["kind"] = world.entity(event.data["occurrence"]).data["data"]["kind"]
    record_fact(world, player, "defended", None, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


# --- the fix ----------------------------------------------------------------------------------------

@listen("bracket_drawn")
def _secret(world, event, event_id: int) -> None:
    """The fix is a fact from the draw, but nobody holds it yet."""
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    p = t.get("intrigue")
    if not p or p["kind"] != "fixed":
        return
    variant = make_variant("fixed", p["victim"], p["against"], place=place_name(world, event.place))
    variant.update(how=p["how"], kind=t["kind"])
    fact = record_fact(world, p["victim"], "fixed", p["against"], place=event.place, variant=variant, weight=2.0,
                       spread=False, extra={"occurrence": occurrence.id})
    world.update_data(occurrence.id, data={**t, "intrigue": {**p, "fact": fact}})


def fix_of(world, occurrence_id: int) -> dict | None:
    p = world.entity(occurrence_id).data["data"].get("intrigue") or {}
    return p if p.get("kind") == "fixed" and p.get("fact") is not None else None


def knows(world, person: int, fact_id: int) -> bool:
    return any(b.knower == person for b in world.believers(fact_id))


def _tell(world, knower: int, fact_id: int, confidence: float, hops: int, channel: str) -> None:
    believe(world, knower, fact_id, world.fact(fact_id).variant, None, confidence, hops, channel)


def _publish(world, fact_id: int) -> None:
    """A secret gets out: from here it travels the way any deed does (3c channels)."""
    fact = world.fact(fact_id)
    for channel in ON_FACT:
        channel(world, fact)


@listen("watched")
def _saw_it(world, event, event_id: int) -> None:
    d = event.data
    p = fix_of(world, d["occurrence"])
    if p is not None and (p["round"], p["match"]) == (d["round"], d["match"]):
        _tell(world, event.actors[0], p["fact"], 1.0, 0, "witness")


@listen("match_resolved")
def _rumour(world, event, event_id: int) -> None:
    d = event.data
    if d["round"] != 0:
        return  # a fix is always a first-round bout
    p = fix_of(world, d["occurrence"])
    if p is None or p["exposed"] or p["match"] != d["match"]:
        return
    if rng_for(world.world_seed, f"intrigue:{d['occurrence']}:rumour").random() < RUMOUR_CHANCE:
        _publish(world, p["fact"])


def ask_block(world, occurrence_id: int, player: int) -> str | None:
    occurrence = world.entity(occurrence_id)
    if occurrence.data["place"] not in world.targets(player, "located_in"):
        return "The bookmaker is in the host town."
    if player in occurrence.data["data"].get("asked", []):
        return "The bookmaker has nothing more to tell you."
    return None


def ask_events(world, occurrence_id: int, player: int) -> list[Event]:
    """The bookmaker hears everything; how much they tell depends on who is asking (renown)."""
    occurrence = world.entity(occurrence_id)
    town = occurrence.data["place"]
    p = fix_of(world, occurrence_id)
    learned = False
    if p is not None and not p["exposed"]:
        chance = min(ASK_MAX, ASK_BASE + ASK_PER_RENOWN * reputation(world, town, player).renown)
        learned = rng_for(world.world_seed, f"intrigue:{occurrence_id}:ask:{player}").random() < chance
    return [Event("asked_bookmaker", (player,), town,
                  {"occurrence": occurrence_id, "learned": learned, "fact": p["fact"] if learned else None,
                   "victim": p["victim"] if learned else None})]


@effect("asked_bookmaker")
def _asked(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "asked": t.get("asked", []) + [event.actors[0]]})
    if event.data["learned"]:
        _tell(world, event.actors[0], event.data["fact"], CONF_DECAY, 1, "told")


def exposable(world, player: int) -> list[int]:
    """Tournaments whose fix the player knows of and nobody has exposed yet."""
    found = []
    for row in W.index(world):
        if row[W.TYPE] in T.KINDS:
            p = fix_of(world, row[W.ID])
            if p is not None and not p["exposed"] and knows(world, player, p["fact"]):
                found.append(row[W.ID])
    return found


def expose_events(world, occurrence_id: int, player: int, town: int) -> list[Event]:
    if occurrence_id not in exposable(world, player):
        return []
    p = fix_of(world, occurrence_id)
    return [Event("exposed", (player, p["victim"]), town,
                  {"occurrence": occurrence_id, "fact": p["fact"], "how": p["how"]})]


@effect("exposed")
def _exposed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "intrigue": {**t["intrigue"], "exposed": True}})


@listen("exposed")
def _exposed_news(world, event, event_id: int) -> None:
    player, victim = event.actors
    _publish(world, event.data["fact"])
    _tell(world, event.place, event.data["fact"], CONF_DECAY, 1, "gossip")  # told where the player stands
    variant = make_variant("exposed_fix", player, victim, place=place_name(world, event.place))
    record_fact(world, player, "exposed_fix", victim, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)
