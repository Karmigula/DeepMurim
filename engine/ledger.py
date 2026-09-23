"""The sect ledger (F7, phase 3c spec 8)."""

import systems.founding as founding
import systems.sect as sect_mod
from engine.standing_page import known_factions
from narrate.base import Line
from systems import factions as F


def _loyalty_word(value: int) -> str:
    return "devoted" if value >= 80 else "loyal" if value >= 50 else "uneasy" if value >= 25 else "disloyal"


def ledger_lines(world, player: int) -> list[Line]:
    sect = founding.my_sect(world, player)
    if sect is None:
        return [("You lead no sect.", "system")]
    entity = world.entity(sect)
    d = entity.data
    taboos = ", ".join(t.replace("_", " ") for t in d.get("taboos", []))
    lines: list[Line] = [
        (f"{entity.name} ({d['path']}) at {world.entity(d['seat']).name}", "heading"),
        (f"Taboos: {taboos}. Entry: {d['trial']}.", "dim"),
        (f"Treasury: {d['treasury']} silver | power {d['power']}", "dim"),
    ]
    building = [f"{b.replace('_', ' ')}{'' if v['built'] else ' (building)'}" for b, v in sorted(d.get("buildings", {}).items())]
    lines.append(("Buildings: " + (", ".join(building) or "none"), "dim"))
    roster = sect_mod.members(world, sect)
    lines.append((f"Roster ({len(roster)}):", "heading"))
    for person in roster:
        p = world.entity(person)
        rank = F.title(world, sect, F.membership(world, person, sect)[0])
        status = " - away on duty" if p.data.get("on_duty") else ""
        lines.append((f"  {p.name}, {rank}, {p.data.get('realm', 'mortal')}, {_loyalty_word(p.data.get('loyalty', 50))}{status}", "dim"))
    lines.append(("Relations:", "heading"))
    here = world.targets(player, "located_in")
    heard = set(known_factions(world, player, here[0])) if here else set()
    for other in [f for f in F.ensure_roster(world) if f in heard]:  # never name a faction the player never heard of
        value = sect_mod.sect_stance(world, other, sect)
        word = sect_mod.stance_word(value, sect_mod.has_pact(world, sect, other))
        if word != "neutral":
            lines.append((f"  {world.entity(other).name}: {word}", "dim"))
    lines.append(("Recent seasons:", "heading"))
    lines += [(f"  {line}", "dim") for line in d.get("chronicle", [])[-6:]] or [("  none yet", "dim")]
    return lines
