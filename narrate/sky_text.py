"""What the player is told about the sky and the Murim's great events (phase 4d)."""

from narrate.gossip_text import SPECIAL_PHRASES
from narrate.outcomes import cap, outcome, summary
from systems.realms import REALMS

NAMES = {"qi_tide": "a qi tide", "blood_moon": "a blood moon", "comet": "a comet",
         "dao_resonance": "a dao resonance", "tribulation": "tribulation lightning", "beast_tide": "a beast tide"}
STAGE_WORDS = {"foretold": "is foretold over", "announced": "gathers over", "active": "hangs over",
               "aftermath": "has passed over"}


def phenomenon_name(kind: str) -> str:
    return NAMES.get(kind, "a " + kind.replace("_", " "))


def _phenomenon_story(world, variant, viewer) -> str:
    where = variant.get("place") or "the land"
    text = f"{cap(phenomenon_name(variant.get('kind', 'omen')))} {STAGE_WORDS.get(variant.get('stage'), 'was seen over')} {where}."
    if variant.get("reading"):
        text += f" People say it means {variant['reading']}."
    return text


SPECIAL_PHRASES["phenomenon"] = _phenomenon_story


TRIBULATION_WORDS = {
    "clean": "You stand in the lightning and come through whole; heaven has let you pass.",
    "scarred": "The lightning finds you. You come through it scarred and shaking.",
    "crippled": "The lightning tears through your meridians. You live, but something in you is broken.",
}


def _tribulation_story(world, variant, viewer) -> str:
    who = "you" if variant.get("actor") == viewer else (world.entity(variant["actor"]).name if variant.get("actor") else "someone")
    where = variant.get("place") or "the hills"
    return cap(f"heavenly lightning fell on {who} in {where}, breaking through to {variant.get('realm') or 'a higher realm'}.")


SPECIAL_PHRASES["tribulation"] = _tribulation_story


@outcome("tribulation")
def _tribulation(world, event):
    d = event.data
    return [f"Clouds gather over you as you reach {REALMS[d['realm']].name}. {TRIBULATION_WORDS.get(d.get('outcome'), '')}".strip()], {}


@summary("tribulation")
def _tribulation_line(world, entry, names, place, other):
    return f"Faced the heavenly tribulation in {place}: {entry.data.get('outcome') or 'witnessed'}."


@outcome("beast_hunted", body_facts=False)
def _hunted(world, event):
    return [f"That is {event.data['kills']} beast{'s' if event.data['kills'] != 1 else ''} for the magistrate's bounty."], {}


@summary("beast_hunted")
def _hunted_line(world, entry, names, place, other):
    return f"Killed a beast in the beast tide near {place}."


@outcome("bounty_paid", body_facts=False)
def _paid(world, event):
    return [f"The magistrate pays you {event.data['silver']} silver for the beasts."], {}


@summary("bounty_paid")
def _paid_line(world, entry, names, place, other):
    return f"Was paid {entry.data['silver']} silver for hunting beasts near {place}."
