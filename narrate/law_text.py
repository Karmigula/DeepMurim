"""What the player is told about the law."""

from narrate.outcomes import cap, outcome, summary


@outcome("arrest", body_facts=False)
def _arrest(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} bars your way: there is a price of "
            f"{event.data['bounty']} silver on your head here."], {}


@outcome("fined", body_facts=False)
def _fined(world, event):
    return [f"You pay the fine of {event.data['bounty']} silver. The charges are settled."], {}


@outcome("jailed", body_facts=False)
def _jailed(world, event):
    return [f"You spend {event.data['days']} days in a cell. The charges are settled."], {}


@outcome("escaped_arrest", body_facts=False)
def _escaped(world, event):
    return [f"You break away from {world.entity(event.actors[1]).name}."], {}


@summary("arrest")
def _arrest_line(world, entry, names, place, other):
    return f"Arrested by {other} in {place}."


@summary("fined")
def _fined_line(world, entry, names, place, other):
    return f"Paid a fine of {entry.data['bounty']} silver."


@summary("jailed")
def _jailed_line(world, entry, names, place, other):
    return f"Spent {entry.data['days']} days in a cell."


@summary("escaped_arrest")
def _escaped_line(world, entry, names, place, other):
    return f"Broke away from {other}."
