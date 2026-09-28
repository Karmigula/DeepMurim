"""What the player is told of karma: fated meetings, a fortune read, the temple, misfortune, and a smith's estate
paying back (phase 5f spec 7)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

import systems.gear as gear
import systems.karma as K
import systems.threads as TH

THREAD_WORDS = {"spared": "you spared them", "healed": "you healed them", "freed": "you freed them from the worms",
                "robbed": "you robbed them", "crippled": "you crippled them", "bereaved": "you killed their kin",
                "accused": "you falsely accused them"}
OWED_WORDS = {"spared": "You spared me", "healed": "You healed me", "freed": "You freed me from the worms"}


def _name(world, entity_id) -> str:
    entity = world.entity(entity_id) if isinstance(entity_id, int) else None
    return entity.name if entity else "someone"


@outcome("fated_repaid", body_facts=False)
def _repaid(world, event):
    d = event.data
    return [f"{cap(_name(world, event.actors[1]))} is on the road, and knows you. \"{OWED_WORDS[d['kind']]}. "
            f"I have not forgotten.\" They press {d['silver']} silver on you."], {}


@summary("fated_repaid")
def _repaid_line(world, entry, names, place, other):
    return f"Was repaid by {other} on the road."


@outcome("fortune_read", body_facts=False)
def _fortune(world, event):
    me = event.actors[0]
    teller = _name(world, event.actors[1])
    lines = [f"{cap(teller)} spreads the sticks and reads them twice. \"{cap(K.words(event.data['balance']))}.\""]
    threads = sorted(TH.threads(world, me), key=lambda t: (-t["weight"], t["since"]))[:3]
    for t in threads:
        lines.append(f"\"A thread runs to {_name(world, t['whom'])}: {THREAD_WORDS[t['kind']]}.\"")
    if not threads:
        lines.append("\"No thread of fate pulls hard at you yet.\"")
    return lines, {}


@summary("fortune_read")
def _fortune_line(world, entry, names, place, other):
    return f"Had {other} read your fortune."


@outcome("alms_given", body_facts=False)
def _alms(world, event):
    return [f"You give {event.data['silver']} silver in alms. The monk bows without a word."], {}


@summary("alms_given")
def _alms_line(world, entry, names, place, other):
    return f"Gave {entry.data['silver']} silver in alms at {place}."


@outcome("incense_burned", body_facts=False)
def _incense(world, event):
    return ["You light a stick of incense and watch the smoke climb."], {}


@summary("incense_burned")
def _incense_line(world, entry, names, place, other):
    return f"Burned incense at {place}."


@outcome("misfortune", body_facts=False)
def _misfortune(world, event):
    d = event.data
    if d["what"] == "purse":
        return [f"Your purse is lighter by {d['silver']} silver, and you never felt the hand."], {}
    return ["A stair gives way under you. Your leg takes the fall."], {}


@summary("misfortune")
def _misfortune_line(world, entry, names, place, other):
    return "Lost silver to a cutpurse." if entry.data["what"] == "purse" else "Hurt in a fall."


@outcome("commission_refunded", body_facts=False)
def _refunded(world, event):
    d = event.data
    what = gear.ARMOUR_WORDS.get(d["form"], d["form"])
    return [f"{cap(_name(world, event.actors[1]))} died before the {what} was forged; their estate returns your "
            f"{d['silver']} silver."], {}


@summary("commission_refunded")
def _refunded_line(world, entry, names, place, other):
    return f"Had {entry.data['silver']} silver back from {other}'s estate."


def _struck(world, v, viewer) -> str:
    return cap(f"{who(world, v.get('actor'), viewer)} was struck down by heaven in {v.get('place') or 'a town'}.")


SPECIAL_PHRASES["struck_down"] = _struck
