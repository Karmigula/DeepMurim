"""What the player is told when they create an art."""

from narrate.outcomes import outcome, summary


@outcome("created_technique")
def _created(world, event):
    d = event.data
    sources = ", ".join(sorted({f["technique"] for f in d["used"]}))
    return [f"You create a new art: the {d['name']}!",
            f"It grew from what you glimpsed of the {sources}.",
            "No one else in the world knows it."], {"art": d["name"]}


@summary("created_technique")
def _created_line(world, entry, names, place, other):
    return f"Created the {entry.data['name']}."
