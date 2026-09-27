"""The alchemist's page (phase 5b spec 5-6): recipes, herbs as known, the furnace's tray, the body's poisons."""

import math

import systems.alchemy as A
import systems.herbs as H
import systems.toxins as X
from systems.bodies import load_body
from world.body import WATCHES_PER_DAY


def herb_line(world, viewer: int, item) -> str:
    name, grade = H.herb_info(item)
    if not H.known(world, viewer, name):
        return f"{H.herb_name(name, grade)}: its nature unknown until tasted"
    p = H.props(name)
    return (f"{H.herb_name(name, grade)}: {p['element']}, {p['polarity']}, potency {p['potency']}, "
            f"toxicity {p['toxicity']}")


def poison_words(body) -> list[str]:
    """What the body tells of its poisons: the grade only of those it knows (spec 6)."""
    out = []
    for p in body.poisons:
        grade = f"grade {p['grade']}" if p.get("named") else "grade unknown"
        death = X.days_to_death(body, p)
        if death is not None:
            out.append(f"poison in your blood ({grade}): it will kill you within {max(1, math.ceil(death))} day(s)")
        else:
            out.append(f"poison in your blood ({grade}), {max(1, math.ceil(p['strength'] / WATCHES_PER_DAY))} "
                       f"day(s) of it left")
    return out


def alchemy_lines(world, player: int, tray: list[int]) -> list:
    body = load_body(world, player)
    lines = [("Alchemy", "heading"), (f"  Alchemy level {A.level(world, player)} | residue {body.residue:.0f} | "
                                     f"venom {body.venom:.0f}", "dim")]
    for words in poison_words(body):
        lines.append((f"  {words}", "red"))
    known = A.known_recipes(world, player)
    lines.append(("Recipes you know:" if known else "You know no recipes yet: experiment to find them.", "heading"))
    for recipe, mastery in known:
        entity = world.entity(recipe)
        lines.append((f"  {entity.name} ({entity.data['effect']}): mastery {mastery:.2f}", "dim"))
    herbs = H.herbs_of(world, player)
    if herbs:
        lines.append(("Herbs you carry:", "heading"))
        lines += [(f"  {herb_line(world, player, h)}", "dim") for h in herbs]
    if tray:
        names = ", ".join(H.herb_name(*H.herb_info(world.entity(h))) for h in tray if H.herb_info(world.entity(h)))
        lines.append((f"In the furnace: {names}", "dim"))
    for hint in (world.entity(player).data.get("alchemy_hints") or [])[-3:]:
        lines.append((f"  A note to yourself: {hint}", "dim"))
    return lines


def constitution_words(world, player: int) -> str:
    """The sheet's note of residue, venom and poisons, folded into its constitution line."""
    body = load_body(world, player)
    parts = [f"residue {body.residue:.0f}"]
    if body.venom:
        parts.append(f"venom {body.venom:.0f}")
    if body.poisons:
        parts.append(f"{len(body.poisons)} poison(s) in your blood")
    return " | " + " | ".join(parts)
