"""What the player is told of plots (phase 4h spec 9, 11): the tales of exposures, what their clues say, their deeds."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

CLUE_WORDS = {"body": "{poison} on the late master's lips", "witness": "a witness saw {name} at the master's door",
              "motive": "letters and debts in {name}'s quarters", "silver": "{name}'s silver in a voter's purse",
              "envoy": "{name} is another sect's envoy", "night": "{name} seen outside the walls at night",
              "mark": "the cult's mark among {name}'s things", "seal": "the will's seal is false, and {name} had it made",
              "scribe": "the scribe who wrote the will for {name}", "planted": "the evidence was planted by {name}",
              "false_witness": "a witness paid by {name} to swear to the crime",
              "missing": "a witness gone missing, after crossing {name}"}
CRIME_WORDS = {"stole_art": "stole the sect's secret art", "killed_disciple": "killed a fellow disciple"}


def clue_words(world, kind: str, person, viewer: int, poison: str | None = None) -> str:
    return CLUE_WORDS.get(kind, "something that points at {name}").format(
        name=who(world, person, viewer), poison=poison or "a poison")


def _faction(world, faction) -> str:
    entity = world.entity(faction) if isinstance(faction, int) else None
    return f"the {entity.name}" if entity is not None and entity.kind == "faction" else "a sect"


def _poisoned(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} poisoned {who(world, v.get('target'), viewer)}.")


def _murdered(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} was exposed as the murderer of {who(world, v.get('target'), viewer)}.")


def _puppet(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} was a puppet of {_faction(world, v.get('target'))}.")


def _spy_for(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} was a spy for {_faction(world, v.get('target'))}.")


def _spy_exposed(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} was unmasked as a cult spy in {_faction(world, v.get('target'))}.")


def _framed(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} framed {who(world, v.get('target'), viewer)} for a crime never done.")


def _forged(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} forged the late master's will of {_faction(world, v.get('target'))}.")


def _cleared(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)}'s name was cleared in {_faction(world, v.get('target'))}.")


def _crime(predicate):
    def story(world, v, viewer) -> str:
        return cap(f"{who(world, v.get('actor'), viewer)} {CRIME_WORDS[predicate]} and was cast out of "
                   f"{_faction(world, v.get('target'))}.")
    return story


def _defied(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} defied the arbiter of {_faction(world, v.get('target'))}.")


def _false_accusation(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} accused {who(world, v.get('target'), viewer)} falsely.")


def _clue(world, v, viewer) -> str:
    return cap(f"In {_faction(world, v.get('target'))}: {clue_words(world, v.get('kind'), v.get('actor'), viewer)}.")


SPECIAL_PHRASES.update({"poisoned": _poisoned, "murdered": _murdered, "puppet_of": _puppet, "spy_for": _spy_for,
                        "spy_exposed": _spy_exposed, "framed": _framed, "forged_will": _forged, "cleared": _cleared,
                        "stole_art": _crime("stole_art"), "killed_disciple": _crime("killed_disciple"),
                        "defied_arbiter": _defied, "false_accusation": _false_accusation, "clue": _clue})


def _name(world, person) -> str:
    entity = world.entity(person) if person is not None else None
    return entity.name if entity is not None else "someone"


@outcome("body_examined", body_facts=False)
def _examined(world, event):
    if event.data["found"]:
        return [f"You kneel by the late master. The lips are dark: {event.data['poison']}. This was no natural death."], {}
    return ["You kneel by the late master and find nothing the physicians missed."], {}


@summary("body_examined")
def _examined_line(world, entry, names, place, other):
    return "Found poison on a dead master's lips." if entry.data["found"] else f"Looked on a dead master at {place}."


@outcome("clue_found", body_facts=False)
def _found(world, event):
    plot = world.entity(event.data["plot"])
    poison = next((c.get("poison") for c in plot.data["clues"] if c["kind"] == "body"), None)
    return [f"You have found it: {clue_words(world, event.data['kind'], event.data['points_to'], event.actors[0], poison)}."], {}


@summary("clue_found")
def _found_line(world, entry, names, place, other):
    return f"Found something that points at {other}."


@outcome("quarters_searched", body_facts=False)
def _searched(world, event):
    return (["You turn their quarters over, and something turns up."] if event.data["found"]
            else ["You turn their quarters over and find nothing."]), {}


@summary("quarters_searched")
def _searched_line(world, entry, names, place, other):
    return f"Searched {other}'s quarters."


@outcome("plot_exposed", body_facts=False)
def _exposed(world, event):
    plot = world.entity(event.data["plot"])
    return [f"Before the elders it all comes out: {plot.name}. {_name(world, plot.data['plotter'])} has nowhere to hide."], {}


@summary("plot_exposed")
def _exposed_line(world, entry, names, place, other):
    return f"Exposed {world.entity(entry.data['plot']).name} at {place}."


@outcome("false_accusation", body_facts=False)
def _false(world, event):
    return [f"The elders hear you out, and the evidence falls apart in your hands. {_name(world, event.actors[1])} "
            f"will not forget this."], {}


@summary("false_accusation")
def _false_line(world, entry, names, place, other):
    return f"Accused {other} falsely before the elders at {place}."


@outcome("asked_night", body_facts=False)
def _night(world, event):
    return (["They lower their voice and tell you what they saw that night."] if event.data["told"]
            else ["They saw nothing that night, they say."]), {}


@summary("asked_night")
def _night_line(world, entry, names, place, other):
    return f"Asked {other} about the night the master died."


@outcome("asked_about", body_facts=False)
def _asked(world, event):
    return (["They hesitate, then tell you more than they meant to."] if event.data["told"]
            else ["They have nothing to tell you."]), {}


@summary("asked_about")
def _asked_line(world, entry, names, place, other):
    return f"Questioned {other}."


@outcome("will_examined", body_facts=False)
def _will(world, event):
    return (["You hold the will to the light: the seal is not the late master's."] if event.data["found"]
            else ["The will looks like any will, and the seal like any seal."]), {}


@summary("will_examined")
def _will_line(world, entry, names, place, other):
    return f"Studied the late master's will at {place}."


@outcome("founder_passed", body_facts=False)
def _passed(world, event):
    return ["The founder's hall falls silent around you, and then the old bell rings once: you are chosen."], {}


@summary("founder_passed")
def _passed_line(world, entry, names, place, other):
    return f"{names[0]} passed the founder's test at {place}."


@outcome("founder_failed", body_facts=False)
def _failed(world, event):
    return ["The founder's hall rejects you. You come out broken, and without a claim."], {}


@summary("founder_failed")
def _failed_line(world, entry, names, place, other):
    return f"{names[0]} failed the founder's test at {place}."


@outcome("heir_returned", body_facts=False)
def _returned(world, event):
    return [f"{_name(world, event.actors[0])} comes back through the gate of the "
            f"{world.entity(event.data['faction']).name}, and demands the seat."], {}


@summary("heir_returned")
def _returned_line(world, entry, names, place, other):
    return f"{names[0]} returned to {place} to demand the seat."


for kind in ("murder_revealed", "puppet_revealed", "spy_revealed", "forgery_revealed", "frame_revealed",
             "thanked", "claim_joined"):
    @outcome(kind, body_facts=False)
    def _quiet(world, event):
        return [], {}


def _deed(predicate: str, words: str):
    def story(world, v, viewer) -> str:
        return cap(f"{who(world, v.get('actor'), viewer)} {words} {_faction(world, v.get('target'))}.")
    return story


SPECIAL_PHRASES.update({"poisoner": _deed("poisoner", "was exposed as the poisoner in"),
                        "spymaster": _deed("spymaster", "was exposed as the one who planted a spy in"),
                        "framer": _deed("framer", "was exposed as the one who framed a claimant of"),
                        "forger": _deed("forger", "was exposed as the forger of a will in"),
                        "puppet_master": _deed("puppet_master", "was exposed as the silver behind a claimant of")})


@outcome("poison_bought", body_facts=False)
def _poison_bought(world, event):
    return [f"{_name(world, event.actors[1])} wraps a small black vial in cloth and takes your silver without a word."], {}


@summary("poison_bought")
def _poison_bought_line(world, entry, names, place, other):
    return f"Bought a poison in {place}."


@outcome("poison_slipped", body_facts=False)
def _slipped(world, event):
    return [f"You pour the tea. {_name(world, event.actors[1])} drinks, and does not see the dawn."], {}


@summary("poison_slipped")
def _slipped_line(world, entry, names, place, other):
    return f"Poisoned {other}."


@outcome("spy_sent", body_facts=False)
def _spy_sent(world, event):
    return [f"{_name(world, event.actors[1])} bows, takes your silver, and goes to knock on the "
            f"{world.entity(event.data['faction']).name}'s gate as a stranger."], {}


@summary("spy_sent")
def _spy_sent_line(world, entry, names, place, other):
    return f"Sent {other} to spy for you."


@outcome("claim_funded", body_facts=False)
def _funded(world, event):
    return [f"Your silver goes quietly to {_name(world, event.actors[1])}'s camp."], {}


@summary("claim_funded")
def _funded_line(world, entry, names, place, other):
    return f"Put silver behind {other}'s claim."


@outcome("frame_paid", body_facts=False)
def _frame_paid(world, event):
    return ["The evidence is made, and placed where it will be found."], {}


@summary("frame_paid")
def _frame_paid_line(world, entry, names, place, other):
    return f"Paid for false evidence against {other}."


@outcome("forgery_paid", body_facts=False)
def _forgery_paid(world, event):
    return ["A scribe who owes no one anything copies the late master's hand, and a will is read out."], {}


@summary("forgery_paid")
def _forgery_paid_line(world, entry, names, place, other):
    return f"Had a will forged at {place}."


for kind in ("scheme_exposed", "puppet_thanks", "spy_reported", "framed_out", "plot_made"):
    @outcome(kind, body_facts=False)
    def _quiet_deed(world, event):
        return [], {}
