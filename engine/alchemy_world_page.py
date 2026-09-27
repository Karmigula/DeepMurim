"""The alchemy world's pages (phase 5c spec 7-8): a hall and garden as known, the Guild, the clinic, the dark, the
scrolls one carries, and the sheet's lines (a Guild rank, a healer's name, the worms)."""

import systems.control as C
import systems.guild as G
import systems.hall_theft as T
import systems.physic as PY
import systems.pill_hall as PH
import systems.recipe_trade as RT
from systems.bodies import load_body
from systems.time import format_season_year


def recipe_label(world, key: str) -> str:
    """A recipe's world name once it has one, else its plain kind (asking never names it)."""
    found = world.entity_by_seed(f"recipe:{key}")
    return found.name if found is not None else key.replace("_", " ")


def hall_lines(world, viewer: int, faction: int) -> list:
    """What a sect's hall and garden hold, only for one who knows them (spec 8)."""
    name = world.entity(faction).name
    if not T.knows_hall(world, viewer, faction):
        return [(f"You do not know what the {name} keeps.", "dim")]
    lines = [(f"The {name}", "heading")]
    if PH.keeps_hall(world, faction):
        stock = sorted(PH.table(world, faction).items())
        held = ", ".join(f"{count} grade-{key.split(':')[0]} {key.split(':')[1]}" for key, count in stock if count > 0)
        lines.append((f"  Pill hall: {held or 'empty'}", "dim"))
        if not PH.own(world, faction):
            secrets = ", ".join(recipe_label(world, k) for k in RT.secret_recipes(world, faction))
            lines.append((f"  Its secret recipes: {secrets}", "dim"))
    if PH.keeps_garden(world, faction):
        grown = ", ".join(f"{count} {herb} ({'a hundred years' if grade >= 2 else 'ten years' if grade else 'young'})"
                          for herb, (count, grade) in sorted(PH.garden(world, faction).items()) if count > 0)
        lines.append((f"  Herb garden: {grown or 'bare'}", "dim"))
        if PH.guarded(world, faction):
            lines.append(("  Something large sleeps among the oldest herbs.", "dim"))
    return lines


def guild_lines(world, player: int) -> list:
    rank = world.entity(player).data.get("guild_rank")
    lines = [("The Alchemists' Guild", "heading")]
    if rank is None:
        lines.append(("  You are not of the Guild. Joining costs nothing.", "dim"))
    else:
        lines.append((f"  You are {G.title(rank)}.", "dim"))
        if rank < G.MAX_RANK:
            lines.append((f"  The {G.ORDINALS[rank + 1]} rank asks a recipe of grade {G.needed_grade(rank + 1)} and "
                          f"{G.EXAM_FEE * (rank + 1)} silver.", "dim"))
    return lines


def clinic_lines(world, player: int, town: int) -> list:
    lines = [(f"The physician's clinic in {world.entity(town).name}", "heading")]
    seen = world.entity(player).data.get("doctors_seen") or {}
    for key, found in sorted(seen.items()):
        doctor = world.entity(found["doctor"])
        if doctor is None or doctor.data.get("dead"):
            continue
        when = format_season_year(found["season"] * 360)
        lines.append((f"  {doctor.name}, {doctor.data['doctor']['title']}, was last seen in {found['town']} "
                      f"({when}).", "dim"))
    return lines


def night_lines(world, player: int, factions: list[int]) -> list:
    lines = [("The dark is a thief's friend." if T.night(world) else "It is too light to steal.", "dim")]
    for fid in factions:
        if T.knows_hall(world, player, fid):
            lines += hall_lines(world, player, fid)
        lines.append((f"  Against the {world.entity(fid).name}: a {round(100 * T.chance(world, player, fid))}% chance "
                      "to go unseen.", "dim"))
    return lines


def scroll_lines(world, player: int) -> list:
    scrolls = RT.scrolls_of(world, player)
    if not scrolls:
        return []
    return [("Scrolls you carry:", "heading")] + [(f"  {s.name}", "dim") for s in scrolls]


def sheet_alchemy_world_lines(world, player: int) -> list:
    """The sheet's lines: a Guild rank, the towns that call you healer, the worms in you, those bound to you."""
    entity = world.entity(player)
    lines = []
    rank = entity.data.get("guild_rank")
    if rank is not None:
        lines.append((f"Alchemists' Guild: {G.title(rank)}", "default"))
    towns = PY.healer_of(world, player)
    if towns:
        lines.append(("Known as the healer of " + ", ".join(world.entity(t).name for t in towns), "default"))
    bound = C.bound(world, player)
    if bound:
        master = world.entity(bound["master"]).name
        days = (bound["fed_until"] - world.time) / 4
        state = f"fed for {max(0, round(days))} more day(s)" if days >= 0 else f"unfed for {round(-days)} day(s)"
        task = C.service(world, player)
        what = {"message": f"carry a message to {task.get('town')}", "beat": "beat a fighter in a real duel",
                "steal": "rob a sect's garden or hall unseen"}[task["kind"]]
        lines.append((f"Bound to {master} by a control pill: {state}. This month's service: {what}.", "red"))
    servants = C.servants_of(world, player)
    if servants:
        lines.append(("Bound to you: " + ", ".join(world.entity(s).name for s in servants), "default"))
    body = load_body(world, player)
    if body.poisons and any(not p.get("named") for p in body.poisons):
        lines.append(("A physician could read your body and name what poisons you.", "dim"))
    return ([("", "default"), ("Alchemy:", "heading")] + lines) if lines else []
