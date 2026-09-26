"""What the player is told of weapons and armour (phase 5a spec 3, 5): their tales and the deeds done with them."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

DEED_WORDS = {"killed": "slew {whom}", "bested": "bested {whom}", "won_tournament": "won a tournament"}


def deed_words(world, deed: str, whom, viewer: int) -> str:
    return DEED_WORDS.get(deed, "was wielded by {wielder}").format(whom=who(world, whom, viewer), wielder="someone")


def _wielded_in(world, v, viewer) -> str:
    blade = world.entity(v.get("actor"))
    name = blade.name if blade is not None else "a famous blade"
    text = f"{name}, in the hand of {who(world, v.get('wielder'), viewer)}, {deed_words(world, v.get('deed'), v.get('target'), viewer)}"
    return cap(text + (f" in {v['place']}." if v.get("place") else "."))


def _returned(world, v, viewer) -> str:
    faction = world.entity(v.get("target")) if isinstance(v.get("target"), int) else None
    return cap(f"{who(world, v.get('actor'), viewer)} gave the {faction.name if faction else 'sect'} back what was theirs.")


def _kept(world, v, viewer) -> str:
    faction = world.entity(v.get("target")) if isinstance(v.get("target"), int) else None
    return cap(f"{who(world, v.get('actor'), viewer)} keeps a blade the {faction.name if faction else 'sect'} calls its own.")


SPECIAL_PHRASES["wielded_in"] = _wielded_in
SPECIAL_PHRASES["returned_gear"] = _returned
SPECIAL_PHRASES["kept_gear"] = _kept


@outcome("blade_known", body_facts=False)
def _blade_known(world, event):
    item = world.entity(event.data["item"])
    return [f"{who(world, event.actors[0], event.actors[1])} stares at {item.name}. They know whose blood is on it."], {}


@summary("blade_known")
def _blade_known_line(world, entry, names, place, other):
    return f"Was known by the blade you carry, at {place}."


@outcome("blade_demanded", body_facts=False)
def _demanded(world, event):
    item = world.entity(event.data["item"])
    if event.data["handed"]:
        return [f"You hand over {item.name}. It goes back where they say it belongs."], {}
    return [f"You keep {item.name}. They will remember that you did."], {}


@summary("blade_demanded")
def _demanded_line(world, entry, names, place, other):
    return "Gave back a blade a sect called its own." if entry.data["handed"] else "Kept a blade a sect called its own."
