"""Teachers and manuals (phase 2 spec §10).

A teacher's art is learned whole. A manual teaches only what it truly
contains, while claiming more; the claim is what its reader believes until
practice at the true limit ends in a deviation that reveals the lie.
"""

from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.duel import ensure_npc_arts
from systems.reputation import reputation
from systems.items import create_manual, manual_price, manuals_of, transfer_events
from systems.purse import payment_events
from systems.talk import conversations_with
from systems.techniques import create_technique, generate, known_arts, teach
from systems.time import advance
from world.events import Event, effect
from world.seed import rng_for

GOODS_CHANCE = {"merchant": 0.4, "scholar": 0.4}
STUDY_DAYS = 14


def lesson_price(known) -> int:
    return 20 * known.technique.data["grade"] ** 2


def teachable_arts(world, npc_id: int, player_id: int) -> list:
    arts = ensure_npc_arts(world, npc_id)
    if not world.entity(npc_id).data.get("teacher"):
        return []
    mine = {a.technique.id for a in known_arts(world, player_id)}
    return [a for a in arts if a.technique.id not in mine]


def will_deal(world, npc_id: int, player_id: int) -> bool:
    """The hostile will neither teach nor sell (phase 3a spec 3.2)."""
    return attitude(world, npc_id, apparent_to(world, npc_id, player_id)).score > -1.0


def will_teach(world, npc_id: int, player_id: int, town_id: int) -> bool:
    """And the kind and honest will not teach a name this town calls ruthless."""
    if not will_deal(world, npc_id, player_id):
        return False
    if {"kind", "honest"} & set(world.entity(npc_id).data.get("traits", ())):
        return reputation(world, town_id, apparent_to(world, town_id, player_id)).path != "ruthless"
    return True


def can_ask_to_learn(world, npc_id: int, player_id: int) -> bool:
    return len(conversations_with(world, npc_id, player_id)) >= 2 and bool(teachable_arts(world, npc_id, player_id))


def lesson_events(world, player: int, teacher: int, place: int, technique_id: int, via: str) -> list[Event]:
    art = next((a for a in teachable_arts(world, teacher, player) if a.technique.id == technique_id), None)
    if art is None:
        return []
    price = lesson_price(art) if via == "silver" else 0
    events = payment_events(player, teacher, place, price, "lesson") if price else []
    return events + [Event("learned", (player, teacher), place,
                           {"technique": technique_id, "name": art.name, "via": via, "price": price})]


@effect("learned")
def _learned(world, event: Event) -> None:
    player, teacher = event.actors
    teach(world, player, event.data["technique"], source="taught", teacher=teacher)


def ensure_goods(world, npc_id: int) -> list:
    npc = world.entity(npc_id)
    if npc.data.get("goods_ready"):
        return manuals_of(world, npc_id)
    key = npc.seed_path or f"entity:{npc_id}"
    rng = rng_for(world.world_seed, f"{key}/goods")
    with world.transaction():
        if rng.random() < GOODS_CHANCE.get(npc.data.get("occupation"), 0.0):
            for _ in range(rng.randint(1, 2)):
                name, art = generate(rng, "martial", grade=rng.randint(1, 2))
                create_manual(world, npc_id, create_technique(world, name, art), rng.uniform(0.4, 1.0))
        world.update_data(npc_id, goods_ready=True)
    return manuals_of(world, npc_id)


def purchase_events(world, player: int, seller: int, place: int, item_id: int) -> list[Event]:
    manual = next((m for m in manuals_of(world, seller) if m.item.id == item_id), None)
    if manual is None:
        return []
    return (payment_events(player, seller, place, manual_price(manual), "manual")
            + transfer_events(seller, player, place, [item_id], "bought"))


def unstudied(world, player: int) -> list:
    known = {a.technique.id for a in known_arts(world, player)}
    return [m for m in manuals_of(world, player) if m.technique.id not in known]


def study_events(world, player: int, place: int, item_id: int) -> list[Event]:
    manual = next((m for m in unstudied(world, player) if m.item.id == item_id), None)
    if manual is None:
        return []
    data = {"item": item_id, "technique": manual.technique.id, "name": manual.technique.name, "days": STUDY_DAYS}
    return [Event("studied_manual", (player,), place, data)]


@effect("studied_manual")
def _studied(world, event: Event) -> None:
    player, data = event.actors[0], event.data
    advance(world, data["days"] * 4)
    item = world.entity(data["item"])
    teach(world, player, data["technique"], completeness=item.data["true_completeness"],
          known_completeness=item.data["claimed_completeness"], source="manual")
