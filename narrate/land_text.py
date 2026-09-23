"""What the player is told about land."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import outcome, summary

EXTRA_PHRASES["seized"] = "{actor} seized the seat of the {target}."


@outcome("land_bought", body_facts=False)
def _bought(world, event):
    return [f"The deed is yours: land in {world.entity(event.place).name}, for {event.data['price']} silver."], {}


@outcome("land_claimed", body_facts=False)
def _claimed(world, event):
    return [f"You claim the old hall in {world.entity(event.place).name}."], {}


@outcome("seized", body_facts=False)
def _seized(world, event):
    return [f"The {world.entity(event.data['faction']).name} is broken; its seat is yours."], {}


@summary("land_bought")
def _bought_line(world, entry, names, place, other):
    return f"Bought land in {place}."


@summary("land_claimed")
def _claimed_line(world, entry, names, place, other):
    return f"Claimed the old hall in {place}."


@summary("seized")
def _seized_line(world, entry, names, place, other):
    return f"Seized the seat of the {world.entity(entry.data['faction']).name}."
