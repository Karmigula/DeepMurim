"""Conversation: meeting, remembering, small talk, and running out of patience."""

from collections import Counter

from systems.time import advance
from world.db import Memory, World
from world.events import Event, Witness, effect

TOPICS = ("work", "town")
GREETINGS = ("met", "conversed")
PATIENCE = 3  # repeated questions tolerated in one conversation
PATIENCE_BY_TRAIT = {"hot-tempered": 2, "kind": 4}


def patience_of(npc) -> int:
    for trait in npc.data.get("traits", []):
        if trait in PATIENCE_BY_TRAIT:
            return PATIENCE_BY_TRAIT[trait]
    return PATIENCE


def current_conversation(world: World, npc_id: int, player_id: int) -> list[Memory]:
    """What the NPC remembers since their latest greeting with the player."""
    memories = world.memories(npc_id, about=player_id)
    starts = [i for i, m in enumerate(memories) if m.event.kind in GREETINGS]
    return memories[starts[-1] + 1:] if starts else memories


def times_asked(world: World, npc_id: int, player_id: int, topic: str) -> int:
    """Across every conversation ever, how often the player asked this."""
    return sum(
        1 for m in world.memories(npc_id, about=player_id)
        if m.event.kind == "asked" and m.event.data.get("topic") == topic
    )


def repeats_if_asked(world: World, npc_id: int, player_id: int, topic: str) -> int:
    """Repeated questions in this conversation, counting the one about to be asked."""
    counts = Counter(
        m.event.data.get("topic") for m in current_conversation(world, npc_id, player_id) if m.event.kind == "asked"
    )
    counts[topic] += 1
    return sum(count - 1 for count in counts.values())


def lost_patience_events(player: int, npc_id: int, place: int, topic: str) -> list[Event]:
    return [Event("lost_patience", (player, npc_id), place, {"topic": topic}, witnesses=(Witness(npc_id, "annoyed", 0.5),))]


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
