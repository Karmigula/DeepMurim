"""The prose guard (phase 6 spec 6): Claude's prose is shown only if it adds no one and nothing.

Refused when it names a person the player has not heard of (`check_people`'s rule), names a thing of the world
(an item, a pill, a herb, a manual) that the turn did not, or states a number the turn did not carry. The guard
reads the world's names only; it never decides what is true, only what the prose may not bring in.
"""

import re

from systems.beliefs import known_people
from world.gen.materialize import people_at

THINGS = ("gear", "pill", "herb", "treasure", "scroll", "manual", "furnace", "recipe")
NUMBER = re.compile(r"\b\d+\b")


def _names(world, kinds) -> set[str]:
    marks = ",".join("?" * len(kinds))
    return {row[0] for row in world._conn.execute(f"select distinct name from entities where kind in ({marks})",
                                                  tuple(kinds))}


def allowed_people(world, player: int, place: int) -> set[str]:
    ids = set(known_people(world, player)) | {p.id for p in people_at(world, place)} | {player}
    return {world.entity(i).name for i in ids if world.entity(i) is not None}


def refusal(world, prose: str, player: int, place: int, given: str, needed: str = "") -> str | None:
    """Why this prose may not be shown (None: it may). `given` is all the turn told Claude (briefs and pack);
    `needed` is the text it replaces: every number there (silver, merit, days) must be kept."""
    allowed = allowed_people(world, player, place)
    for name in _names(world, ("person", "persona")):
        if name in prose and name not in allowed:
            return f"it names {name}, whom you have not heard of"
    for name in _names(world, THINGS):
        if len(name) > 3 and name in prose and name not in given:
            return f"it names {name}, which the turn did not"
    numbers = set(NUMBER.findall(given))
    stated = set(NUMBER.findall(prose))
    for number in stated:
        if number not in numbers:
            return f"it states {number}, which the turn did not"
    for number in NUMBER.findall(needed):
        if number not in stated:
            return f"it leaves out the {number} the turn told"
    return None
