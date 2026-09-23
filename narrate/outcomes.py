"""Registries that let each feature narrate its own events (phase 2b).

OUTCOME_BUILDERS[kind](world, event) -> (outcome lines, details)
BODY_FACT_KINDS: kinds whose brief facts lead with the player's body
SUMMARIES[kind](world, entry, names, place, other) -> one journal line
"""

from collections.abc import Callable

OUTCOME_BUILDERS: dict[str, Callable] = {}
BODY_FACT_KINDS: set[str] = set()
SUMMARIES: dict[str, Callable] = {}


def outcome(kind: str, body_facts: bool = True):
    def register(fn: Callable) -> Callable:
        OUTCOME_BUILDERS[kind] = fn
        if body_facts:
            BODY_FACT_KINDS.add(kind)
        return fn
    return register


def summary(kind: str):
    def register(fn: Callable) -> Callable:
        SUMMARIES[kind] = fn
        return fn
    return register


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


# Feature modules register on import. Each later task appends its module here.
import narrate.combat_text  # noqa: E402,F401
