import sqlite3

import pytest

from world.db import SCHEMA_VERSION, SaveError, World


@pytest.fixture
def world(tmp_path):
    w = World.create(tmp_path / "t.world", world_seed=42)
    yield w
    w.close()


def test_create_and_reopen(tmp_path):
    path = tmp_path / "a.world"
    World.create(path, 7).close()
    w = World.open(path)
    assert w.world_seed == 7 and w.time == 0
    w.close()


def test_create_refuses_existing(tmp_path):
    path = tmp_path / "a.world"
    World.create(path, 1).close()
    with pytest.raises(SaveError):
        World.create(path, 1)


def test_open_missing_corrupt_and_future(tmp_path):
    with pytest.raises(SaveError, match="No save"):
        World.open(tmp_path / "missing.world")
    junk = tmp_path / "junk.world"
    junk.write_bytes(b"this is not sqlite at all" * 100)
    with pytest.raises(SaveError):
        World.open(junk)
    future = tmp_path / "future.world"
    w = World.create(future, 1)
    w.set_meta("schema_version", SCHEMA_VERSION + 1)
    w.close()
    with pytest.raises(SaveError, match="version"):
        World.open(future)


def test_entities(world):
    eid = world.add_entity("person", "Li Wei", {"age": 30}, seed_path="p/1")
    assert world.entity(eid).data == {"age": 30}
    assert world.entity_by_seed("p/1").id == eid
    world.update_data(eid, age=31, scar=True)
    assert world.entity(eid).data == {"age": 31, "scar": True}
    assert [e.id for e in world.entities("person")] == [eid]
    assert world.entity(9999) is None
    with pytest.raises(sqlite3.IntegrityError):
        world.add_entity("person", "Dup", seed_path="p/1")


def test_relations(world):
    a, b, c = (world.add_entity("x", n) for n in "abc")
    world.relate(a, b, "located_in")
    world.relate(a, b, "located_in", value=2.0)  # upsert, no duplicate
    world.relate(c, b, "located_in")
    assert world.targets(a, "located_in") == [b]
    assert world.sources(b, "located_in") == [a, c]
    world.unrelate(a, "located_in")
    assert world.targets(a, "located_in") == []


def test_transaction_rolls_back(world):
    with pytest.raises(RuntimeError):
        with world.transaction():
            world.add_entity("ghost", "Nobody")
            with world.transaction():  # nested joins the outer one
                world.add_entity("ghost", "Nobody2")
            raise RuntimeError
    assert world.entities("ghost") == []


def test_chronicle_and_memories(world):
    a, b, c = (world.add_entity("person", n) for n in "abc")
    e1 = world.append_chronicle("met", (a, b), None, {}, 1.0)
    e2 = world.append_chronicle("met", (c, b), None, {}, 1.0)
    world.add_memory(b, e1, "curious", 0.3)
    world.add_memory(b, e2, "wary", 0.5, indelible=True)
    assert [m.event.id for m in world.memories(b)] == [e1, e2]
    assert [m.event.id for m in world.memories(b, about=a)] == [e1]
    assert world.memories(b, about=c)[0].indelible is True
    assert [e.id for e in world.chronicle_about(b)] == [e2, e1]


def test_digest_changes_with_state(world):
    before = world.digest()
    world.add_entity("x", "y")
    assert world.digest() != before
