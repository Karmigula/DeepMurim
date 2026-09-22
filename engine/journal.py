"""One-line summaries of chronicle entries for the player's journal."""

from systems.time import format_date
from world.db import ChronicleEntry, World
from world.gen.town import town_path


def summarize(world: World, entry: ChronicleEntry) -> str:
    names = [world.entity(a).name for a in entry.actors]
    place = world.entity(entry.place).name if entry.place else "the road"
    other = names[1] if len(names) > 1 else "someone"
    match entry.kind:
        case "began":
            text = f"{names[0]} set out from {place}."
        case "met":
            text = f"Met {other} in {place}."
        case "conversed":
            text = f"Spoke again with {other} in {place}."
        case "asked":
            text = f"Asked {other} about {entry.data.get('topic', 'things')}."
        case "parted":
            text = f"Took leave of {other}."
        case "travelled":
            dest = world.entity_by_seed(town_path(*entry.data["to"]))
            text = f"Left {place} for {dest.name if dest else 'parts unknown'}."
        case _:
            text = entry.kind
    return f"{format_date(entry.time)} - {text}"
