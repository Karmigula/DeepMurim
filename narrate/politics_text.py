"""What the player is told about summons, judgement and rivals."""

from narrate.outcomes import cap, outcome, summary

CHARGES = {"robbed": "robbing", "killed": "killing", "crippled": "crippling", "spared": "sparing",
           "member_of": "consorting with", "defeated": "attacking", "left_for_dead": "maiming"}


def _faction(world, data) -> str:
    return world.entity(data["faction"]).name


def _charge(world, data) -> str:
    fact = world.fact(data["fact"])
    target = fact.variant.get("target") if fact is not None else None
    whom = world.entity(target).name if isinstance(target, int) and world.entity(target) else "someone"
    return f"{CHARGES.get(data.get('predicate') or (fact.predicate if fact else ''), 'wrongdoing')} {whom}"


@outcome("summoned", body_facts=False)
def _summoned(world, event):
    d = event.data
    return [f"{cap(world.entity(event.actors[1]).name)} summons you before the {_faction(world, d)}.",
            f"You stand accused of {_charge(world, d)}."], {}


@outcome("judged", body_facts=False)
def _judged(world, event):
    d = event.data
    line = {"punished": "You are punished: your merit is docked.", "cleared": "The charge is set aside.",
            "expelled": "Judgement goes against you."}[d["outcome"]]
    out = [line]
    fact = world.fact(d["fact"])
    liar = fact.data.get("liar") if fact is not None else None
    if d["outcome"] == "cleared" and liar:
        out.append(f"{cap(world.entity(event.actors[1]).name)} lets slip that it was {world.entity(liar).name} who spread it.")
    return out, {}


@outcome("rival_exposed", body_facts=False)
def _exposed(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} is exposed as a liar and cast out.", "Your standing rises."], {}


@summary("summoned")
def _summoned_line(world, entry, names, place, other):
    return f"Summoned by the {_faction(world, entry.data)}."


@summary("judged")
def _judged_line(world, entry, names, place, other):
    return f"Judged by the {_faction(world, entry.data)}: {entry.data['outcome']}."


@summary("rival_exposed")
def _exposed_line(world, entry, names, place, other):
    return f"Exposed {other} as a liar."
