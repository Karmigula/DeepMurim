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


@outcome("proposal", body_facts=False)
def _proposal(world, event):
    name = world.entity(event.actors[1]).name
    if event.data["accepted"]:
        return [f"{name} says yes. You are married."], {}
    return [f"{name} turns you down, gently but firmly."], {}


@summary("proposal")
def _proposal_line(world, entry, names, place, other):
    return f"Married {other}." if entry.data.get("accepted") else f"{other} turned down your proposal."


@outcome("took_disciple", body_facts=False)
def _took(world, event):
    return [f"{world.entity(event.actors[1]).name} kneels and becomes your disciple."], {}


@summary("took_disciple")
def _took_line(world, entry, names, place, other):
    return f"Took {other} as a disciple."


@outcome("sworn_siblings", body_facts=False)
def _sworn(world, event):
    return [f"You and {world.entity(event.actors[1]).name} swear to be kin."], {}


@summary("sworn_siblings")
def _sworn_line(world, entry, names, place, other):
    return f"Swore kinship with {other}."


@outcome("named_heir", body_facts=False)
def _named(world, event):
    return [f"You name {world.entity(event.actors[1]).name} your heir."], {}


@summary("named_heir")
def _named_line(world, entry, names, place, other):
    return f"Named {other} as heir."


@summary("born")
def _born_line(world, entry, names, place, other):
    return f"{names[2]} was born in {place}."


@outcome("succession", body_facts=False)
def _succession(world, event):
    old, heir = (world.entity(a) for a in event.actors)
    return [f"You take up the mantle of {old.name}.", f"You are {heir.name} now."], {}


@summary("succession")
def _succession_line(world, entry, names, place, other):
    return f"Took up the mantle of {names[0]}."


@outcome("player_aged", body_facts=False)
def _aged(world, event):
    return [], {}


@summary("player_aged")
def _aged_line(world, entry, names, place, other):
    return f"Grew older (now {int(entry.data['age'])})."
