"""Typed commands to Actions, matched against what the player can do right now.

The parser knows only global words and the current choices, so every command
the engine can take also has a number to press.
"""

import re

from engine.game import Action, Choice

GLOBAL = {
    "look": "look", "l": "look", "journal": "journal", "j": "journal", "chronicle": "journal",
    "help": "help", "?": "help", "bye": "farewell", "farewell": "farewell", "leave": "farewell",
}
PREFIX_VERBS = {"talk": "talk", "speak": "talk", "go": "travel", "travel": "travel", "walk": "travel", "ask": "ask"}
FILLER = {"to", "about", "with", "the"}
WORD = re.compile(r"[a-z0-9']+")


def _words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def parse(text: str, choices: list[Choice], extra: list[Choice] = ()) -> Action | None:
    """Numbers index the visible `choices`; words also search `extra` (grouped-away choices)."""
    cleaned = " ".join(text.split())[:200]
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered.isascii() and lowered.isdigit():
        n = int(lowered)
        return choices[n - 1].action if 1 <= n <= len(choices) else Action("unknown", cleaned)
    if lowered in GLOBAL:
        return Action(GLOBAL[lowered])
    head, _, rest = lowered.partition(" ")
    verb = PREFIX_VERBS.get(head)
    wanted = [w for w in _words(rest) if w not in FILLER]
    if verb is None or not wanted:
        return Action("unknown", cleaned)
    pool = [c for c in [*choices, *extra] if c.action.verb == verb]
    pool = list({c.action: c for c in pool}.values())  # a choice may be both visible and extra
    exact = [c for c in pool if all(w in _words(c.label) for w in wanted)]
    prefix = [c for c in pool if all(any(lw.startswith(w) for lw in _words(c.label)) for w in wanted)]
    for matches in (exact, prefix):
        if len(matches) == 1:
            return matches[0].action
        if len(matches) > 1:
            return Action("ambiguous", tuple(matches))
    return Action("unknown", cleaned)
