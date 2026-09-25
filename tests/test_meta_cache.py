import pytest

from world.db import World


@pytest.fixture
def world(tmp_path):
    w = World.create(tmp_path / "m.world", 5)
    yield w
    w.close()


def test_the_clock_is_read_from_memory_after_the_first_time(world, monkeypatch):
    world.set_time(40)
    reads = []
    real = world._conn

    class Counting:
        def execute(self, sql, *args):
            reads.append(sql)
            return real.execute(sql, *args)
    monkeypatch.setattr(world, "_conn", Counting())
    assert world.time == 40 and world.time == 40 and world.world_seed == 5
    assert not any("from meta" in sql for sql in reads)
    monkeypatch.setattr(world, "_conn", real)


def test_a_rolled_back_clock_is_forgotten(world):
    world.set_time(40)
    with pytest.raises(RuntimeError):
        with world.transaction():
            world.set_time(99)
            raise RuntimeError("the turn fails")
    assert world.time == 40


def test_a_listing_by_kind_is_served_from_memory(world):
    ids = [world.add_entity("thing", f"Jar {i}", {"n": i}) for i in range(3)]
    first = world.entities("thing")
    again = world.entities("thing")
    assert [e.id for e in again] == ids and all(a is b for a, b in zip(first, again))  # decoded once
    world.update_data(ids[1], n=9)
    assert [e.data["n"] for e in world.entities("thing")] == [0, 9, 2]


def test_a_list_is_never_kept_in_memory(world):
    world.set_meta("index", [[1, 2]])
    world.get_meta("index")[0].append(3)  # a caller that edits what it got back
    assert world.get_meta("index") == [[1, 2]]
