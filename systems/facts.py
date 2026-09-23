"""Deeds become facts (phase 3a spec §4.1). Listeners on committed events write them.

A fact is ground truth. Its `variant` is the story as it looked to those present
(a masked deed names the persona). Fact hooks (ON_FACT) spread it as beliefs.
"""

from collections.abc import Callable

from systems.realms import realm_index
from world.db import Fact, World
from world.events import listen

WEIGHTS = {
    "killed": 3.0, "crippled": 2.0, "robbed": 1.0, "spared": 0.5, "fled_from": 0.5, "paid_off": 0.3,
    "is": 2.0, "lied_about": 1.5, "left_for_dead": 1.5, "owns_manual": 0.5, "defeated": 0.5,
}
FAMILY = {
    "killed": "harm", "crippled": "harm", "robbed": "harm", "left_for_dead": "harm", "defeated": "harm",
    "spared": "mercy", "fled_from": "flight", "paid_off": "flight", "is": "identity",
    "lied_about": "deceit", "owns_manual": "possession",
}
VERDICT_FACTS = {"kill": "killed", "cripple": "crippled", "rob": "robbed", "spare": "spared",
                 "leave_for_dead": "left_for_dead"}
FIGHT_MODES = ("duel", "encounter")
ON_FACT: list[Callable[[World, Fact], None]] = []


def on_fact(fn: Callable[[World, Fact], None]) -> Callable[[World, Fact], None]:
    """Register a channel that reacts to every new (spreading) fact."""
    ON_FACT.append(fn)
    return fn


def make_variant(predicate: str, actor: int | None, target: int | None, *, place: str | None = None,
                 realm: str | None = None, art: str | None = None, form: str | None = None,
                 masked: bool = False) -> dict:
    return {"predicate": predicate, "actor": actor, "target": target, "count": 1, "place": place,
            "realm": realm, "art": art, "form": form, "masked": masked, "soft": False}


def record_fact(world: World, subject: int, predicate: str, obj: int | None, *, place: int | None, variant: dict,
                source_event: int | None = None, weight: float | None = None, is_true: bool = True,
                extra: dict | None = None, spread: bool = True) -> int:
    weight = WEIGHTS.get(predicate, 1.0) if weight is None else weight
    fact_id = world.add_fact(subject, predicate, obj, place=place, weight=weight, is_true=is_true,
                             data={"variant": variant, **(extra or {})}, source_event=source_event)
    if spread:
        fact = world.fact(fact_id)
        for channel in ON_FACT:
            channel(world, fact)
    return fact_id


def apparent(event, person_id: int) -> int:
    """The id a deed is credited to: the persona while the player (actors[0]) wears a mask."""
    persona = event.data.get("as")
    return persona if persona and event.actors and person_id == event.actors[0] else person_id


def place_name(world: World, place_id: int | None) -> str | None:
    entity = world.entity(place_id) if place_id else None
    return entity.name if entity else None


def _arts(world: World, data: dict) -> dict:
    """side -> (art name, form) as the fight began."""
    started = world.chronicle_entry(data.get("duel"))
    out = {"player": (None, None), "opponent": (None, None)}
    if started is None or started.kind != "duel_started":
        return out
    for side, key in (("player", "technique"), ("opponent", "opponent_technique")):
        technique = world.entity(started.data.get(key)) if started.data.get(key) else None
        if technique is not None:
            out[side] = (technique.name, technique.data.get("form"))
    return out


@listen("duel_ended")
def _fight_facts(world: World, event, event_id: int) -> None:
    d = event.data
    if d.get("mode") not in FIGHT_MODES:
        return
    player, opponent = event.actors
    beast = bool(world.entity(opponent).data.get("beast"))
    me = apparent(event, player)
    where = place_name(world, event.place)
    result = d.get("result")
    if result == "fled":
        record_fact(world, me, "fled_from", opponent, place=event.place, source_event=event_id,
                    variant=make_variant("fled_from", me, opponent, place=where, masked=me != player))
        return
    if result == "won":
        winner, loser, true_winner, true_loser, side = me, opponent, player, opponent, "player"
    elif result == "lost" and not beast:
        winner, loser, true_winner, true_loser, side = opponent, me, opponent, player, "opponent"
    else:
        return
    loser_realm = world.entity(true_loser).data.get("realm", "mortal")
    gap = max(0, realm_index(loser_realm) - realm_index(world.entity(true_winner).data.get("realm", "mortal")))
    art, form = _arts(world, d)[side]
    masked = winner == me and me != player
    story = dict(place=where, realm=loser_realm, art=art, form=form, masked=masked)
    if not beast:
        record_fact(world, winner, "defeated", loser, place=event.place, source_event=event_id,
                    weight=0.5 + 0.75 * gap, variant=make_variant("defeated", winner, loser, **story))
    predicate = VERDICT_FACTS.get(d.get("verdict"))
    if predicate and (not beast or predicate == "killed"):
        record_fact(world, winner, predicate, loser, place=event.place, source_event=event_id,
                    weight=0.5 if beast else None, variant=make_variant(predicate, winner, loser, **story))
    if result == "won":
        for item in d.get("loot") or []:
            manual = world.entity(item)
            if manual is not None:
                record_fact(world, me, "owns_manual", None, place=event.place, source_event=event_id,
                            variant=make_variant("owns_manual", me, None, place=where, art=manual.name,
                                                 masked=me != player))


@listen("encounter_resolved")
def _paid_off(world: World, event, event_id: int) -> None:
    if event.data.get("how") != "paid":
        return
    player, bandit = event.actors
    me = apparent(event, player)
    record_fact(world, me, "paid_off", bandit, place=event.place, source_event=event_id,
                variant=make_variant("paid_off", me, bandit, place=place_name(world, event.place), masked=me != player))


# Channels register themselves on import (like narrate/outcomes.py). Later tasks add theirs here.
import systems.rumours  # noqa: E402,F401
