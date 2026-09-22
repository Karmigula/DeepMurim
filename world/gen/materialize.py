"""Turning seeds into records. After this, the database wins over the seed."""

from world.db import Entity, World
from world.gen.npc import npc_path, npc_spec
from world.gen.region import region_path, region_spec
from world.gen.town import town_path, town_spec


def ensure_region(world: World, x: int, y: int) -> int:
    path = region_path(x, y)
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    spec = region_spec(world.world_seed, x, y)
    data = {"x": x, "y": y, "terrain": spec.terrain, "town_count": spec.town_count}
    return world.add_entity("region", spec.name, data, path)


def ensure_town(world: World, x: int, y: int, i: int) -> int:
    path = town_path(x, y, i)
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    spec = town_spec(world.world_seed, x, y, i)
    with world.transaction():
        region_id = ensure_region(world, x, y)
        data = {
            "x": x, "y": y, "index": i, "kind": spec.kind, "terrain": spec.terrain,
            "npc_count": spec.npc_count, "populated": False,
        }
        town_id = world.add_entity("town", spec.name, data, path)
        world.relate(town_id, region_id, "located_in")
    return town_id


def people_at(world: World, place_id: int, exclude: int | None = None) -> list[Entity]:
    people = []
    for entity_id in world.sources(place_id, "located_in"):
        entity = world.entity(entity_id)
        if entity.kind == "person" and entity_id != exclude:
            people.append(entity)
    return people


def populate(world: World, town_id: int) -> list[Entity]:
    """Create the town's seeded residents the first time anyone looks."""
    town = world.entity(town_id)
    if not town.data["populated"]:
        with world.transaction():
            for i in range(town.data["npc_count"]):
                spec = npc_spec(world.world_seed, town.seed_path, i)
                data = {
                    "surname": spec.surname, "given": spec.given, "gender": spec.gender,
                    "age": spec.age, "occupation": spec.occupation, "traits": list(spec.traits),
                    "realm": spec.realm, "portrait": dict(spec.portrait),
                }
                person = world.add_entity("person", spec.name, data, npc_path(town.seed_path, i))
                world.relate(person, town_id, "located_in")
            world.update_data(town_id, populated=True)
    return [p for p in people_at(world, town_id) if not p.data.get("is_player")]


def region_of(world: World, town_id: int) -> Entity:
    return world.entity(world.targets(town_id, "located_in")[0])


def town_label(world: World, x: int, y: int, i: int) -> str:
    found = world.entity_by_seed(town_path(x, y, i))
    return found.name if found else town_spec(world.world_seed, x, y, i).name


def region_label(world: World, x: int, y: int) -> str:
    found = world.entity_by_seed(region_path(x, y))
    return found.name if found else region_spec(world.world_seed, x, y).name
