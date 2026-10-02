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
POSSESSIVE = re.compile(r"'s?$")
NAMED = re.compile(r"\b[A-Z][a-z'\-]+(?:\s+[A-Z][a-z'\-]+)+")  # two or more capitalised words: a name
LEADING = frozenset({"The", "A", "An", "You", "Your", "In", "At", "On", "As", "But", "And", "Then", "When", "Old",
                     "Young", "Little", "Elder", "Brother", "Sister", "Master", "Uncle", "Aunt", "Lord", "Lady"})


def _names(world, kinds) -> set[str]:
    marks = ",".join("?" * len(kinds))
    return {row[0] for row in world._conn.execute(f"select distinct name from entities where kind in ({marks})",
                                                  tuple(kinds))}


def allowed_people(world, player: int, place: int) -> set[str]:
    ids = set(known_people(world, player)) | {p.id for p in people_at(world, place)} | {player}
    names = {world.entity(i).name for i in ids if world.entity(i) is not None}
    own = world._conn.execute("select name from entities where kind = 'persona' and json_extract(data, '$.of') = ?",
                              (player,))
    return names | {row[0] for row in own}  # the player's own masks are no strangers (6a review)


def _names_in(name: str, prose: str) -> bool:
    """The name as a whole name, not inside a longer one ("Baek Yun" is not in "Baek Yunsu")."""
    return name in prose and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", prose) is not None


def names_in(text: str) -> list[str]:
    """The names a text seems to give: two or more capitalised words, a leading "The" or "You" and a trailing
    possessive taken off ("Jin Yunhyun's eyes" names Jin Yunhyun). The guard and the deed check share it."""
    out = []
    for found in NAMED.findall(text):
        words = found.split()
        words[-1] = POSSESSIVE.sub("", words[-1])
        while words and words[0] in LEADING:
            words = words[1:]
        if len(words) >= 2:
            out.append(" ".join(words))
    return out


def refusal(world, prose: str, player: int, place: int, given: str, needed: str = "") -> str | None:
    """Why this prose may not be shown (None: it may). `given` is all the turn told Claude (briefs and pack);
    `needed` is the text it replaces: every number there (silver, merit, days) must be kept."""
    allowed = allowed_people(world, player, place)
    for name in _names(world, ("person", "persona")):
        if name not in allowed and _names_in(name, prose):
            return f"it names {name}, whom you have not heard of"
    for name in _names(world, THINGS):
        if len(name) > 3 and name not in given and _names_in(name, prose):
            return f"it names {name}, which the turn did not"
    for name in names_in(prose):  # a name Claude made up is in no table at all (6a minors)
        if name not in given and not any(name in known for known in allowed):
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
