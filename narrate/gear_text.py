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


HOW_LINES = {"taken": "You take {item}.", "won": "{item} is yours by the fight.", "found": "You take up {item}.",
             "given": "{item} changes hands.", "inherited": "{item} passes to its heir.", "sold": "You sell {item}.",
             "returned": "You give {item} back to the armoury.", "lost": "{item} is left where it fell."}


def gear_facts(world, town: int, player: int) -> list[str]:
    """The famous blades the player knows by their tales, carried by people here (spec 5)."""
    from systems.provenance import known_blades
    from world.gen.materialize import people_at
    present = [p.id for p in people_at(world, town, exclude=player)]
    return [f"{world.entity(p).name} carries {world.entity(i).name}." for p, i in known_blades(world, player, present)]


@outcome("gear_taken_up", body_facts=False)
def _taken_up(world, event):
    item = world.entity(event.data["item"])
    return [f"You {'take up' if item.data['slot'] == 'weapon' else 'put on'} {item.name}."], {}


@summary("gear_taken_up")
def _taken_up_line(world, entry, names, place, other):
    return f"Took up {world.entity(entry.data['item']).name}."


@outcome("gear_put_away", body_facts=False)
def _put_away(world, event):
    return [f"You put away {world.entity(event.data['item']).name}."], {}


@summary("gear_put_away")
def _put_away_line(world, entry, names, place, other):
    return f"Put away {world.entity(entry.data['item']).name}."


LOST_LINES = {"taken": "{item} is taken from you.", "won": "{item} is taken from you by the fight.",
              "given": "{item} leaves your hands.", "sold": "You sell {item}.",
              "returned": "You give {item} back to the armoury.", "lost": "{item} is left where it fell."}


def _pass_words(world, data, how_lines=None) -> str:
    """The line from the player's side: what they gained, or what was taken from them (5a review)."""
    player = world.get_meta("player_id")
    lines = LOST_LINES if data.get("giver") == player and data.get("taker") != player else HOW_LINES
    return lines.get(data["how"], "{item} changes hands.").format(item=world.entity(data["item"]).name)


@outcome("gear_passed", body_facts=False)
def _passed(world, event):
    return [_pass_words(world, event.data)], {}


@summary("gear_passed")
def _passed_line(world, entry, names, place, other):
    return _pass_words(world, entry.data)


@outcome("gear_bought", body_facts=False)
def _bought(world, event):
    from systems.gear import gear_name
    d = event.data
    return [f"You pay {d['price']} silver for {gear_name(d['slot'], d['form'], d['grade'])}."], {}


@summary("gear_bought")
def _bought_line(world, entry, names, place, other):
    return f"Bought gear at {place} for {entry.data['price']} silver."


@outcome("gear_sold", body_facts=False)
def _sold(world, event):
    return [f"{event.data['price']} silver changes hands."], {}


@summary("gear_sold")
def _sold_line(world, entry, names, place, other):
    return f"Sold {world.entity(entry.data['item']).name} at {place}."


@outcome("armoury_drawn", body_facts=False)
def _drawn(world, event):
    d = event.data
    return [f"The armoury's keeper hands you {d['form'] if d['slot'] == 'weapon' else 'armour'} of {world.entity(d['faction']).name}'s stock."], {}


@summary("armoury_drawn")
def _drawn_line(world, entry, names, place, other):
    return f"Drew from the {world.entity(entry.data['faction']).name}'s armoury."


@outcome("armoury_returned", body_facts=False)
def _returned(world, event):
    return ["The keeper takes it back and marks the ledger."], {}


@summary("armoury_returned")
def _returned_line(world, entry, names, place, other):
    return "Returned gear to the armoury."


@outcome("gear_seized", body_facts=False)
def _seized(world, event):
    item = world.entity(event.data["item"])
    return [f"You take {item.name} from {world.entity(event.actors[1]).name}."
            + (" The law will call it robbery." if event.data["lawful"] else "")], {}


@summary("gear_seized")
def _seized_line(world, entry, names, place, other):
    return f"Took {world.entity(entry.data['item']).name} from {other}."


@outcome("heirloom_returned", body_facts=False)
def _heirloom(world, event):
    return [f"{world.entity(event.actors[1]).name} takes {world.entity(event.data['item']).name} in both hands. "
            "The clan will not forget this."], {}


@summary("heirloom_returned")
def _heirloom_line(world, entry, names, place, other):
    return f"Gave {world.entity(entry.data['item']).name} back to its clan."
