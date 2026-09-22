"""Conversation. Phase 1: meeting, remembering, small talk."""

from systems.time import advance
from world.db import Memory, World
from world.events import Event, Witness, effect

TOPICS = ("work", "town")


def conversations_with(world: World, npc_id: int, about: int) -> list[Memory]:
    return [m for m in world.memories(npc_id, about=about) if m.event.kind in ("met", "conversed")]


def greet_events(world: World, player: int, npc_id: int, place: int) -> list[Event]:
    past = conversations_with(world, npc_id, player)
    kind, feeling = ("conversed", "familiar") if past else ("met", "curious")
    return [Event(kind, (player, npc_id), place, {"times": len(past)}, witnesses=(Witness(npc_id, feeling, 0.3),))]


def ask_events(player: int, npc_id: int, place: int, topic: str) -> list[Event]:
    return [Event("asked", (player, npc_id), place, {"topic": topic}, witnesses=(Witness(npc_id, "engaged", 0.1),))]


def farewell_events(player: int, npc_id: int, place: int) -> list[Event]:
    return [Event("parted", (player, npc_id), place)]


@effect("met")
@effect("conversed")
def _talking_takes_a_watch(world: World, event: Event) -> None:
    advance(world, 1)
