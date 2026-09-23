"""How news travels (phase 3a spec §5): witnesses, town gossip, kin, distance and telling."""

from systems.beliefs import CONF_DECAY, believe
from systems.facts import on_fact


@on_fact
def _witnesses(world, fact) -> None:
    """Channel 1: everyone who took part in or saw the deed knows it first-hand."""
    if fact.source_event is None:
        return
    entry = world.chronicle_entry(fact.source_event)
    people = set(world.witnesses_of(fact.source_event)) | set(entry.actors if entry else ())
    for person_id in sorted(people):
        person = world.entity(person_id)
        if person is None or person.kind != "person" or person.data.get("dead") or person.data.get("beast"):
            continue
        believe(world, person_id, fact.id, fact.variant, None, 1.0, 0, "witness")


@on_fact
def _town_gossip(world, fact) -> None:
    """Channel 2: the town where it happened talks about it at once."""
    town = world.entity(fact.place) if fact.place else None
    if town is None or town.kind != "town":
        return
    believe(world, town.id, fact.id, fact.variant, None, CONF_DECAY, 1, "gossip")
