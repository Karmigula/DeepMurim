"""What the player is told about followers and founding."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import cap, outcome, summary

EXTRA_PHRASES["founded"] = "{actor} founded the {target}."


@outcome("sworn", body_facts=False)
def _sworn(world, event):
    name = cap(world.entity(event.actors[1]).name)
    if event.data["accepted"]:
        return [f"{name} swears to follow you."], {}
    return [f"{name} is not ready to follow you."], {}


@outcome("sect_founded", body_facts=False)
def _founded(world, event):
    sect = world.entity(event.actors[0]).data["sect"]
    return [f"The charter is sealed: the {world.entity(sect).name} is founded.",
            "Your followers bow to you as their leader."], {}


@summary("sworn")
def _sworn_line(world, entry, names, place, other):
    return f"{cap(other)} swore to follow you." if entry.data["accepted"] else f"{cap(other)} declined to follow you."


@summary("sect_founded")
def _founded_line(world, entry, names, place, other):
    return f"Founded a sect in {place}."
