"""Manuals as items (phase 2 spec §10), owned through the `owns` relation.

A manual carries a technique, how complete it truly is, and how complete it
claims to be. Only the claim is ever shown, until practice proves it wrong.
"""

from dataclasses import dataclass

from world.db import Entity, World
from world.events import Event, effect


@dataclass(frozen=True)
class Manual:
    item: Entity
    technique: Entity

    @property
    def name(self) -> str:
        return self.item.name

    @property
    def true_completeness(self) -> float:
        return self.item.data["true_completeness"]

    @property
    def claimed(self) -> float:
        return self.item.data["claimed_completeness"]

    @property
    def grade(self) -> int:
        return self.technique.data["grade"]


def create_manual(world: World, owner_id: int, technique_id: int, true_completeness: float, claimed: float = 1.0) -> int:
    technique = world.entity(technique_id)
    data = {"technique": technique_id, "true_completeness": round(true_completeness, 2), "claimed_completeness": claimed}
    with world.transaction():
        item = world.add_entity("manual", f"{technique.name} manual", data)
        world.relate(owner_id, item, "owns")
    return item


def manuals_of(world: World, person_id: int) -> list[Manual]:
    manuals = []
    for item_id in world.targets(person_id, "owns"):
        item = world.entity(item_id)
        if item.kind == "manual":
            manuals.append(Manual(item, world.entity(item.data["technique"])))
    return manuals


def manual_price(manual: Manual) -> int:
    return int(15 * manual.grade ** 2 * manual.claimed) + 10


def transfer_events(giver: int, taker: int, place: int, item_ids, reason: str) -> list[Event]:
    return [Event("handed_over", (giver, taker), place, {"items": list(item_ids), "reason": reason})]


@effect("handed_over")
def _handed_over(world: World, event: Event) -> None:
    giver, taker = event.actors
    for item in event.data["items"]:
        if item not in world.targets(giver, "owns"):
            raise ValueError(f"#{giver} does not own item #{item}")
        world.unrelate(giver, "owns", item)
        world.relate(taker, item, "owns")
