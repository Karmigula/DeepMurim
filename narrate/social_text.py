"""Greetings that show how someone feels about the player, and why (phase 3a spec 3.2)."""

from narrate.outcomes import cap, outcome
from systems.attitude import attitude
from systems.beliefs import apparent_to


@outcome("met", body_facts=False)
@outcome("conversed", body_facts=False)
def _greeting(world, event):
    player, npc = event.actors[0], event.actors[1]
    feeling = attitude(world, npc, apparent_to(world, npc, player))
    if not feeling.reason or feeling.word == "neutral":
        return [], {}
    return [f"{cap(world.entity(npc).name)} seems {feeling.word} toward you ({feeling.reason})."], \
        {"attitude": feeling.word}
