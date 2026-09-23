"""What the player is told on the road, and about tolls and payments."""

from narrate.outcomes import cap, outcome, summary

HOW = {
    "paid": "You pay and are let through.", "talked": "You talk your way past {name}.",
    "fled": "You slip away from {name}.", "fight": "There is no way around it: you fight.",
    "backed_off": "{name} recognises you, thinks better of it and slips away.",
}


def _name(world, event) -> str:
    return world.entity(event.actors[1]).name


@outcome("encounter")
def _encounter(world, event):
    d, name = event.data, _name(world, event)
    line = {
        "bandit": f"{cap(name)}, a bandit, blocks the road and demands {d['toll']} silver.",
        "beast": f"{cap(name)} stalks out onto the road, hungry.",
        "wanderer": f"{cap(name)}, a wandering swordsman, bars the road and looks you over.",
        "avenger": f'{cap(name)} steps into the road. "You killed my {d.get("role") or "kin"}."',
    }[d["kind"]]
    return [line], {"grammar_key": f"encounter.{d['kind']}"}


@outcome("encounter_resolved")
def _resolved(world, event):
    return [cap(HOW[event.data["how"]].format(name=_name(world, event)))], {}


@outcome("challenge_issued", body_facts=False)
def _challenge(world, event):
    return [f"{cap(_name(world, event))} blocks your way: they have not forgotten you."], {}


@outcome("declined_challenge", body_facts=False)
def _declined(world, event):
    return [f"You turn {_name(world, event)} down. They will not forget it."], {}


@outcome("paid", body_facts=False)
def _paid(world, event):
    return [f"You pay {event.data['amount']} silver."], {}


@summary("encounter")
def _encounter_line(world, entry, names, place, other):
    return f"Met {other} on the road."


@summary("encounter_resolved")
def _resolved_line(world, entry, names, place, other):
    return {"paid": f"Paid {other} to pass.", "talked": f"Talked past {other}.",
            "fled": f"Fled from {other}.", "fight": f"Fought {other} on the road.",
            "backed_off": f"{cap(other)} backed off from you on the road."}.get(entry.data["how"], f"Met {other} on the road.")


@summary("challenge_issued")
def _challenge_line(world, entry, names, place, other):
    return f"{cap(other)} challenged you."


@summary("declined_challenge")
def _declined_line(world, entry, names, place, other):
    return f"Declined {other}'s challenge."


@summary("paid")
def _paid_line(world, entry, names, place, other):
    return f"Paid {entry.data['amount']} silver ({entry.data['reason']})."
