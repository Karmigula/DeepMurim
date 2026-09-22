import pytest

from systems.time import advance, format_date, format_season_year, season_of
from world.db import World
from world.events import EFFECTS, Event, Witness, commit, effect


@pytest.fixture
def world(tmp_path):
    w = World.create(tmp_path / "t.world", 1)
    yield w
    w.close()


def test_commit_writes_chronicle_and_memories(world):
    a, b = world.add_entity("person", "A"), world.add_entity("person", "B")
    [eid] = commit(world, [Event("met", (a, b), None, {"x": 1}, witnesses=(Witness(b, "curious", 0.3),))])
    assert world.chronicle_about(a)[0].id == eid
    assert world.memories(b)[0].feeling == "curious"


def test_effect_runs_and_failure_rolls_back(world):
    calls = []

    @effect("test_ok")
    def _ok(w, ev):
        calls.append(ev.kind)

    @effect("test_boom")
    def _boom(w, ev):
        raise RuntimeError("boom")

    try:
        a = world.add_entity("person", "A")
        commit(world, [Event("test_ok", (a,))])
        assert calls == ["test_ok"]
        with pytest.raises(RuntimeError):
            commit(world, [Event("test_ok", (a,)), Event("test_boom", (a,))])
        assert len(world.chronicle_about(a)) == 1
    finally:
        EFFECTS.pop("test_ok", None)
        EFFECTS.pop("test_boom", None)


def test_time_formatting(world):
    assert format_date(0) == "Year 1, Spring day 1, morning"
    one_season_and_a_bit = 90 * 4 + 4 + 2
    assert format_date(one_season_and_a_bit) == "Year 1, Summer day 2, dusk"
    assert format_date(360 * 4) == "Year 2, Spring day 1, morning"
    assert season_of(90 * 4) == "summer"
    assert format_season_year(0) == "the spring of year 1"
    advance(world, 5)
    assert world.time == 5
