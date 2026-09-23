"""Every state change is an Event, committed atomically with its effects."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from world.db import World


@dataclass(frozen=True)
class Witness:
    owner: int
    feeling: str
    intensity: float
    indelible: bool = False


@dataclass(frozen=True)
class Event:
    kind: str
    actors: tuple[int, ...]
    place: int | None = None
    data: dict = field(default_factory=dict)
    weight: float = 1.0
    witnesses: tuple[Witness, ...] = ()


Effect = Callable[[World, Event], None]
EFFECTS: dict[str, Effect] = {}
Listener = Callable[[World, Event, int], None]
LISTENERS: dict[str, list[Listener]] = {}
INDELIBLE_FEELINGS = frozenset({"hatred", "grief", "saved", "betrayed"})  # never fade (phase 3a spec §3.1)


def effect(kind: str) -> Callable[[Effect], Effect]:
    """Register how an event kind changes state beyond being recorded."""
    def register(fn: Effect) -> Effect:
        EFFECTS[kind] = fn
        return fn
    return register


def listen(kind: str) -> Callable[[Listener], Listener]:
    """Register a reaction to an event kind, run after its effect, given the new event's id.

    Several listeners can watch one kind (facts, kin and masks each add their own).
    """
    def register(fn: Listener) -> Listener:
        LISTENERS.setdefault(kind, []).append(fn)
        return fn
    return register


def commit(world: World, events: Sequence[Event]) -> list[int]:
    """Record, remember and apply events; all of them or none of them."""
    ids = []
    with world.transaction():
        for event in events:
            event_id = world.append_chronicle(event.kind, event.actors, event.place, event.data, event.weight)
            for witness in event.witnesses:
                lasting = witness.indelible or witness.feeling in INDELIBLE_FEELINGS
                world.add_memory(witness.owner, event_id, witness.feeling, witness.intensity, lasting)
            apply = EFFECTS.get(event.kind)
            if apply is not None:
                apply(world, event)
            for react in LISTENERS.get(event.kind, ()):
                react(world, event, event_id)
            ids.append(event_id)
    return ids
