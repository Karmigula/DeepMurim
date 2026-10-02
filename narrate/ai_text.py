"""What the player is told of what the model's accepted proposals did (phase 6c, spec 14.6): the engine's own
short line for each change, shown under the model's paragraph in assist mode, and the journal's lines. A deed is a
rumour like any other."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

from ai.deeds import TONES


def _name(world, entity_id) -> str:
    entity = world.entity(entity_id) if isinstance(entity_id, int) else None
    return entity.name if entity else "someone"


# --- rumours ---------------------------------------------------------------------------------------------------

def _deed(world, v, viewer) -> str:
    teller = who(world, v.get("actor"), viewer)
    return cap(f"{teller}: {v.get('text', 'a deed').rstrip('.')}" + (f", in {v['place']}." if v.get("place") else "."))


for _tone in TONES:
    SPECIAL_PHRASES[f"deed_{_tone}"] = _deed


# --- outcomes --------------------------------------------------------------------------------------------------

@outcome("ai_paid", body_facts=False)
def _paid(world, event):
    return [f"{cap(_name(world, event.actors[1]))} takes {event.data['amount']} silver from you."], {}


@summary("ai_paid")
def _paid_line(world, entry, names, place, other):
    return f"Paid {entry.data['amount']} silver to {_name(world, entry.actors[1])} in {place}."


@outcome("ai_gave", body_facts=False)
def _gave(world, event):
    return [f"{cap(_name(world, event.actors[1]))} now holds {_name(world, event.data['item'])}."], {}


@summary("ai_gave")
def _gave_line(world, entry, names, place, other):
    return f"Gave {_name(world, entry.data['item'])} to {_name(world, entry.actors[1])} in {place}."


FELT = {"grateful": "is grateful", "amused": "is amused", "respect": "respects you", "annoyed": "is annoyed",
        "contempt": "holds you in contempt", "fear": "fears you"}


@outcome("ai_felt", body_facts=False)
def _felt(world, event):
    return [f"{cap(_name(world, event.actors[1]))} {FELT.get(event.data['feeling'], 'remembers it')}."], {}


@summary("ai_felt")
def _felt_line(world, entry, names, place, other):
    return f"Left {_name(world, entry.actors[1])} {entry.data['feeling']} in {place}."


@outcome("ai_deed", body_facts=False)
def _deed_done(world, event):
    return [f"It may be told: {event.data['text'].rstrip('.')}."], {}


@summary("ai_deed")
def _deed_line(world, entry, names, place, other):
    return f"{entry.data['text'].rstrip('.')} ({place})."


@outcome("ai_told", body_facts=False)
def _told(world, event):
    return [f"You learn what {_name(world, event.actors[0])} holds to be so."], {}


@summary("ai_told")
def _told_line(world, entry, names, place, other):
    return f"Heard something from {_name(world, entry.actors[0])} in {place}."


@outcome("ai_arrived", body_facts=False)
def _arrived(world, event):
    trade = event.data["occupation"]
    return [f"{'An' if trade[:1] in 'aeiou' else 'A'} {trade} is here now."], {}


@summary("ai_arrived")
def _arrived_line(world, entry, names, place, other):
    return f"Met a {entry.data['occupation']} in {place}."


@outcome("ai_hurt", body_facts=False)
def _hurt(world, event):
    d = event.data
    done = {"bruise": "bruised", "cut": "cut", "burn": "burned", "fracture": "fractured"}.get(d["kind"], "hurt")
    return [f"Your {d['location']} is {done}."], {}


@summary("ai_hurt")
def _hurt_line(world, entry, names, place, other):
    return f"Hurt your {entry.data['location']} in {place}."


@outcome("ai_waited", body_facts=False)
def _waited(world, event):
    n = event.data["watches"]
    return ["A watch passes." if n == 1 else f"{n} watches pass."], {}


@outcome("talked", body_facts=False)
def _talked(world, event):
    return [], {}  # the answer itself is the turn's text


@summary("talked")
def _talked_line(world, entry, names, place, other):
    return f"Talked with {_name(world, entry.actors[1])} in {place}: {entry.data['summary'].rstrip('.')}."


@summary("ai_waited")
def _waited_line(world, entry, names, place, other):
    return f"Spent {entry.data['watches']} watch{'es' if entry.data['watches'] != 1 else ''} in {place}."
