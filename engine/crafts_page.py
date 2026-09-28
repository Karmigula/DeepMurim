"""The crafts page (phase 5d spec 7-8): forging and formations as the player knows them, what is laid here, the
Meet's standings, and the sheet's lines."""

import systems.forging as FG
import systems.formations as FM
import systems.materials as M
import systems.meet as MT


def laid_lines(world, viewer: int, place) -> list:
    """What is laid here: one's own and patterns one knows by name, the rest only as something (spec 8)."""
    lines = []
    known = FM.known(world, viewer)
    for f in FM.laid(world, place):
        name = FM.PATTERNS[f["pattern"]]["name"]
        name = name[:1].upper() + name[1:]
        if f["owner"] == viewer:
            days = max(1, round((f["until"] - world.time) / 4))
            lines.append((f"  {name} holds here, laid by you ({days} day(s) left).", "dim"))
        elif f["pattern"] in known:
            lines.append((f"  {name} is laid here, by another hand.", "dim"))
        else:
            lines.append(("  Something is laid here: the air is wrong.", "dim"))
    return lines


def crafts_lines(world, player: int, place) -> list:
    lines = [("Crafts", "heading"),
             (f"  Forging level {FG.level(world, player)} | formation level {FM.level(world, player)} | "
              f"{FM.flags_of(world, player)} formation flags", "dim")]
    masteries = world.entity(player).data.get("forge_mastery") or {}
    if masteries:
        lines.append(("  Forged: " + ", ".join(f"{form} {m:.2f}" for form, m in sorted(masteries.items())), "dim"))
    known = FM.known(world, player)
    lines.append(("Patterns you know:" if known else "You know no formations yet: a manual will teach one.", "heading"))
    lines += [(f"  {FM.PATTERNS[k]['name']} ({FM.PATTERNS[k]['use']}): mastery {m:.2f}", "dim")
              for k, m in sorted(known.items())]
    materials = M.materials_of(world, player)
    if materials:
        lines.append(("Materials:", "heading"))
        lines += [(f"  {m.name} (grade {M.material_info(m)[1]})", "dim") for m in materials]
    manuals = FM.manuals_of(world, player)
    if manuals:
        lines.append(("Manuals:", "heading"))
        lines += [(f"  {m.name}", "dim") for m in manuals]
    if MT.is_open(world):  # the Meet is news: where it is held, and for how long
        m = MT.current(world)
        days = -(-(m["end"] - world.time) // 4)
        lines.append((f"The Meet of Hammer and Furnace is held in {world.entity(m['town']).name} "
                      f"for {days} more day(s).", "dim"))
    here = laid_lines(world, player, place)
    if here:
        lines.append(("Laid here:", "heading"))
        lines += here
    return lines


def meet_lines(world) -> list:
    m = MT.current(world)
    lines = [(f"The Meet of Hammer and Furnace, year {m['year']}", "heading")]
    for craft in MT.CRAFTS:
        top = MT.standings(world, craft)[:3]
        lines.append((f"  At {MT.WORDS[craft]}: " + "; ".join(f"{name} {score}" for name, score, _ in top), "dim"))
    return lines


def sheet_crafts_lines(world, player: int) -> list:
    masteries = world.entity(player).data.get("forge_mastery") or {}
    known = FM.known(world, player)
    if not masteries and not known:
        return []
    lines = [("", "default"), ("Crafts:", "heading"),
             (f"  Forging level {FG.level(world, player)}; formation level {FM.level(world, player)}", "default")]
    if known:
        lines.append(("  Patterns: " + ", ".join(FM.PATTERNS[k]["name"] for k in sorted(known)), "default"))
    return lines
