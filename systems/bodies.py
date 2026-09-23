"""Getting a person's body. NPC bodies are rolled from their seed the first time
anything needs one; every save keeps data["realm"] in step with the body."""

from systems.realms import REALMS, next_threshold, realm_index
from world.body import Body, body_of, max_qi, roll_body, settle, to_dict
from world.db import World
from world.seed import rng_for


def npc_body(world: World, entity) -> Body:
    key = entity.seed_path or f"entity:{entity.id}"
    rng = rng_for(world.world_seed, f"{key}/body")
    body = roll_body(rng)
    body.realm = realm_index(entity.data.get("realm", "mortal"))
    low, high = REALMS[body.realm].threshold, next_threshold(body.realm)
    body.energy_years = round(low + ((high - low) * rng.uniform(0.0, 0.6) if high else 0.0), 3)
    if body.realm >= 1:
        body.flags.append("sensed_qi")
    for name in ("Governing", "Conception")[: max(0, body.realm - 1)]:
        body.meridians[name].state, body.meridians[name].flow = "open", 0.3
    body.qi = max_qi(body)
    body.settled_at = world.time
    return body


def ensure_body(world: World, person_id: int) -> Body:
    """The person's body brought up to now; created from their seed if they have none."""
    entity = world.entity(person_id)
    existing = body_of(entity)
    if existing is not None:
        return settle(existing, world.time)
    body = npc_body(world, entity)
    world.update_data(person_id, body=to_dict(body))
    return body


def load_body(world: World, person_id: int) -> Body:
    return ensure_body(world, person_id)


def save_body(world: World, person_id: int, body: Body) -> None:
    body.qi = max(0.0, min(body.qi, max_qi(body)))
    world.update_data(person_id, body=to_dict(body), realm=REALMS[body.realm].label)
