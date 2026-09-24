"""What the player is told about the sky and the Murim's great events (phase 4d)."""

from narrate.gossip_text import SPECIAL_PHRASES
from narrate.outcomes import cap, outcome, summary
from systems.realms import REALMS

NAMES = {"qi_tide": "a qi tide", "blood_moon": "a blood moon", "comet": "a comet",
         "dao_resonance": "a dao resonance", "tribulation": "tribulation lightning", "beast_tide": "a beast tide",
         "treasure_light": "a pillar of treasure light", "star_fall": "a falling star"}
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


PRIZE_WORDS = {"manual": "a martial manual", "pill": "a heavenly pill", "herb": "a spirit herb", "star_iron": "star iron"}


def race_line(world, occurrence: int, distance: int) -> str:
    d = world.entity(occurrence).data
    town = world.entity(d["place"]).name
    how_far = "here" if distance == 0 else f"{distance} region{'s' if distance != 1 else ''} away"
    return f"{cap(phenomenon_name(d['type']))} stands over {town}, {how_far}."


def _treasure_story(world, variant, viewer) -> str:
    who = "you" if variant.get("actor") == viewer else (world.entity(variant["actor"]).name if variant.get("actor") else "someone")
    return cap(f"{who} claimed {PRIZE_WORDS.get(variant.get('prize'), 'a treasure')} in {variant.get('place') or 'the wilds'}.")


SPECIAL_PHRASES["treasure"] = _treasure_story


@outcome("race_fought", body_facts=False)
def _fought(world, event):
    champion = world.entity(event.actors[1]).name
    if event.data["won"]:
        return [f"{champion} falls back; the way to the treasure is a step clearer."], {}
    return [f"{champion} bars the way. Your chance at the treasure is gone."], {}


@summary("race_fought")
def _fought_line(world, entry, names, place, other):
    return f"{'Beat' if entry.data['won'] else 'Lost to'} {other} in the race for a treasure near {place}."


@outcome("treasure_claimed", body_facts=False)
def _claimed(world, event):
    prize = event.data["prize"]
    what = prize.get("name") or PRIZE_WORDS.get(prize["kind"], "the treasure")
    return [f"You claim the treasure: {what}."], {}


@summary("treasure_claimed")
def _claimed_line(world, entry, names, place, other):
    prize = entry.data["prize"]
    return f"Claimed {prize.get('name') or PRIZE_WORDS.get(prize['kind'], 'a treasure')} near {place}."


@outcome("swallowed", body_facts=True)
def _swallowed(world, event):
    return [f"You swallow it. Qi floods your meridians: {event.data['qi_years']:.1f} years of it."], {}


@summary("swallowed")
def _swallowed_line(world, entry, names, place, other):
    return f"Swallowed a pill worth {entry.data['qi_years']:.1f} years of qi."


@outcome("sold_treasure", body_facts=False)
def _sold(world, event):
    return [f"You sell {world.entity(event.data['item']).name} for {event.data['silver']} silver."], {}


@summary("sold_treasure")
def _sold_line(world, entry, names, place, other):
    return f"Sold a treasure in {place} for {entry.data['silver']} silver."
