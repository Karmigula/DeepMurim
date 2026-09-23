"""What the player is told about running the sect."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import cap, outcome, summary

EXTRA_PHRASES.update({"allied_with": "{actor} allied with the {target}.",
                      "sect_dissolved": "{actor} disbanded the {target}."})


def _who(world, event, i=1) -> str:
    return cap(world.entity(event.actors[i]).name)


@outcome("sect_invite", body_facts=False)
def _invite(world, event):
    if event.data["accepted"]:
        return [f"{_who(world, event)} accepts, and sets out for your seat."], {}
    return [f"{_who(world, event)} declines."], {}


@outcome("sect_teach", body_facts=False)
def _teach(world, event):
    return [f"You teach {world.entity(event.actors[1]).name} the {event.data['name']}."], {}


@outcome("sect_elder", body_facts=False)
def _elder(world, event):
    return [f"{_who(world, event)} is raised to elder."], {}


@outcome("sect_duty", body_facts=False)
def _duty(world, event):
    if event.data["on"]:
        return [f"{_who(world, event)} sets out on sect business."], {}
    return [f"{_who(world, event)} is called back to the seat."], {}


@outcome("sect_expel", body_facts=False)
def _expel(world, event):
    return [f"You cast {world.entity(event.actors[1]).name} out of the sect."], {}


@outcome("sect_build", body_facts=False)
def _build(world, event):
    return [f"Work begins on a {event.data['building'].replace('_', ' ')}; it will stand in a season."], {}


@outcome("sect_treasury", body_facts=False)
def _treasury(world, event):
    amount = event.data["amount"]
    return [f"You {'deposit' if amount > 0 else 'withdraw'} {abs(amount)} silver."], {}


@outcome("allied_with", body_facts=False)
def _allied(world, event):
    return [f"Your sect and the {world.entity(event.data['other']).name} are now allies."], {}


@outcome("sect_dissolved", body_facts=False)
def _dissolved(world, event):
    return [f"The {world.entity(event.data['sect']).name} is no more."], {}


for _kind, _line in {"sect_invite": "Invited {other} to the sect.", "sect_teach": "Taught {other} an art.",
                     "sect_elder": "Raised {other} to elder.", "sect_duty": "Sent {other} on sect business.",
                     "sect_expel": "Cast {other} out of the sect.", "sect_build": "Began a new building.",
                     "sect_treasury": "Moved silver in the treasury.", "allied_with": "Made an alliance.",
                     "sect_dissolved": "The sect was dissolved."}.items():
    summary(_kind)(lambda world, entry, names, place, other, _line=_line: _line.format(other=other))
