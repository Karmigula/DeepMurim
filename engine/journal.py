"""One-line summaries of chronicle entries for the player's journal."""

from narrate.outcomes import SUMMARIES
from systems.time import days_word, format_date
from world.db import ChronicleEntry, World
from world.gen.town import town_path


def summarize(world: World, entry: ChronicleEntry) -> str:
    names = [world.entity(a).name for a in entry.actors]
    place = world.entity(entry.place).name if entry.place else "the road"
    other = names[1] if len(names) > 1 else "someone"
    data = entry.data
    if entry.kind in SUMMARIES:
        return f"{format_date(entry.time)} - {SUMMARIES[entry.kind](world, entry, names, place, other)}"
    match entry.kind:
        case "began":
            text = f"{names[0]} set out from {place}."
        case "body_awakened":
            text = "Took stock of body and training."
        case "met":
            text = f"Met {other} in {place}."
        case "conversed":
            text = f"Spoke again with {other} in {place}."
        case "asked":
            topic = str(data.get("topic", "things"))
            text = f"Asked {other} {topic}." if topic.startswith("about ") else f"Asked {other} about {topic}."
        case "parted":
            text = f"Took leave of {other}."
        case "lost_patience":
            text = f"{other} lost patience with your questions."
        case "travelled":
            dest = world.entity_by_seed(town_path(*data["to"]))
            text = f"Left {place} for {dest.name if dest else 'parts unknown'}."
        case "cultivated":
            text = f"Meditated for {days_word(data['days'])}."
        case "practised":
            text = f"Practised the {data['technique']}."
        case "opening_meridian":
            text = f"Opened the {data['meridian']} meridian." if data["opened"] else f"Worked on the {data['meridian']} meridian."
        case "rested":
            text = "Rested."
        case "breakthrough":
            text = f"Broke through to {data['target']}." if data["success"] else f"Failed to break through to {data['target']}."
        case "deviation":
            text = "Suffered a qi deviation."
        case _:
            text = entry.kind
    return f"{format_date(entry.time)} - {text}"
