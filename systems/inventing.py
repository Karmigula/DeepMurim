"""Turning glimpsed fragments into an art of your own (phase 2 spec §10).

The route is stitched from the fragments' meridian segments through your own
unsevered meridians; the grade is capped by both realm and insight.
"""

from collections import Counter

from systems.bodies import load_body
from systems.techniques import FORMS, INTENTS, STANCES, create_technique, teach, technique_name
from systems.time import advance
from world.body import REGULAR
from world.events import Event, effect
from world.seed import rng_for

MIN_FRAGMENTS = 3
MIN_INSIGHT = 20.0
CREATE_DAYS = 7


def fragments_of(world, pid: int) -> list[dict]:
    return list(world.entity(pid).data.get("fragments", []))


def creatable_forms(world, pid: int) -> list[str]:
    return sorted({f["form"] for f in fragments_of(world, pid) if f["form"] in FORMS})


def why_not_create(world, pid: int) -> str | None:
    fragments = fragments_of(world, pid)
    if len(fragments) < MIN_FRAGMENTS:
        return f"You need at least {MIN_FRAGMENTS} fragments of other arts; you have {len(fragments)}."
    if load_body(world, pid).insight < MIN_INSIGHT:
        return "You need deeper martial insight before you can create an art."
    if not creatable_forms(world, pid):
        return "Your fragments do not suggest any form you could build on."
    return None


def create_events(world, pid: int, place: int, form: str) -> list[Event]:
    if why_not_create(world, pid) or form not in creatable_forms(world, pid):
        return []
    body = load_body(world, pid)
    fragments = fragments_of(world, pid)
    rng = rng_for(world.world_seed, f"invent:{pid}:{world.time}")
    chosen = ([f for f in fragments if f["form"] == form] + [f for f in fragments if f["form"] != form])[:MIN_FRAGMENTS]
    route: list[str] = []
    for fragment in chosen:
        for meridian in fragment["segment"]:
            if meridian not in route and body.meridians[meridian].state != "severed":
                route.append(meridian)
    spare = [m for m in REGULAR if body.meridians[m].state == "open" and m not in route]
    while len(route) < 2 and spare:
        route.append(spare.pop(rng.randrange(len(spare))))
    favours = rng.choice(INTENTS)
    data = {
        "category": "martial", "form": form, "stance": {"name": rng.choice(STANCES[favours]), "favours": favours},
        "route": route[:6], "element": Counter(f["element"] for f in chosen).most_common(1)[0][0],
        "grade": max(1, min(6, body.realm + 1, 1 + int(body.insight // 40))),
        "power": round(rng.uniform(0.8, 1.3), 2), "speed": round(rng.uniform(0.8, 1.3), 2),
        "defence": round(rng.uniform(0.8, 1.3), 2), "creator": pid, "origin": "created",
    }
    event = {"name": technique_name(rng, form), "technique_data": data, "used": chosen, "days": CREATE_DAYS}
    return [Event("created_technique", (pid,), place, event)]


@effect("created_technique")
def _created(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    advance(world, data["days"] * 4)
    technique = create_technique(world, data["name"], data["technique_data"])
    teach(world, pid, technique, source="created", mastery=0.1)
    remaining = fragments_of(world, pid)
    for used in data["used"]:
        if used in remaining:
            remaining.remove(used)
    world.update_data(pid, fragments=remaining)
