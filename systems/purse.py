"""Silver (phase 2 spec §8). Changed only through events; NPC purses are seeded on first use."""

from world.db import World
from world.events import Event, effect
from world.seed import rng_for

OCCUPATION_SILVER = {
    "merchant": (40, 200), "innkeeper": (20, 80), "scholar": (10, 60), "blacksmith": (15, 60),
    "constable": (10, 40), "wandering swordsman": (5, 50), "bandit": (10, 120), "beggar": (0, 5),
}
DEFAULT_SILVER = (5, 30)


def silver_of(world: World, person_id: int) -> int:
    entity = world.entity(person_id)
    if "silver" in entity.data:
        return int(entity.data["silver"])
    if entity.data.get("beast"):
        amount = 0
    else:
        low, high = OCCUPATION_SILVER.get(entity.data.get("occupation"), DEFAULT_SILVER)
        key = entity.seed_path or f"entity:{person_id}"
        amount = rng_for(world.world_seed, f"{key}/silver").randint(low, high)
    world.update_data(person_id, silver=amount)
    return amount


def payment_events(payer: int, payee: int | None, place: int, amount: int, reason: str) -> list[Event]:
    actors = (payer,) if payee is None else (payer, payee)
    return [Event("paid", actors, place, {"amount": int(amount), "reason": reason})]


@effect("paid")
def _paid(world: World, event: Event) -> None:
    amount, payer = event.data["amount"], event.actors[0]
    have = silver_of(world, payer)
    if amount < 0 or amount > have:
        raise ValueError(f"#{payer} cannot pay {amount} silver (has {have})")
    world.update_data(payer, silver=have - amount)
    if len(event.actors) > 1:
        payee = event.actors[1]
        world.update_data(payee, silver=silver_of(world, payee) + amount)
