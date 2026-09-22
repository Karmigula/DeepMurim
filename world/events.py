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


def effect(kind: str) -> Callable[[Effect], Effect]:
    """Register how an event kind changes state beyond being recorded."""
    def register(fn: Effect) -> Effect:
        EFFECTS[kind] = fn
        return fn
    return register


def commit(world: World, events: Sequence[Event]) -> list[int]:
    """Record, remember and apply events; all of them or none of them."""
    ids = []
    with world.transaction():
        for event in events:
            event_id = world.append_chronicle(event.kind, event.actors, event.place, event.data, event.weight)
            for witness in event.witnesses:
                world.add_memory(witness.owner, event_id, witness.feeling, witness.intensity, witness.indelible)
            apply = EFFECTS.get(event.kind)
            if apply is not None:
                apply(world, event)
            ids.append(event_id)
    return ids
