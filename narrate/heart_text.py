"""What the player is told of their heart: trials, epiphanies, oaths, graves and amends, a blade's spirit, and the
masters who go mad (phase 5e spec 8)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

from engine.heart_page import dao_name, dao_words, demon_words, oath_words


def _name(world, entity_id) -> str:
    entity = world.entity(entity_id) if isinstance(entity_id, int) else None
    return entity.name if entity else "someone"


def _demon(world, data) -> str:
    return demon_words(world, {"kind": data["kind"], "whom": data["whom"]})


# --- the heart trial ---------------------------------------------------------------------------------------------

@outcome("heart_trial", body_facts=False)
def _trial(world, event):
    d = event.data
    demon = _demon(world, d)
    if d["choice"] == "turn_back":
        return [f"You turn back from the gate. {cap(demon)} waits."], {}
    if d["choice"] == "bury":
        return [f"You push {demon} down, and step through with it still inside you."], {}
    if d["success"]:
        return [f"You look {demon} in the face, and it lets you go."], {}
    return [f"{cap(demon)} will not be faced: your qi turns on itself."], {}


@summary("heart_trial")
def _trial_line(world, entry, names, place, other):
    d = entry.data
    words = {"turn_back": "Turned back from", "bury": "Buried", "face": "Faced" if d.get("success") else "Was beaten by"}
    return f"{words[d['choice']]} {_demon(world, d)} at a breakthrough."


@outcome("demon_stirred", body_facts=False)
def _stirred(world, event):
    return [f"In the stillness, {_demon(world, event.data)} rises. Your qi stumbles."], {}


@summary("demon_stirred")
def _stirred_line(world, entry, names, place, other):
    return f"Troubled by {_demon(world, entry.data)} in meditation."


@outcome("paid_respects", body_facts=False)
def _respects(world, event):
    return [f"You kneel at {_name(world, event.actors[1])}'s grave. The grief loosens its hold."], {}


@summary("paid_respects")
def _respects_line(world, entry, names, place, other):
    return f"Paid respects at {other}'s grave."


@outcome("amends_made", body_facts=False)
def _amends(world, event):
    return [f"You press {event.data['silver']} silver on {_name(world, event.actors[1])}. "
            "It undoes nothing, but it is something."], {}


@summary("amends_made")
def _amends_line(world, entry, names, place, other):
    return f"Made amends to {other}."


# --- epiphanies ----------------------------------------------------------------------------------------------------

@outcome("epiphany", body_facts=False)
def _epiphany(world, event):
    d = event.data
    lines = [f"Understanding opens like a door: {dao_name(d['dao'])}, {dao_words(d['after'])}."]
    if d["origin"]:
        lines.append("Everything you learnt falls away, and what is left is simple. You have returned to the origin.")
    return lines, {}


@summary("epiphany")
def _epiphany_line(world, entry, names, place, other):
    return f"Glimpsed more of {dao_name(entry.data['dao'])}."


# --- oaths ------------------------------------------------------------------------------------------------------------

def _oath(world, data) -> str:
    return oath_words(world, {"kind": data["kind"], "whom": data["whom"]})


@outcome("oath_sworn", body_facts=False)
def _sworn(world, event):
    return [f"You swear on your dao heart: {_oath(world, event.data)}."], {}


@summary("oath_sworn")
def _sworn_line(world, entry, names, place, other):
    return f"Swore on the dao heart: {_oath(world, entry.data)}."


@outcome("oath_kept", body_facts=False)
def _kept(world, event):
    return [f"An oath is kept: {_oath(world, event.data)}. Your heart stands straighter."], {}


@summary("oath_kept")
def _kept_line(world, entry, names, place, other):
    return f"Kept an oath: {_oath(world, entry.data)}."


@outcome("oath_released", body_facts=False)
def _released(world, event):
    return [f"{cap(_name(world, event.actors[1]))} is gone, and no hand did it: your oath is released."], {}


@summary("oath_released")
def _released_line(world, entry, names, place, other):
    return f"Released from an oath: {_oath(world, entry.data)}."


@outcome("oath_broken", body_facts=False)
def _broken(world, event):
    return [f"An oath is broken: {_oath(world, event.data)}. Something in your heart cracks."], {}


@summary("oath_broken")
def _broken_line(world, entry, names, place, other):
    return f"Broke an oath: {_oath(world, entry.data)}."


# --- blades ---------------------------------------------------------------------------------------------------------

@outcome("spirit_woke", body_facts=False)
def _woke(world, event):
    return [f"{cap(_name(world, event.actors[1]))} feels heavier in your hand."], {}


@summary("spirit_woke")
def _woke_line(world, entry, names, place, other):
    return f"Something stirred in {_name(world, entry.actors[1])}."


@outcome("spirit_felt", body_facts=False)
def _felt(world, event):
    item = _name(world, event.actors[1])
    if event.data["cursed"]:
        return [f"A season in your hand, and you know it: {item} is cursed, and it thirsts."], {}
    return [f"A season in your hand, and you know it: {item} holds a {event.data['nature']} spirit."], {}


@summary("spirit_felt")
def _felt_line(world, entry, names, place, other):
    return f"Came to know the spirit in {_name(world, entry.actors[1])}."


@outcome("blade_whispered", body_facts=False)
def _whispered(world, event):
    return [f"{cap(_name(world, event.actors[1]))} whispers of blood. Your heart wavers."], {}


@summary("blade_whispered")
def _whispered_line(world, entry, names, place, other):
    return f"{cap(_name(world, entry.actors[1]))} hungered."


@outcome("blade_read", body_facts=False)
def _read(world, event):
    smith, d = _name(world, event.actors[1]), event.data
    if d["nature"] is None:
        verdict = "Good steel. Nothing sleeps in it."
    elif d["cursed"]:
        verdict = "This one is cursed. It wants blood, and it will ask you for it."
    else:
        verdict = f"There is a spirit in this, and a {d['nature']} one."
    return [f"{smith} turns the blade in the light. \"{verdict}\""], {}


@summary("blade_read")
def _read_line(world, entry, names, place, other):
    return f"Had {other} read {_name(world, entry.actors[2])}."


# --- the world ------------------------------------------------------------------------------------------------------

@summary("heart_madness")
def _mad_line(world, entry, names, place, other):
    return f"{_name(world, entry.actors[0])} went mad with their demons."


@summary("madness_passed")
def _sane_line(world, entry, names, place, other):
    return f"{_name(world, entry.actors[0])} came back to themselves."


def _went_mad(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} went mad with their demons in {v.get('place') or 'a town'}.")


def _oath_news(world, v, viewer) -> str:
    person, target = who(world, v.get("actor"), viewer), v.get("target")
    what = {"vengeance": f"to take vengeance on {who(world, target, viewer)}",
            "protection": f"to protect {who(world, target, viewer)}",
            "abstinence": "to kill no one"}.get(v.get("oath"), "an oath")
    verb = {"oath_sworn": "swore on their dao heart", "oath_kept": "kept an oath sworn on their dao heart",
            "oath_broken": "broke an oath sworn on their dao heart"}[v.get("predicate")]
    return cap(f"{person} {verb} {what}.")


SPECIAL_PHRASES["went_mad"] = _went_mad
for _kind in ("oath_sworn", "oath_kept", "oath_broken"):
    SPECIAL_PHRASES[_kind] = _oath_news
