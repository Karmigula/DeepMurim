"""Tribulation lightning (phase 4d spec 4.1): heaven's answer to a great breakthrough, seen across the region.

A breakthrough to First-rate or beyond, by anyone, calls it down. The townsfolk witness it,
a `tribulation` fact names who broke through (the Pavilion's informants listen for these),
and the player must come through it: clean, scarred, or with a meridian torn (played wave by wave since 5f).
"""

import systems.sky as sky
import systems.world_events as W
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.realms import REALMS
from world.body import REGULAR, add_injury
from world.events import Event, Witness, commit, effect, listen
from world.gen.materialize import people_at

TRIBULATION_REALM = 3  # First-rate
OUTCOMES = ("clean", "scarred", "crippled")
WITNESSES = 8


def trigger_events(world, person: int, place: int, realm: int, season: int | None = None,
                   outcome: str | None = None) -> list[Event]:
    """The lightning (if it is still to be seen) and the tribulation itself."""
    recent = season is None or season >= world.time // W.SEASON
    events = sky.start_events(world, "tribulation", place, world.time if recent else season * W.SEASON,
                              {"person": person, "realm": realm})
    witnesses = tuple(Witness(p.id, "respect", 0.4) for p in people_at(world, place, exclude=person)[:WITNESSES]) \
        if recent else ()
    return events + [Event("tribulation", (person,), place, {"realm": realm, "outcome": outcome}, witnesses=witnesses)]


@effect("tribulation")
def _tribulation(world, event) -> None:
    outcome = event.data.get("outcome")
    if outcome not in ("scarred", "crippled"):
        return
    pid = event.actors[0]
    body = load_body(world, pid)
    if outcome == "scarred":
        add_injury(body, "torso", "internal", 2, world.time, "the heavenly tribulation")
    else:
        opened = [m for m in REGULAR if body.meridians[m].state == "open"]
        if opened:
            body.meridians[opened[0]].state = "damaged"
            add_injury(body, opened[0], "meridian", 3, world.time, "the heavenly tribulation")
    save_body(world, pid, body)


@listen("tribulation")
def _news(world, event, event_id: int) -> None:
    person, realm = event.actors[0], event.data["realm"]
    variant = make_variant("tribulation", person, None, place=place_name(world, event.place), realm=REALMS[realm].label)
    variant["age"] = int(world.entity(person).data.get("age", 20))
    record_fact(world, person, "tribulation", None, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


@listen("broke_through")
def _npc_tribulation(world, event, event_id: int) -> None:
    realm = event.data["realm"]
    if realm >= TRIBULATION_REALM and event.place is not None:
        from systems.tribulations import npc_fate_events  # phase 5f: karma weighs the lightning
        commit(world, trigger_events(world, event.actors[0], event.place, realm, season=event.data.get("season"))
               + npc_fate_events(world, event.actors[0], event.place, event.data.get("season")))
