"""What the player is told of halls, gardens, the Guild, the clinic, theft, healing, contracts and the worms
(phase 5c spec 7)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import EXTRA_PHRASES, SPECIAL_PHRASES, who

import systems.guild as G


def _name(world, entity_id) -> str:
    entity = world.entity(entity_id) if isinstance(entity_id, int) else None
    return entity.name if entity else "someone"


def _where(v) -> str:
    return f" in {v['place']}" if v.get("place") else ""


# --- rumours ---------------------------------------------------------------------------------------------------

def _guild_rank(world, v, viewer) -> str:
    be = "are" if v.get("actor") == viewer else "is"
    return cap(f"{who(world, v.get('actor'), viewer)} {be} now {G.title(v.get('rank', 0))}.")


def _robbed_hall(world, v, viewer) -> str:
    what = {"garden": "herb garden", "hall": "pill hall", "scroll": "pill hall"}.get(v.get("what"), "hall")
    return f"Someone robbed the {_name(world, v.get('target'))}'s {what} in the night."


def _healed(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} healed {who(world, v.get('target'), viewer)}{_where(v)}.")


def _hired(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} poisoned {who(world, v.get('target'), viewer)} for "
               f"silver{_where(v)}.")


def _enslaved(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} fed {who(world, v.get('target'), viewer)} a control "
               f"pill{_where(v)}.")


def _freed(world, v, viewer) -> str:
    if v.get("target") is None:
        be = "are" if v.get("actor") == viewer else "is"
        return cap(f"{who(world, v.get('actor'), viewer)} {be} free of a control pill's worms.")
    return cap(f"{who(world, v.get('actor'), viewer)} freed {who(world, v.get('target'), viewer)} from a control "
               "pill's worms.")


def _doctor_seen(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)}, {v.get('title', 'a famous doctor')}, was seen{_where(v)}.")


SPECIAL_PHRASES.update({"doctor_seen": _doctor_seen, "guild_rank": _guild_rank, "robbed_hall": _robbed_hall, "healed": _healed,
                        "poisoned_for_hire": _hired, "enslaved": _enslaved, "freed": _freed})
EXTRA_PHRASES["sold_secret"] = "{actor} sold the secrets of the {target} to its enemies."
EXTRA_PHRASES["stole"] = "{actor} stole from the {target}."


# --- the sect's hall and garden -----------------------------------------------------------------------------------

@outcome("pill_drawn", body_facts=False)
def _drawn(world, event):
    d = event.data
    paid = f" for {d['merit']} merit" if d["merit"] else ""
    return [f"The hall keeper hands you a grade-{d['grade']} {d['effect']} pill{paid}."], {}


@summary("pill_drawn")
def _drawn_line(world, entry, names, place, other):
    return f"Drew a pill from the {_name(world, entry.data['faction'])}'s hall."


@outcome("garden_harvested", body_facts=False)
def _harvested(world, event):
    return [f"You cut a stem of {event.data['herb']} from the sect's garden."], {}


@summary("garden_harvested")
def _harvested_line(world, entry, names, place, other):
    return f"Harvested {entry.data['herb']} from the {_name(world, entry.data['faction'])}'s garden."


@outcome("secret_scroll_given", body_facts=False)
def _given(world, event):
    return ["An elder unlocks a lacquered box and hands you a scroll: the sect's own recipe, not to leave its walls."], {}


@summary("secret_scroll_given")
def _given_line(world, entry, names, place, other):
    return f"Was trusted with a secret recipe of the {_name(world, entry.data['faction'])}."


# --- the Guild and scrolls -----------------------------------------------------------------------------------------

@outcome("guild_joined", body_facts=False)
def _joined(world, event):
    return ["Your name goes into the Guild's register, below ten thousand others."], {}


@summary("guild_joined")
def _joined_line(world, entry, names, place, other):
    return "Joined the Alchemists' Guild."


@outcome("guild_exam", body_facts=False)
def _exam(world, event):
    d = event.data
    if d["passed"]:
        return [f"The examiners weigh your pill and nod: you are {G.title(d['rank'])}."], {}
    return [f"Your pill cracks under the examiners' eyes. The {d['fee']} silver is not returned."], {}


@summary("guild_exam")
def _exam_line(world, entry, names, place, other):
    return f"Passed the Guild's examination for the {G.ORDINALS[entry.data['rank']]} rank." \
        if entry.data["passed"] else "Failed a Guild examination."


@outcome("scroll_bought", body_facts=False)
def _scroll_bought(world, event):
    return [f"The Guild's clerk counts {event.data['price']} silver and hands you a sealed scroll."], {}


@summary("scroll_bought")
def _scroll_bought_line(world, entry, names, place, other):
    return "Bought a recipe scroll from the Guild."


@outcome("scroll_sold", body_facts=False)
def _scroll_sold(world, event):
    return [f"The Guild buys the scroll back for {event.data['price']} silver."], {}


@summary("scroll_sold")
def _scroll_sold_line(world, entry, names, place, other):
    return "Sold a recipe scroll to the Guild."


@outcome("scroll_read", body_facts=False)
def _scroll_read(world, event):
    return [f"You read the scroll twice through, and know the {_name(world, event.data['recipe'])}."], {}


@summary("scroll_read")
def _scroll_read_line(world, entry, names, place, other):
    return f"Learnt the {_name(world, entry.data['recipe'])} from a scroll."


@outcome("recipe_taught", body_facts=False)
def _taught(world, event):
    return [f"{cap(_name(world, event.actors[1]))} writes the recipe out for you, slowly, for {event.data['price']} "
            "silver."], {}


@summary("recipe_taught")
def _taught_line(world, entry, names, place, other):
    return f"Was taught a recipe by {other}."


@outcome("secret_sold", body_facts=False)
def _secret_sold(world, event):
    return [f"The {_name(world, event.data['buyer'])} pays {event.data['price']} silver for the "
            f"{_name(world, event.data['sect'])}'s secret. They will not keep your name out of it."], {}


@summary("secret_sold")
def _secret_sold_line(world, entry, names, place, other):
    return f"Sold a secret of the {_name(world, entry.data['sect'])}."


# --- the clinic and the doctors --------------------------------------------------------------------------------------

@outcome("physician_treated", body_facts=False)
def _treated(world, event):
    return [f"The physician cleans and binds your {event.data['location']}: it will heal three times as fast."], {}


@summary("physician_treated")
def _treated_line(world, entry, names, place, other):
    return f"Had a wound treated in {place}."


@outcome("physician_cured", body_facts=False)
def _cured(world, event):
    return [f"A bitter draught and a night's sweat: the poison is gone, for {event.data['price']} silver."], {}


@summary("physician_cured")
def _cured_line(world, entry, names, place, other):
    return f"Had a poison cured in {place}."


@outcome("body_read", body_facts=False)
def _read(world, event):
    return ["The physician takes your pulse at both wrists and names what is in your blood."], {}


@summary("body_read")
def _read_line(world, entry, names, place, other):
    return "Had a physician read your body."


@outcome("asked_doctor", body_facts=False)
def _asked(world, event):
    d = event.data
    from systems.physic import doctor_spec
    spec = doctor_spec(world, tuple(d["block"]))
    return [f"The physician lowers their voice: {spec['name']}, {spec['title']}, was last seen in {d['town']}."], {}


@summary("asked_doctor")
def _asked_line(world, entry, names, place, other):
    return f"Heard where a famous doctor was last seen: {entry.data['town']}."


@outcome("go_played", body_facts=False)
def _go(world, event):
    if event.data["won"]:
        return ["You win by half a stone. The doctor laughs and says they will treat you."], {}
    return ["The doctor's stones close around yours. \"Come back when you can see further,\" they say."], {}


@summary("go_played")
def _go_line(world, entry, names, place, other):
    return f"{'Beat' if entry.data['won'] else 'Lost to'} {other} at go."


@outcome("doctor_cured", body_facts=False)
def _doctor_cured(world, event):
    what = {"poison": "every poison in you", "meridian": "your broken meridians", "injury": "an old, deep wound",
            "control": "the worms of the control pill"}.get(event.data["what"], "what ailed you")
    return [f"{cap(_name(world, event.actors[1]))} works for a day and a night, and {what} is gone."], {}


@summary("doctor_cured")
def _doctor_cured_line(world, entry, names, place, other):
    return f"Was cured of {entry.data['what']} by {other}."


# --- by night -------------------------------------------------------------------------------------------------

@outcome("waited_for_night", body_facts=False)
def _waited(world, event):
    return ["You wait out the light in a quiet corner until the lanterns go out."], {}


@summary("waited_for_night")
def _waited_line(world, entry, names, place, other):
    return f"Waited for nightfall in {place}."


@outcome("hall_surveyed", body_facts=False)
def _surveyed(world, event):
    return [f"You go over the {_name(world, event.data['faction'])}'s wall and look, and touch nothing."], {}


@summary("hall_surveyed")
def _surveyed_line(world, entry, names, place, other):
    return f"Looked over the {_name(world, entry.data['faction'])}'s hall by night."


@outcome("hall_theft", body_facts=False)
def _theft(world, event):
    d = event.data
    if d["caught"]:
        return [f"A lantern swings round: you are seen, and flee with nothing. The {_name(world, d['faction'])} "
                "will know your face."], {}
    return [f"In and out unseen, with {len(d['loot'])} thing(s) of the {_name(world, d['faction'])}'s."], {}


@summary("hall_theft")
def _theft_line(world, entry, names, place, other):
    return f"{'Was caught stealing' if entry.data['caught'] else 'Stole'} from the " \
        f"{_name(world, entry.data['faction'])}."


# --- healing and poisoning ---------------------------------------------------------------------------------------

@outcome("healed", body_facts=False)
def _healed_outcome(world, event):
    name = cap(_name(world, event.actors[1]))
    if event.data["success"]:
        return [f"{name}'s colour comes back. They thank you, and do not forget it."], {}
    return [f"Your herbs do nothing for {name}."], {}


@summary("healed")
def _healed_line(world, entry, names, place, other):
    return f"Treated {other}." if entry.data["success"] else f"Failed to treat {other}."


@outcome("patient_brought", body_facts=False)
def _patient(world, event):
    return ["Word has gone round that you heal: someone is carried to you, grey-faced."], {}


@summary("patient_brought")
def _patient_line(world, entry, names, place, other):
    return f"Was brought someone sick in {place}."


@outcome("contract_taken", body_facts=False)
def _contract(world, event):
    return [f"You take {event.data['silver']} silver's worth of work: {_name(world, event.actors[2])} is to die."], {}


@summary("contract_taken")
def _contract_line(world, entry, names, place, other):
    return f"Agreed to poison {names[2] if len(names) > 2 else 'someone'} for {other}."


@outcome("contract_poisoned", body_facts=False)
def _poisoned(world, event):
    return [f"The powder goes into {_name(world, event.actors[1])}'s cup, and you are gone before they drink."], {}


@summary("contract_poisoned")
def _poisoned_line(world, entry, names, place, other):
    return f"Poisoned {other} for silver."


@outcome("contract_paid", body_facts=False)
def _paid(world, event):
    return [f"{cap(_name(world, event.actors[1]))} pays {event.data['silver']} silver and does not meet your eye."], {}


@summary("contract_paid")
def _paid_line(world, entry, names, place, other):
    return f"Was paid for a poisoning by {other}."


@outcome("contract_void", body_facts=False)
def _void(world, event):
    return ["The poisoning you were paid for will not happen now; the offer is void."], {}


@summary("contract_void")
def _void_line(world, entry, names, place, other):
    return "A contract to poison came to nothing."


@outcome("npc_pill_bought", body_facts=False)
def _pill_bought(world, event):
    return [f"You buy a grade-{event.data['grade']} pill for {event.data['price']} silver."], {}


@summary("npc_pill_bought")
def _pill_bought_line(world, entry, names, place, other):
    return f"Bought a pill from {other}."


# --- the worms ------------------------------------------------------------------------------------------------

@outcome("service_rendered", body_facts=False)
def _served(world, event):
    return [f"Word comes from {_name(world, event.actors[1])}: the service is done, and a month's antidote is "
            "left where you will find it."], {}


@summary("service_rendered")
def _served_line(world, entry, names, place, other):
    return f"Served {other} for a month's antidote."


@outcome("worms_forced", body_facts=False)
def _forced(world, event):
    if event.data["cleared"]:
        return ["You drive your qi through the belly and the worms die in a black flux. You are free."], {}
    return ["The worms twist away from your qi. They are still there."], {}


@summary("worms_forced")
def _forced_line(world, entry, names, place, other):
    return "Forced out a control pill's worms." if entry.data["cleared"] else "Tried to force out the worms."


@outcome("control_forced", body_facts=False)
def _control_forced(world, event):
    return [f"You force the pill down {_name(world, event.actors[1])}'s throat. From now on they need you "
            "every month."], {}


@summary("control_forced")
def _control_forced_line(world, entry, names, place, other):
    return f"Fed {other} a control pill."


@outcome("servant_fed", body_facts=False)
def _servant_fed(world, event):
    return [f"The month's antidote goes to {_name(world, event.actors[1])}."], {}


@summary("servant_fed")
def _servant_fed_line(world, entry, names, place, other):
    return f"Sent {other} the antidote."


@outcome("worms_killed", body_facts=False)
def _worms_killed(world, event):
    return [f"Your antidote kills the worms in {_name(world, event.actors[1])}. They weep."], {}


@summary("worms_killed")
def _worms_killed_line(world, entry, names, place, other):
    return f"Freed {other} from a control pill."


@outcome("control_freed", body_facts=False)
def _control_freed(world, event):
    return ["The worms are dead; no one's antidote is needed now."], {}


@summary("control_freed")
def _control_freed_line(world, entry, names, place, other):
    return "Was freed of a control pill."
