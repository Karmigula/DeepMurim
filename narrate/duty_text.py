"""What the player is told about duties."""

from narrate.outcomes import cap, outcome, summary

VERBS = {"hunt": "Hunt down {target} in the {region}", "deliver": "Carry a sealed letter to {town}",
         "escort": "Escort a caravan to {town}", "collect": "Collect {amount} silver owed by {target} of {town}",
         "gather": "Find out what you can about {target}", "guard": "Stand guard at the seat for {days} days",
         "alchemy": "{alchemy}"}


def _alchemy(world, d) -> str:
    """An alchemy duty's task in words (phase 5c)."""
    if d.get("task") == "bring":
        return f"Bring {d['count']} {d['herb']} to the seat"
    if d.get("task") == "refine":
        return f"Refine a {world.entity(d['recipe']).name} and bring it to the seat"
    return ""


def _faction(world, data) -> str:
    return world.entity(data["faction"]).name


@outcome("duty_issued", body_facts=False)
def _issued(world, event):
    d = event.data
    target = world.entity(d["target"]).name if d.get("target") else "someone"
    town = world.entity(d["town"]).name if d.get("town") else "the seat"
    region = world.entity(world.targets(d["target"], "located_in")[0]).name if d["kind"] == "hunt" else ""
    days = max(1, (d["deadline"] - world.time) // 4)
    task = VERBS[d["kind"]].format(target=target, town=town, region=region, amount=d.get("amount", 0), days=d["days"],
                                   alchemy=_alchemy(world, d))
    return [f"Your duty for the {_faction(world, d)}: {task}, within {days} days."], {}


@outcome("duty_done", body_facts=False)
def _done(world, event):
    d = event.data
    return [f"Your duty for the {_faction(world, d)} is done: {d['merit']} merit and {d['silver']} silver."], {}


@outcome("duty_failed", body_facts=False)
def _failed(world, event):
    why = {"abandoned": "You abandon", "raided": "The raiders break through; you have failed",
           "late": "You have failed"}.get(event.data["reason"], "You have failed")
    return [f"{why} your duty for the {_faction(world, event.data)}."], {}


@outcome("debt_paid", body_facts=False)
def _paid(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} pays the {event.data['amount']} silver owed."], {}


@outcome("raid", body_facts=False)
def _raid(world, event):
    return [f"Raiders strike at the seat! {cap(world.entity(event.actors[1]).name)} comes at you."], {}


@summary("duty_issued")
def _issued_line(world, entry, names, place, other):
    return f"Took a duty for the {_faction(world, entry.data)}."


@summary("duty_done")
def _done_line(world, entry, names, place, other):
    return f"Finished a duty for the {_faction(world, entry.data)}."


@summary("duty_failed")
def _failed_line(world, entry, names, place, other):
    return f"Failed a duty for the {_faction(world, entry.data)}."


@summary("debt_paid")
def _paid_line(world, entry, names, place, other):
    return f"Collected a debt from {other}."


@summary("raid")
def _raid_line(world, entry, names, place, other):
    return f"Fought off {other} at the seat."
