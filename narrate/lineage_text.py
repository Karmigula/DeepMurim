"""What the player is told about lineage (phase 4b)."""

from narrate.outcomes import outcome, summary


@outcome("player_aged", body_facts=False)
def _aged(world, event):
    return [], {}


@summary("player_aged")
def _aged_line(world, entry, names, place, other):
    return f"Grew older (now {int(entry.data['age'])})."
