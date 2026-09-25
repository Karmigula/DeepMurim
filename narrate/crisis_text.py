"""What the player is told of succession crises (phase 4g spec 5): the tales, the kinds of claim, how seats were won."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

KIND_WORDS = {"chief": "the chief disciple", "blood": "the late master's blood", "elder": "an elder",
              "grand_elder": "the Grand Elder, down from seclusion", "regent": "a regent", "player": "a claimant"}
HOW_WORDS = {"backing": "with the elders behind them", "trial": "by trial of arms", "unopposed": "unopposed",
             "chosen": "chosen by the elders", "far": "after a bitter contest", "strife": "by force of arms",
             "stepped_down": "named by the old master", "regency": "as regent"}


def names(world, people, viewer: int) -> str:
    said = [who(world, p, viewer) for p in people]
    return said[0] if len(said) == 1 else ", ".join(said[:-1]) + " and " + said[-1] if said else "no one"


def _faction(world, variant) -> str:
    faction = world.entity(variant.get("target")) if variant.get("target") is not None else None
    return f"the {faction.name}" if faction is not None else "a sect"


def _crisis_story(world, variant, viewer) -> str:
    sect = _faction(world, variant)
    if variant.get("stage") == "settled":
        how = HOW_WORDS.get(variant.get("how"), "")
        return cap(f"{who(world, variant.get('actor'), viewer)} now leads {sect}{', ' + how if how else ''}.")
    return cap(f"{sect} is without a master: {names(world, variant.get('people') or [variant.get('actor')], viewer)} "
               f"each claim the seat.")


def _named_chief_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} was named chief disciple of {_faction(world, variant)}.")


def _transmitted_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)}, dying, poured their inner strength into "
               f"{who(world, variant.get('target'), viewer)}.")



def _schism_story(world, variant, viewer) -> str:
    new = world.entity((variant.get("factions") or [None])[0]) if variant.get("factions") else None
    founded = f" and founded the {new.name}" if new is not None else ""
    return cap(f"{who(world, variant.get('actor'), viewer)} walked out of {_faction(world, variant)} with their "
               f"followers{founded}.")


def _exiled_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} lost the war for the seat of {_faction(world, variant)} "
               f"and was driven out.")


SPECIAL_PHRASES.update({"crisis": _crisis_story, "named_chief": _named_chief_story,
                        "transmitted": _transmitted_story, "schism": _schism_story, "exiled": _exiled_story})


def claim_words(kind: str) -> str:
    return KIND_WORDS.get(kind, "a claimant")


def _name(world, person) -> str:
    entity = world.entity(person) if person is not None else None
    return entity.name if entity is not None else "someone"


def _sect_of(world, event) -> str:
    occurrence = world.entity(event.data["occurrence"])
    return world.entity(occurrence.data["data"]["faction"]).name


@outcome("crisis_declared", body_facts=False)
def _declared(world, event):
    return [f"You stand with {_name(world, event.data['claimant'])} before the {_sect_of(world, event)}."], {}


@summary("crisis_declared")
def _declared_line(world, entry, names, place, other):
    return f"Declared for {other} in the crisis at {place}."


@outcome("crisis_claimed", body_facts=False)
def _claimed(world, event):
    return [f"Before the mourning banners you name yourself for the seat of the {_sect_of(world, event)}."], {}


@summary("crisis_claimed")
def _claimed_line(world, entry, names, place, other):
    return f"Claimed the seat of a sect at {place}."


SWAY_WORDS = {"speak": ("{v} hears you out, and nods slowly.", "{v} hears you out, unmoved."),
              "gift": ("{v} accepts your gift and your cause with it.", "{v} will not touch your silver, and is offended."),
              "threat": ("{v} goes pale, and says they will think again.", "{v} goes pale."),
              "favour": ("{v} names a favour: a letter to carry.", "{v} names a favour: a letter to carry."),
              "favour_done": ("{v} remembers the favour, and leans your way.", "{v} remembers the favour.")}


@outcome("crisis_swayed", body_facts=False)
def _swayed(world, event):
    good, bad = SWAY_WORDS.get(event.data["way"], ("{v} listens.", "{v} listens."))
    return [(good if event.data["delta"] > 0 else bad).format(v=_name(world, event.data["voter"]))], {}


@summary("crisis_swayed")
def _swayed_line(world, entry, names, place, other):
    return f"Worked on {other} in the crisis at {place}."


@outcome("crisis_champion", body_facts=False)
def _champion(world, event):
    return [f"You will fight for {_name(world, event.data['claimant'])} if it comes to a trial."], {}


@summary("crisis_champion")
def _champion_line(world, entry, names, place, other):
    return f"Swore to fight as {other}'s champion at {place}."


@outcome("chambers_searched", body_facts=False)
def _searched(world, event):
    if event.data["found"]:
        return ["Behind a loose board in the late master's study: a sealed will. It is yours to read out or burn."], {}
    return ["You turn the late master's rooms over and find nothing."], {}


@summary("chambers_searched")
def _searched_line(world, entry, names, place, other):
    return "Found the late master's will." if entry.data["found"] else "Searched the late master's rooms in vain."


@outcome("will_revealed", body_facts=False)
def _revealed(world, event):
    return [f"You read the will aloud: it names {_name(world, event.data['names'])}."], {}


@summary("will_revealed")
def _revealed_line(world, entry, names, place, other):
    return f"Read out the late master's will at {place}."


@outcome("will_burned", body_facts=False)
def _burned(world, event):
    return ["The will curls and blackens in the brazier."], {}


@summary("will_burned")
def _burned_line(world, entry, names, place, other):
    return f"Burned the late master's will at {place}."


@outcome("will_taken", body_facts=False)
def _will_taken(world, event):
    return ["You take the late master's will from them."], {}


@summary("will_taken")
def _will_taken_line(world, entry, names, place, other):
    return f"Won the late master's will at {place}."


@outcome("sect_token_bought", body_facts=False)
def _token_bought(world, event):
    return [f"{_name(world, event.actors[1])} counts your {event.data['silver']} silver and hands over the token."], {}


@summary("sect_token_bought")
def _token_bought_line(world, entry, names, place, other):
    return f"Bought a sect's leader's token from {other}."


@outcome("sect_token_taken", body_facts=False)
def _token_taken(world, event):
    return [f"You pick up {world.entity(event.data['token']).name}."], {}


@summary("sect_token_taken")
def _token_taken_line(world, entry, names, place, other):
    return f"Picked up a sect's leader's token at {place}."


@outcome("sect_token_won", body_facts=False)
def _token_won(world, event):
    return [f"You take {world.entity(event.data['token']).name} from {_name(world, event.actors[1])}."], {}


@summary("sect_token_won")
def _token_won_line(world, entry, names, place, other):
    return f"Won a sect's leader's token from {other}."


@outcome("sect_token_handed", body_facts=False)
def _token_handed(world, event):
    paid = f", and {event.data['silver']} silver changes hands" if event.data["silver"] else ""
    return [f"You place the token in {_name(world, event.actors[1])}'s hands{paid}."], {}


@summary("sect_token_handed")
def _token_handed_line(world, entry, names, place, other):
    return f"Handed a sect's leader's token to {other}."


@outcome("crisis_trial", body_facts=False)
def _trial(world, event):
    trial = event.data["trial"]
    if trial.get("pending"):
        return ["The claimants' camps cannot agree: it will be settled by a trial of arms."], {}
    return [f"The trial is fought: {_name(world, trial['winner'])}'s side has won it."], {}


@summary("crisis_trial")
def _trial_line(world, entry, names, place, other):
    return f"A trial of arms for a sect's seat at {place}."


@outcome("crisis_settled", body_facts=False)
def _settled(world, event):
    return [f"{_name(world, event.data['winner'])} takes the seat of the {_sect_of(world, event)}."], {}


@summary("crisis_settled")
def _settled_line(world, entry, names, place, other):
    return f"{names[0] if names else 'Someone'} took a sect's seat at {place}."


@outcome("crisis_refused", body_facts=False)
def _refused(world, event):
    return [f"{_name(world, event.actors[0])} will not bow to the trial. It will be settled by arms."], {}


@summary("crisis_refused")
def _refused_line(world, entry, names, place, other):
    return f"{names[0]} refused the trial at {place}; the camps went to war."


@outcome("crisis_lost", body_facts=False)
def _lost(world, event):
    return [], {}


@summary("crisis_lost")
def _lost_line(world, entry, names, place, other):
    return f"{other} lost the seat to {names[0]}."
