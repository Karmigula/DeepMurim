"""What the player is told about joining and leaving factions."""

from narrate.gossip_text import EXTRA_PHRASES
from narrate.outcomes import cap, outcome, summary
from systems import factions as F

EXTRA_PHRASES.update({
    "expelled": "{actor} {be} cast out of the {target}.",
    "deserted": "{actor} deserted the {target}.",
    "spy_exposed": "{actor} {be} unmasked as a spy in the {target}.",
    "released": "{actor} left the {target} with its blessing.",
})
LEFT_LINES = {"expelled": "You are cast out of the {name}.", "deserted": "You desert the {name}.",
              "spy_exposed": "You are exposed as a spy of the {name}!", "released": "The {name} releases you."}
LEFT_SUMMARY = {"expelled": "Cast out of the {name}.", "deserted": "Deserted the {name}.",
                "spy_exposed": "Exposed as a spy of the {name}.", "released": "Released by the {name}."}


def _faction(world, data) -> str:
    return world.entity(data["faction"]).name


def _days(world, deadline) -> int:
    return max(1, (deadline - world.time) // 4)


@outcome("trial_begun", body_facts=False)
def _trial(world, event):
    d, name = event.data, _faction(world, event.data)
    kind = d["kind"]
    if kind == "spar":
        line = "Very well. Show us what you can do against one of our disciples."
    elif kind == "blood":
        target = world.entity(d["target"])
        town = world.entity(world.targets(d["target"], "located_in")[0]).name
        line = f"Prove your resolve: {target.name} of {town} must die within {_days(world, d['deadline'])} days."
    elif kind in ("service", "escort"):
        what = "Carry our word" if kind == "service" else "See a caravan safely"
        line = f"{what} to {world.entity(d['town']).name} within {_days(world, d['deadline'])} days."
    elif kind == "ears":
        line = "Bring me three things I have not heard."
    else:
        line = "Beat our chief, or pay tribute."
    return [f"The {name} will test you. {line}"], {}


@outcome("joined", body_facts=False)
def _joined(world, event):
    d, name = event.data, _faction(world, event.data)
    out = [f"You are now {F.title(world, d['faction'], 0)} of the {name}."]
    if d["sponsor"]:
        out.append(f"You join {world.entity(d['sponsor']).name}'s hall.")
    if d["secret"]:
        out.append("Your joining is kept secret.")
    return out, {}


@outcome("trial_failed", body_facts=False)
def _failed(world, event):
    return [f"You have failed the trial of the {_faction(world, event.data)}."], {}


def _left_outcome(world, event):
    return [LEFT_LINES[event.kind].format(name=_faction(world, event.data))], {}


def _left_summary(world, entry, names, place, other):
    return LEFT_SUMMARY[entry.kind].format(name=_faction(world, entry.data))


for _kind in LEFT_LINES:
    outcome(_kind, body_facts=False)(_left_outcome)
    summary(_kind)(_left_summary)


@summary("trial_begun")
def _trial_line(world, entry, names, place, other):
    return f"Began the trial of the {_faction(world, entry.data)}."


@summary("joined")
def _joined_line(world, entry, names, place, other):
    return f"Joined the {_faction(world, entry.data)}."


@summary("trial_failed")
def _failed_line(world, entry, names, place, other):
    return f"Failed the trial of the {_faction(world, entry.data)}."
