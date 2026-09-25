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


def test_non_json_version_is_a_save_error(tmp_path):
    path = tmp_path / "odd.world"
    w = World.create(path, 1)
    w._conn.execute("update meta set value = 'not json' where key = 'schema_version'")
    w.close()
    with pytest.raises(SaveError):
        World.open(path)


def test_a_save_syncs_at_checkpoints_not_every_commit(tmp_path):
    """WAL with synchronous = NORMAL: a crash of the game loses nothing, a power cut at most the last turn,
    and the file is never corrupted; each turn no longer waits on the disk (phase 4e)."""
    path = tmp_path / "s.world"
    created = World.create(path, 3)
    assert created._conn.execute("pragma synchronous").fetchone()[0] == 1  # NORMAL
    created.close()
    opened = World.open(path)
    assert opened._conn.execute("pragma synchronous").fetchone()[0] == 1
    assert opened._conn.execute("pragma journal_mode").fetchone()[0] == "wal"
    opened.close()


def test_a_read_entity_is_kept_until_it_changes(tmp_path):
    w = World.create(tmp_path / "c.world", 1)
    eid = w.add_entity("thing", "Jar", {"full": True})
    first = w.entity(eid)
    assert w.entity(eid) is first  # served from memory, not decoded again
    w.update_data(eid, full=False)
    assert w.entity(eid).data["full"] is False and first.data["full"] is True  # a new snapshot; the old one stands
    w.close()


def test_a_rollback_forgets_what_was_cached(tmp_path):
    w = World.create(tmp_path / "r.world", 1)
    eid = w.add_entity("thing", "Jar", {"full": True})
    w.entity(eid)
    with pytest.raises(RuntimeError):
        with w.transaction():
            w.update_data(eid, full=False)
            raise RuntimeError("the turn fails")
    assert w.entity(eid).data["full"] is True
    w.close()


def test_dropped_entities_are_not_served_from_memory(tmp_path):
    w = World.create(tmp_path / "d.world", 1)
    eid = w.add_entity("price_event", "Glut", {"until": 3})
    w.entity(eid)
    w.drop_entities_until("price_event", "until", 5)
    assert w.entity(eid) is None
    w.close()


def test_an_entity_changed_in_memory_but_never_saved_is_caught(tmp_path):
    w = World.create(tmp_path / "m.world", 1)
    eid = w.add_entity("thing", "Jar", {"full": True})
    w.entity(eid).data["full"] = False  # a bug: edited in place, never written
    assert w.cache_drift() == [f"entity #{eid} (Jar) was changed in memory but not saved"]
    w.close()


def test_the_entity_cache_is_bounded(tmp_path, monkeypatch):
    import world.db as db
    monkeypatch.setattr(db, "ENTITY_CACHE", 3)
    w = World.create(tmp_path / "b.world", 1)
    ids = [w.add_entity("thing", f"Jar {i}", {}) for i in range(5)]
    first = w.entity(ids[0])
    for eid in ids[1:]:
        w.entity(eid)
    assert len(w._entities) == 3 and w.entity(ids[0]) is not first  # the oldest was let go and read again
    w.close()


def test_the_debug_rules_catch_an_entity_edited_in_memory(tmp_path):
    from debug.invariants import check_world
    w = World.create(tmp_path / "rules.world", 1)
    eid = w.add_entity("thing", "Jar", {"full": True})
    w.entity(eid).data["full"] = False
    assert any("changed in memory but not saved" in p for p in check_world(w))
    w.close()


def test_the_drift_check_looks_only_at_what_was_read_since_the_last_one(tmp_path, monkeypatch):
    w = World.create(tmp_path / "t.world", 1)
    ids = [w.add_entity("thing", f"Jar {i}", {}) for i in range(50)]
    for eid in ids:
        w.entity(eid)
    w.cache_drift()
    w.entity(ids[0])
    reads = []
    real = w._conn

    class Counting:
        def execute(self, sql, *args):
            reads.append(sql)
            return real.execute(sql, *args)
    monkeypatch.setattr(w, "_conn", Counting())
    assert w.cache_drift() == [] and len(reads) == 1  # one entity handed out since: one row read, not fifty
    monkeypatch.setattr(w, "_conn", real)
    w.close()
