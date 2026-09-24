"""The lineage page (F8, phase 4b spec 7): who came before you, who is yours, and who would carry on."""

import systems.agendas as agendas
import systems.bonds as bonds
import systems.mortality as mortality
from narrate.base import Line
from systems.facts import place_name
from systems.founding import followers
from systems.kin import kin_of


def _someone(world, person: int) -> str:
    p = world.entity(person)
    here = world.targets(person, "located_in")
    where = world.entity(here[0]).name if here else "the roads"
    return f"{p.name}, {int(p.data.get('age', 30))}, {p.data.get('realm', 'mortal')}, in {where}"


def _ancestor(world, person: int) -> str:
    p = world.entity(person)
    death = p.data.get("death") or {}
    killer = world.entity(death["killer"]).name if death.get("killer") else "someone"
    how = mortality.CAUSES.get(death.get("cause"), "").format(killer=killer)
    where = place_name(world, death.get("place")) or "the road"
    return f"  {p.name}, died {how} in {where}, aged {int(death.get('age') or p.data.get('age', 0))}"


def lineage_lines(world, player: int) -> list[Line]:
    lines: list[Line] = [("Your lineage", "heading")]
    ancestors = world.entity(player).data.get("ancestors", [])
    if ancestors:
        lines.append(("Ancestors:", "heading"))
        lines += [(_ancestor(world, a), "dim") for a in ancestors]
    lines.append(("Family and bonds:", "heading"))
    spouse = agendas.spouse_of(world, player)
    rows = []
    if spouse is not None:
        rows.append(f"  Spouse: {_someone(world, spouse)}")
    for role, word in (("child", "Child"), ("disciple", "Disciple"), ("sworn_sibling", "Sworn sibling")):
        rows += [f"  {word}: {_someone(world, k)}" for k, r in kin_of(world, player) if r == role]
    rows += [f"  Sworn follower: {_someone(world, f)}" for f in followers(world, player)]
    lines += [(row, "dim") for row in rows] or [("  none yet", "dim")]
    named = world.entity(player).data.get("named_heir")
    if named is not None:
        lines.append((f"Named heir: {world.entity(named).name}", "dim"))
    lines.append(("If you died today:", "heading"))
    heirs = bonds.candidates(world, player)[:3]
    lines += [(f"  {i}. {world.entity(p).name} ({bonds.relation_word(world, p, kind)})", "dim")
              for i, (p, kind) in enumerate(heirs, 1)] or [("  no one would carry on your name", "dim")]
    return lines
