"""What the player is told about their sect's seasons."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import outcome, summary

EXTRA_PHRASES.update({"defended_gate": "The {actor} drove off {target} at its gate.",
                      "gate_breached": "{target} broke through the gate of the {actor}."})


@outcome("sect_season", body_facts=False)
def _season(world, event):
    return [event.data["line"]], {}


@summary("sect_season")
def _season_line(world, entry, names, place, other):
    return entry.data["line"]
