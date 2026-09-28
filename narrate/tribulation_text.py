"""What the player is told of a tribulation: the gathering, each wave, and what heaven leaves (phase 5f spec 5)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

KIND_WORDS = {"lightning": "the lightning", "fire": "the heavenly fire", "demon": "the demon"}


@outcome("tribulation_gathers", body_facts=False)
def _gathers(world, event):
    d = event.data
    if d["why"] == "notice":
        return ["The sky darkens over you alone. Heaven has taken notice of what you have done."], {}
    if d["minor"]:
        return ["A small, hard cloud gathers overhead. Even this gate is watched."], {}
    return [f"Heaven answers with {len(d['waves'])} waves."], {}


@summary("tribulation_gathers")
def _gathers_line(world, entry, names, place, other):
    if entry.data["minor"]:
        return "A minor tribulation came down." if entry.data["why"] != "notice" else "Heaven took notice of you."
    return f"Heaven sent {len(entry.data['waves'])} waves."


@outcome("tribulation_wave", body_facts=False)
def _wave(world, event):
    d = event.data
    if d["kind"] == "demon":
        return [], {}
    if d["choice"] == "spend":
        return [f"The pill burns in you, and {KIND_WORDS[d['kind']]} breaks around you like water on stone."], {}
    if d["choice"] == "shelter":
        return [f"The array's flags blaze and take {KIND_WORDS[d['kind']]} into the earth."], {}
    if d["success"]:
        return [f"You stand in {KIND_WORDS[d['kind']]} and it passes through you."], {}
    return [f"{cap(KIND_WORDS[d['kind']])} tears through you."], {}


@summary("tribulation_wave")
def _wave_line(world, entry, names, place, other):
    d = entry.data
    return f"{'Weathered' if d['success'] else 'Was struck by'} {KIND_WORDS[d['kind']]} of a tribulation."


@outcome("tribulation_passed", body_facts=False)
def _passed(world, event):
    d = event.data
    if d["died"]:
        return ["The last wave finds nothing left to hold it back."], {}
    return [{"clean": "The clouds break. You come through heaven's tribulation whole.",
             "scarred": "The clouds break. You come through, scarred.",
             "crippled": "The clouds break. You come through, but heaven has taken something with it."}[d["outcome"]]], {}


@summary("tribulation_passed")
def _passed_line(world, entry, names, place, other):
    d = entry.data
    return "Died in heaven's tribulation." if d["died"] else f"Came through a tribulation {d['outcome']}."


def _fell(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} fell to the heavenly tribulation in {v.get('place') or 'a town'}.")


SPECIAL_PHRASES["fell_to_tribulation"] = _fell
