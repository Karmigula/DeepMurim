"""What the player is told about rising in a faction."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import cap, outcome, summary
from systems import factions as F

EXTRA_PHRASES["promoted"] = "{actor} rose in the {target}."


def _name(world, data) -> str:
    return world.entity(data["faction"]).name


@outcome("promoted", body_facts=False)
def _promoted(world, event):
    d = event.data
    return [f"You are raised to {F.title(world, d['faction'], d['rank'])} of the {_name(world, d)}."], {}


@outcome("stipend", body_facts=False)
def _stipend(world, event):
    return [f"You collect {event.data['amount']} silver from the {_name(world, event.data)}."], {}


@outcome("sect_taught", body_facts=False)
def _taught(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} teaches you the {event.data['name']}."], {}


@outcome("library_lent", body_facts=False)
def _lent(world, event):
    return [f"You are lent a manual of the {event.data['name']}."], {}


@outcome("gift", body_facts=False)
def _gift(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} accepts your gift of {event.data['amount']} silver."], {}


@summary("promoted")
def _promoted_line(world, entry, names, place, other):
    return f"Raised to {F.title(world, entry.data['faction'], entry.data['rank'])} of the {_name(world, entry.data)}."


@summary("stipend")
def _stipend_line(world, entry, names, place, other):
    return f"Collected a stipend from the {_name(world, entry.data)}."


@summary("sect_taught")
def _taught_line(world, entry, names, place, other):
    return f"Learned the {entry.data['name']} from {other}."


@summary("library_lent")
def _lent_line(world, entry, names, place, other):
    return f"Borrowed a manual of the {entry.data['name']}."


@summary("gift")
def _gift_line(world, entry, names, place, other):
    return f"Gave {other} a gift."
