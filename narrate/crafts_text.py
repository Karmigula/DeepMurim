"""What the player is told of the forge, formations, commissions and the Meet (phase 5d spec 7)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

import systems.formations as FM
import systems.gear as gear


def _name(world, entity_id) -> str:
    entity = world.entity(entity_id) if isinstance(entity_id, int) else None
    return entity.name if entity else "someone"


def _legend(world, v, viewer) -> str:
    """A smith's own legend is told whole; 5a's tell of sects the hearer may not know, so they are not quoted."""
    legend = v.get("legend") or ""
    if legend.startswith("forged by "):
        return cap(f"{_name(world, v.get('actor'))}: {legend}.")
    return cap(f"{_name(world, v.get('actor'))} is a blade of legend.")


def _meet(world, v, viewer) -> str:
    who_won = who(world, v.get("actor"), viewer) if v.get("actor") is not None else v.get("name", "someone")
    craft = "the anvil" if v.get("craft") == "forging" else "the furnace"
    return cap(f"{who_won} won {craft} at the Meet of Hammer and Furnace in {v.get('place') or 'a city'}.")


SPECIAL_PHRASES.setdefault("blade_legend", _legend)
SPECIAL_PHRASES["meet_won"] = _meet


@outcome("material_bought", body_facts=False)
def _bought(world, event):
    return [f"You pay {event.data['price']} silver for the {event.data['material']}."], {}


@summary("material_bought")
def _bought_line(world, entry, names, place, other):
    return f"Bought {entry.data['material']} at {place}."


@outcome("beast_parts_taken", body_facts=False)
def _parts(world, event):
    what = "bones" if event.data["part"] == "bone" else "core"
    return [f"You take {_name(world, event.actors[1])}'s {what}. A smith will want them."], {}


@summary("beast_parts_taken")
def _parts_line(world, entry, names, place, other):
    return f"Took the {entry.data['part']} of {other}."


@outcome("forge_bought", body_facts=False)
def _forge(world, event):
    return [f"An anvil and a travelling forge are yours, for {event.data['price']} silver."], {}


@summary("forge_bought")
def _forge_line(world, entry, names, place, other):
    return "Bought an anvil and a forge."


@outcome("forged", body_facts=False)
def _forged(world, event):
    d = event.data
    what = d["form"] if d["slot"] == "weapon" else gear.ARMOUR_WORDS[d["form"]]
    if d["success"]:
        return [f"The quench hisses: a {gear.GRADE_WORDS[d['grade']]} {what}, of your own forging."], {}
    return ["The metal cracks in the quench" + (" and the fire bites your arm." if d["burned"] else ".")], {}


@summary("forged")
def _forged_line(world, entry, names, place, other):
    return f"Forged a {entry.data['form']}." if entry.data["success"] else "A forging failed."


@outcome("gear_refined", body_facts=False)
def _refined(world, event):
    d = event.data
    if d["success"]:
        return [f"{cap(_name(world, d['item']))} comes out of the fire a grade finer."], {}
    return [f"{cap(_name(world, d['item']))} cracks under the hammer." if d["cracked"] else "The refining fails."], {}


@summary("gear_refined")
def _refined_line(world, entry, names, place, other):
    return "Refined a piece a grade." if entry.data["success"] else "A refining failed."


@outcome("masterwork_named", body_facts=False)
def _named(world, event):
    return [f"You cut the name into the tang: {event.data['name']}. It will be known."], {}


@summary("masterwork_named")
def _named_line(world, entry, names, place, other):
    return f"Named a masterwork {entry.data['name']}."


@outcome("formation_studied", body_facts=False)
def _studied(world, event):
    return [f"You work through the diagrams until {FM.PATTERNS[event.data['pattern']]['name']} is yours."], {}


@summary("formation_studied")
def _studied_line(world, entry, names, place, other):
    return f"Learnt {FM.PATTERNS[entry.data['pattern']]['name']}."


@outcome("formation_laid", body_facts=False)
def _laid(world, event):
    name = FM.PATTERNS[event.data["pattern"]]["name"]
    if event.data["success"]:
        return [f"The last flag goes in and {name} closes around the place."], {}
    return [f"A flag is out of true: {name} never closes, and the flags are spent."], {}


@summary("formation_laid")
def _laid_line(world, entry, names, place, other):
    name = FM.PATTERNS[entry.data["pattern"]]["name"]
    return f"Laid {name} in {place}." if entry.data["success"] else f"Failed to lay {name}."


@outcome("manual_bought", body_facts=False)
def _manual(world, event):
    return [f"{cap(_name(world, event.actors[1]))} sells you a manual of "
            f"{FM.PATTERNS[event.data['pattern']]['name']} for {event.data['price']} silver."], {}


@summary("manual_bought")
def _manual_line(world, entry, names, place, other):
    return f"Bought a formation manual from {other}."


@outcome("flags_bought", body_facts=False)
def _flags(world, event):
    return [f"{event.data['count']} formation flags, for {event.data['price']} silver."], {}


@summary("flags_bought")
def _flags_line(world, entry, names, place, other):
    return f"Bought formation flags from {other}."


@outcome("formation_commissioned", body_facts=False)
def _commissioned(world, event):
    return [f"{cap(_name(world, event.actors[1]))} walks the ground and lays "
            f"{FM.PATTERNS[event.data['pattern']]['name']} for you."], {}


@summary("formation_commissioned")
def _commissioned_line(world, entry, names, place, other):
    return f"Had {other} lay a formation in {place}."


@outcome("forge_commissioned", body_facts=False)
def _forge_commissioned(world, event):
    return [f"{cap(_name(world, event.actors[1]))} takes {event.data['price']} silver: come back in ten days."], {}


@summary("forge_commissioned")
def _forge_commissioned_line(world, entry, names, place, other):
    return f"Commissioned {other} to forge a {entry.data['form']}."


@outcome("commission_collected", body_facts=False)
def _collected(world, event):
    return [f"{cap(_name(world, event.actors[1]))} hands over the {event.data['form']}, still warm."], {}


@summary("commission_collected")
def _collected_line(world, entry, names, place, other):
    return f"Collected a {entry.data['form']} from {other}."


@outcome("meet_entered", body_facts=False)
def _entered(world, event):
    return [f"The judges look it over and mark {event.data['score']}."], {}


@summary("meet_entered")
def _entered_line(world, entry, names, place, other):
    return f"Showed a piece at the Meet of Hammer and Furnace in {place}."


@outcome("meet_decided", body_facts=False)
def _decided(world, event):
    return [f"The Meet is over: {event.data['name']} wins at "
            f"{'the anvil' if event.data['craft'] == 'forging' else 'the furnace'}."], {}


@summary("meet_decided")
def _decided_line(world, entry, names, place, other):
    return f"Won at the Meet of Hammer and Furnace, year {entry.data['year']}."
