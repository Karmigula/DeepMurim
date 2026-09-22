import pytest

from world.db import World
from world.gen.materialize import ensure_town, people_at, populate, region_of, town_label
from world.gen.town import town_spec


@pytest.fixture
def world(tmp_path):
    w = World.create(tmp_path / "t.world", 42)
    yield w
    w.close()


def test_ensure_town_is_idempotent_and_linked(world):
    tid = ensure_town(world, 0, 0, 0)
    assert ensure_town(world, 0, 0, 0) == tid
    assert region_of(world, tid).data["x"] == 0
    assert world.entity(tid).name == town_spec(42, 0, 0, 0).name


def test_populate_once(world):
    tid = ensure_town(world, 0, 0, 0)
    people = populate(world, tid)
    assert len(people) == world.entity(tid).data["npc_count"]
    assert [p.id for p in populate(world, tid)] == [p.id for p in people]
    assert {"occupation", "portrait", "traits"} <= people[0].data.keys()


def test_database_wins_over_seed(world):
    tid = ensure_town(world, 0, 0, 0)
    people = populate(world, tid)
    other = ensure_town(world, 1, 0, 0)
    mover = people[0]
    world.unrelate(mover.id, "located_in")
    world.relate(mover.id, other, "located_in")
    assert mover.id not in [p.id for p in populate(world, tid)]
    world._conn.execute("update entities set name = 'Renamed' where id = ?", (tid,))
    assert town_label(world, 0, 0, 0) == "Renamed"


def test_same_seed_same_people(tmp_path):
    names = []
    for n in range(2):
        w = World.create(tmp_path / f"{n}.world", 42)
        names.append([p.name for p in populate(w, ensure_town(w, 0, 0, 0))])
        w.close()
    assert names[0] == names[1]


def test_people_at_excludes(world):
    tid = ensure_town(world, 0, 0, 0)
    people = populate(world, tid)
    assert people[0].id not in [p.id for p in people_at(world, tid, exclude=people[0].id)]
