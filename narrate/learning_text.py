"""What the player is told about lessons, purchases and study. Never a true completeness."""

from narrate.outcomes import cap, outcome, summary


@outcome("learned", body_facts=False)
def _learned(world, event):
    teacher = world.entity(event.actors[1]).name
    how = " after passing their test" if event.data["via"] == "test" else ""
    return [f"{cap(teacher)} teaches you the {event.data['name']}{how}."], {"art": event.data["name"]}


@outcome("handed_over", body_facts=False)
def _handed(world, event):
    items = [world.entity(i).name for i in event.data["items"]]
    if event.data["reason"] == "bought":
        return [f"You buy the {', '.join(items)}."], {}
    return [f"The {', '.join(items)} changes hands."], {}


@outcome("studied_manual")
def _studied(world, event):
    return [f"You study the {event.data['name']} manual for two weeks.",
            "Its pages claim to hold the whole art."], {"art": event.data["name"], "days": "two weeks"}


@summary("learned")
def _learned_line(world, entry, names, place, other):
    return f"Learned the {entry.data['name']} from {other}."


@summary("handed_over")
def _handed_line(world, entry, names, place, other):
    return "Bought a manual." if entry.data["reason"] == "bought" else "Items changed hands."


@summary("studied_manual")
def _studied_line(world, entry, names, place, other):
    return f"Studied the {entry.data['name']} manual."
