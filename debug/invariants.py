"""Rules that must hold after every turn. A broken rule is a bug caught early.

Checked live by the app (violations show in the log and F12 overlay) and by the
fuzz test, so new systems are policed from the moment they exist.
"""

import re
from collections.abc import Sequence

from narrate.brief import MAX_FACTS, MAX_PROMPT

LEFTOVER = re.compile(r"\{\w+\}|#\w+#")
FALLBACK = re.compile(r"^\[\w+\]$")
LOWER_START = re.compile(r"(^|[.?!]\s+)[\"']?[a-z]")
NARRATIVE = {"npc", "default", "gold"}  # prose colours; dim/system lines may repeat legitimately
MAX_CHOICES = 9


def check_world(world) -> list[str]:
    problems = []
    player_id = world.get_meta("player_id")
    if player_id is not None and world.entity(player_id) is None:
        problems.append(f"player_id #{player_id} points at nothing")
    for person in world.entities("person"):
        places = world.targets(person.id, "located_in")
        if len(places) != 1:
            problems.append(f"{person.name} (#{person.id}) has {len(places)} locations")
        for place in places:
            if world.entity(place) is None:
                problems.append(f"{person.name} (#{person.id}) is located in missing entity #{place}")
    times = world.recent_chronicle_times()
    for before, after in zip(times, times[1:]):
        if after < before:
            problems.append(f"chronicle time went backwards ({before} -> {after})")
    return problems


def check_turn(game, turn, recent_narration: Sequence[str]) -> list[str]:
    problems = []
    for text, key in turn.lines:
        if LEFTOVER.search(text):
            problems.append(f"leftover template slot in: {text[:80]}")
        if FALLBACK.match(text):
            problems.append(f"narration fallback, no grammar for {text}")
        if key in NARRATIVE and LOWER_START.search(text):
            problems.append(f"lowercase sentence start in: {text[:80]}")
        if key in NARRATIVE and text and text in recent_narration:
            problems.append(f"repeat of a recent line: {text[:80]}")
    if len(turn.choices) > MAX_CHOICES:
        problems.append(f"{len(turn.choices)} choices shown; only {MAX_CHOICES} have number keys")
    for choice in turn.all_choices:
        if not hasattr(game, f"_do_{choice.action.verb}"):
            problems.append(f"choice {choice.label!r} has no handler for verb {choice.action.verb!r}")
    for brief in getattr(game, "last_briefs", []):
        prompt = brief.to_prompt()
        if len(brief.facts) > MAX_FACTS:
            problems.append(f"brief for {brief.kind} has {len(brief.facts)} facts (max {MAX_FACTS})")
        if len(prompt) > MAX_PROMPT:
            problems.append(f"brief for {brief.kind} is {len(prompt)} chars (max {MAX_PROMPT})")
        if LEFTOVER.search(prompt):
            problems.append(f"leftover template slot in {brief.kind} brief")
    return problems
