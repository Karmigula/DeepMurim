"""What the player is told of herbs, the furnace, pills and poison (phase 5b spec 5)."""

from narrate.outcomes import outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

HINT_WORDS = {"element": "the herbs lean to the wrong element", "polarity": "the balance of yin and yang is off",
              "potency": "the brew is too weak", "toxicity": "the brew is too toxic"}


def _poison_body(world, v, viewer) -> str:
    return f"{who(world, v.get('actor'), viewer).capitalize()} has a body of poison: their very blood is venom."


SPECIAL_PHRASES["poison_body"] = _poison_body


@outcome("herb_tasted", body_facts=False)
def _tasted(world, event):
    d = event.data
    line = f"You chew a little of the {d['herb']} and learn its nature."
    return [line + (" Your tongue goes numb: poison." if d["toxicity"] >= 3 else "")], {}


@summary("herb_tasted")
def _tasted_line(world, entry, names, place, other):
    return f"Tasted {entry.data['herb']}."


@outcome("herbs_gathered", body_facts=False)
def _gathered(world, event):
    found = event.data["found"]
    if not found:
        return ["Half a day in the hills and hollows turns up nothing worth the knife."], {}
    names = ", ".join(f["herb"] for f in found)
    return [f"Half a day's searching: {names}." + (" Something large is watching you." if event.data["guarded"] else "")], {}


@summary("herbs_gathered")
def _gathered_line(world, entry, names, place, other):
    return f"Gathered herbs near {place}." if entry.data["found"] else f"Searched for herbs near {place}."


@outcome("herb_bought", body_facts=False)
def _bought(world, event):
    return [f"You pay {event.data['price']} silver for the {event.data['herb']}."], {}


@summary("herb_bought")
def _bought_line(world, entry, names, place, other):
    return f"Bought {entry.data['herb']} at {place}."


@outcome("furnace_bought", body_facts=False)
def _furnace(world, event):
    return [f"A bronze furnace is yours, for {event.data['price']} silver."], {}


@summary("furnace_bought")
def _furnace_line(world, entry, names, place, other):
    return "Bought a furnace."


@outcome("experimented", body_facts=False)
def _experimented(world, event):
    d = event.data
    if d["result"] == "discovered":
        return ["The fumes clear on a single perfect pill. You have found a recipe."], {}
    if d["result"] == "hint":
        return [f"Close, but no: {HINT_WORDS[d['missed']]}."], {}
    return ["A black sludge." + (" Its fumes sting your eyes and lungs." if d["fumes"] else "")], {}


@summary("experimented")
def _experimented_line(world, entry, names, place, other):
    return {"discovered": "Discovered a recipe.", "hint": "Came close to a recipe."}.get(entry.data["result"],
                                                                                        "Burnt a batch of herbs.")


@outcome("refined", body_facts=False)
def _refined(world, event):
    d = event.data
    if d["success"]:
        return [f"{d['count']} pill(s) of grade {d['grade']} cool in the furnace."], {}
    return ["The furnace cracks and burns you." if d["cracked"] else "Only ash comes out."], {}


@summary("refined")
def _refined_line(world, entry, names, place, other):
    return f"Refined {entry.data['count']} pill(s)." if entry.data["success"] else "A refining failed."


@outcome("pill_taken", body_facts=False)
def _taken(world, event):
    return [f"You swallow the pill; its {event.data['effect']} works through you."], {}


@summary("pill_taken")
def _taken_line(world, entry, names, place, other):
    return f"Swallowed a {entry.data['effect']} pill."


@outcome("blade_coated", body_facts=False)
def _coated(world, event):
    return ["You work the venom into the edge. Three wounds' worth."], {}


@summary("blade_coated")
def _coated_line(world, entry, names, place, other):
    return "Coated a blade with venom."


@outcome("acupoints_sealed", body_facts=False)
def _sealed(world, event):
    return ["Two fingers, three points: the poison stops where it is, for now."], {}


@summary("acupoints_sealed")
def _sealed_line(world, entry, names, place, other):
    return "Sealed acupoints against a poison."


@outcome("poison_forced", body_facts=False)
def _forced(world, event):
    if event.data["cleared"]:
        return ["Black blood beads at your fingertips and the poison is gone."], {}
    return ["You drive some of it out; the rest holds on."], {}


@summary("poison_forced")
def _forced_line(world, entry, names, place, other):
    return "Forced a poison out."


@outcome("poison_art_bought", body_facts=False)
def _art(world, event):
    return ["A thin manual, stained, smelling of bitter almonds, changes hands."], {}


@summary("poison_art_bought")
def _art_line(world, entry, names, place, other):
    return "Bought a poison art."


@outcome("beast_butchered", body_facts=False)
def _butchered(world, event):
    if event.data["part"] == "blood":
        return ["The blood is hot and bitter. Your body will know that venom again."], {}
    return ["The core is the size of a fist and burns going down."], {}


@summary("beast_butchered")
def _butchered_line(world, entry, names, place, other):
    return f"Took the {entry.data['part']} of a venomous beast."


@outcome("bathed", body_facts=False)
def _bathed(world, event):
    d = event.data
    line = f"A day in the scalding herbs. Your {d['stat']} is the better for it."
    if d["pain"]:
        line += " It hurt more than it should have."
    if d["awaken"]:
        line += f" Something wakes in your bones: a {d['awaken']}."
    return [line], {}


@summary("bathed")
def _bathed_line(world, entry, names, place, other):
    return f"Took a tempering bath for {entry.data['stat']}."
