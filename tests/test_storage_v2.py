import sqlite3

import pytest

from engine.game import Action, Game
from systems.memory import HALF_LIFE, effective_intensity
from world.db import SCHEMA_VERSION, World, variant_key
from world.events import LISTENERS, Event, Witness, commit, listen

V1_SHAPE = """
create table m1 as select owner, event_id, feeling, intensity, indelible from memories;
drop table memories;
create table memories(owner integer not null, event_id integer not null, feeling text not null,
    intensity real not null, indelible integer not null default 0, primary key(owner, event_id));
insert into memories select * from m1;
drop table m1;
drop table facts;
create table facts(id integer primary key, subject integer not null, predicate text not null,
    object text not null, time integer not null, source_event integer);
drop table beliefs;
create table beliefs(knower integer not null, fact_id integer not null, variant text not null default '{}',
    source integer, confidence real not null, learned_at integer not null, primary key(knower, fact_id));
update meta set value = '1' where key = 'schema_version';
"""


@pytest.fixture
def world(tmp_path):
    w = World.create(tmp_path / "w.world", 5)
    yield w
    w.close()


def test_new_worlds_are_version_2(world):
    assert SCHEMA_VERSION == 2 and world.get_meta("schema_version") == 2


def test_facts_round_trip(world):
    with world.transaction():
        fid = world.add_fact(3, "killed", 4, place=9, weight=3.0, data={"variant": {"predicate": "killed"}}, source_event=7)
        lie = world.add_fact(3, "robbed", None, is_true=False)
    fact = world.fact(fid)
    assert (fact.subject, fact.predicate, fact.object, fact.place, fact.weight, fact.is_true) == (3, "killed", 4, 9, 3.0, True)
    assert fact.variant == {"predicate": "killed"} and fact.source_event == 7
    assert world.fact(lie).object is None and world.fact(lie).is_true is False
    assert [f.id for f in world.facts(is_true=False)] == [lie]
    assert [f.id for f in world.facts(subject=3, predicate="killed")] == [fid]


def test_a_knower_can_hold_two_versions_and_keeps_the_surer_one(world):
    with world.transaction():
        fid = world.add_fact(1, "killed", 2)
        assert world.upsert_belief(10, fid, {"count": 1}, None, 0.5, 1, "gossip") is True
        assert world.upsert_belief(10, fid, {"count": 3}, None, 0.4, 2, "distance") is True
        assert world.upsert_belief(10, fid, {"count": 1}, 5, 0.9, 0, "witness") is False
    beliefs = {b.variant["count"]: b for b in world.beliefs(10)}
    assert set(beliefs) == {1, 3}
    assert (beliefs[1].confidence, beliefs[1].hops, beliefs[1].source) == (0.9, 0, 5)
    assert beliefs[1].variant_key == variant_key({"count": 1})
    assert [f.id for _, f in world.known_facts(10)] == [fid, fid]
    assert [b.knower for b in world.believers(fid)] == [10, 10]
    assert [f.id for f in world.facts_unknown_to(11, until=world.time)] == [fid]
    assert world.facts_unknown_to(10, until=world.time) == []
    assert len(world.all_beliefs()) == 2


def test_inherited_memories_remember_where_they_came_from(world):
    with world.transaction():
        eid = world.append_chronicle("died", (1, 2), None, {}, 1.0)
        world.add_memory(3, eid, "grief", 1.0, True, inherited_from=2)
        world.add_memory(3, eid, "grief", 1.0, True, inherited_from=2, ignore_existing=True)
    [m] = world.memories(3)
    assert m.inherited_from == 2 and m.indelible
    assert world.witnesses_of(eid) == [3]
    assert world.chronicle_entry(eid).kind == "died"
    assert world.chronicle_entry(99999) is None
    assert [x.owner for x in world.memories_with_feeling("grief")] == [3]
    assert [x.owner for x in world.memories_inherited()] == [3]


def test_acquaintances_are_everyone_met_most_recent_first(world):
    with world.transaction():
        for other in (5, 6, 5, 7):
            world.append_chronicle("met", (1, other), None, {}, 1.0)
    assert world.acquaintances(1) == [7, 5, 6]


def test_commit_makes_grave_feelings_indelible_and_calls_listeners(world):
    seen = []
    listen("test_kind")(lambda w, event, event_id: seen.append((event.kind, event_id)))
    try:
        [eid] = commit(world, [Event("test_kind", (1, 2), None, {}, witnesses=(Witness(2, "hatred", 0.5),))])
    finally:
        LISTENERS.pop("test_kind")
    assert seen == [("test_kind", eid)]
    assert world.memories(2)[0].indelible


def test_memories_fade_by_half_each_season_unless_indelible(world):
    with world.transaction():
        eid = world.append_chronicle("met", (1, 2), None, {}, 1.0)
        world.add_memory(2, eid, "curious", 0.8)
        world.add_memory(3, eid, "hatred", 0.8, True)
    fading, lasting = world.memories(2)[0], world.memories(3)[0]
    assert effective_intensity(fading, HALF_LIFE) == pytest.approx(0.4)
    assert effective_intensity(fading, 2 * HALF_LIFE) == pytest.approx(0.2)
    assert effective_intensity(lasting, 10 * HALF_LIFE) == 0.8


def test_a_version_1_save_is_upgraded_and_plays_on(tmp_path):
    path = tmp_path / "old.world"
    g = Game.new(path, "Old", world_seed=5)
    talk = next(c for c in g.start().all_choices if c.action.verb == "talk")
    g.perform(talk.action)
    remembered = len(g.world.memories(talk.action.target))
    g.close()
    conn = sqlite3.connect(path)
    conn.executescript(V1_SHAPE)
    conn.close()
    g = Game.load(path)
    assert g.world.get_meta("schema_version") == 2
    assert len(g.world.memories(talk.action.target)) == remembered
    assert g.perform(Action("look")).lines
    with g.world.transaction():
        fid = g.world.add_fact(1, "killed", 2, place=g.place.id)
        g.world.upsert_belief(g.place.id, fid, {"a": 1}, None, 0.8, 1, "gossip")
    assert g.world.beliefs(g.place.id)[0].channel == "gossip"
    g.close()
