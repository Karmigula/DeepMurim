"""What the player is told about lineage (phase 4b)."""

from narrate.outcomes import outcome, summary


@outcome("tried", body_facts=False)
def _tried(world, event):
    if event.data["verdict"] == "death":
        return ["The magistrate reads the sentence: death."], {}
    return ["The magistrate sentences you to two years in prison."], {}


@summary("tried")
def _tried_line(world, entry, names, place, other):
    return f"Stood trial in {place}."


@outcome("imprisoned", body_facts=False)
def _imprisoned(world, event):
    return ["Two years pass behind stone walls. You walk out a free, older person."], {}


@summary("imprisoned")
def _imprisoned_line(world, entry, names, place, other):
    return f"Spent {entry.data['seasons'] // 4} years in prison in {place}."


@outcome("player_aged", body_facts=False)
def _aged(world, event):
    return [], {}


@summary("player_aged")
def _aged_line(world, entry, names, place, other):
    return f"Grew older (now {int(entry.data['age'])})."
