"""Telling people things, true or invented, and lies found out (phase 3a spec 7.3)."""

from systems.attitude import attitude
from systems.beliefs import CONF_DECAY, believe, knowledge_of
from systems.facts import FAMILY, apparent, make_variant, place_name, record_fact
from world.db import variant_key
from world.events import Event, Witness, listen
from world.gen.materialize import people_at
from world.seed import rng_for

INVENTABLE = ("killed", "robbed", "fled_from", "owns_manual")
NEEDS_OBJECT = frozenset({"killed", "robbed", "fled_from"})


def acceptance(world, listener_id: int, speaker_as: int, variant: dict) -> float:
    """How likely the listener is to believe this. Zero if they know otherwise first-hand."""
    if listener_id in (variant.get("actor"), variant.get("target")):
        return 0.0  # they know what happened to them
    family = FAMILY.get(variant.get("predicate"))
    for belief, fact in knowledge_of(world, listener_id):
        if belief.hops == 0 and fact.subject == variant.get("actor") and fact.object == variant.get("target") \
                and FAMILY.get(fact.predicate) != family:
            return 0.0
    traits = set(world.entity(listener_id).data.get("traits", ()))
    score = max(-1.0, min(1.0, attitude(world, listener_id, speaker_as).score))
    chance = 0.5 + 0.2 * score + (0.2 if "honest" in traits else 0.0) - (0.3 if "cunning" in traits else 0.0)
    return max(0.0, min(1.0, chance))


def tell_events(world, player: int, listener: int, place: int, variant: dict, fact_id: int | None = None,
                speaker_as: int | None = None) -> list[Event]:
    key = fact_id if fact_id is not None else variant_key(variant)
    rng = rng_for(world.world_seed, f"tell:{key}:{listener}:{world.time}")
    accepted = rng.random() < acceptance(world, listener, speaker_as or player, variant)
    witness = Witness(listener, "engaged", 0.1) if accepted else Witness(listener, "annoyed", 0.3)
    data = {"fact": fact_id, "variant": variant, "invented": fact_id is None, "accepted": accepted,
            "speaker": speaker_as or player}
    return [Event("told", (player, listener), place, data, witnesses=(witness,))]


@listen("told")
def _told(world, event, event_id: int) -> None:
    player, listener = event.actors
    d = event.data
    fact_id = d["fact"]
    if d["invented"]:
        story = d["variant"]
        fact_id = record_fact(world, story["actor"], story["predicate"], story.get("target"), place=event.place,
                              variant=story, source_event=event_id, is_true=False,
                              extra={"liar": player, "spread": d["accepted"]}, spread=False)
    if not d["accepted"]:
        return
    speaker = d.get("speaker", player)  # who they took the teller to be: a persona while masked
    believe(world, listener, fact_id, d["variant"], speaker, CONF_DECAY, 1, "told")
    town = world.entity(event.place) if event.place else None
    if town is not None and town.kind == "town":
        believe(world, town.id, fact_id, d["variant"], speaker, CONF_DECAY ** 2, 2, "told")


def exposure_events(world, player: int, town_id: int) -> list[Event]:
    """The player's lies that have reached, here, someone who knows the truth first-hand."""
    done = {f.data.get("lie") for f in world.facts(predicate="lied_about")}  # all of history, not recent pages
    here = {p.id for p in people_at(world, town_id, exclude=player)}
    pool = {b.fact_id for b in world.beliefs(town_id)}
    events = []
    for lie in world.facts(is_true=False):
        if lie.data.get("liar") != player or lie.id in done:
            continue
        victim = world.entity(lie.subject)
        if victim is None or victim.kind != "person" or victim.data.get("dead"):
            continue
        knowers = {lie.subject} & here
        for truth in world.facts(subject=lie.subject, is_true=True):
            if truth.object == lie.object and FAMILY.get(truth.predicate) != FAMILY.get(lie.predicate):
                knowers |= {b.knower for b in world.believers(truth.id) if b.hops == 0} & here
        if not knowers:
            continue
        heard = lie.id in pool or any(b.fact_id == lie.id for k in knowers for b in world.beliefs(k))
        if heard:
            told = world.chronicle_entry(lie.source_event)
            liar_as = told.data.get("as") if told is not None else None  # a lie told masked stays the mask's
            events.append(Event("lie_exposed", (player, lie.subject), town_id,
                                {"fact": lie.id, "predicate": lie.predicate, "as": liar_as},
                                witnesses=(Witness(lie.subject, "wronged", 0.9),)))
    return events


@listen("lie_exposed")
def _exposed(world, event, event_id: int) -> None:
    player, victim = event.actors
    liar = apparent(event, player)
    record_fact(world, liar, "lied_about", victim, place=event.place, source_event=event_id,
                extra={"lie": event.data["fact"]},
                variant=make_variant("lied_about", liar, victim, place=place_name(world, event.place),
                                     masked=liar != player))
