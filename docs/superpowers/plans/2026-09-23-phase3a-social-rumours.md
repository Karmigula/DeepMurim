# Phase 3a: Social Memory, Rumours, Reputation, Masks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** What the player does becomes facts. Facts travel as rumours that change as they are retold, and towns and people react to what they believe. The player can kill, lie and wear masks.

**Architecture:**
- Save format version 2 adds a `facts` table and a `beliefs` table, with a migration from version 1.
- Event *listeners* write facts from committed events. Fact hooks then spread beliefs through the witness, town-gossip and kin channels.
- `catch_up` spreads facts to other towns lazily, by distance, when the player arrives.
- Attitude and reputation are computed when they are read, and never stored.
- Masks use a persona entity. The engine stamps `data["as"]` on the player's events while a mask is worn. Everything that knows something reads through `systems/beliefs.py`.

**Tech Stack:** Python 3.12, SQLite (stdlib `sqlite3`), pygame-ce (unchanged), pytest.

**Spec:** `docs/superpowers/specs/2026-09-23-phase3a-social-rumours-design.md`. The parent spec is `docs/superpowers/specs/2026-09-22-deepmurim-design.md`.

## Global Constraints

- The chronicle stays ground truth: event actors are always the true ids. Anything anyone *knows* goes through beliefs.
- The UI, procedural narration and briefs read only the player's beliefs. They never read `facts.is_true`, `persona.data["of"]` (except to check whether the reader *is* the wearer) or other people's memories.
- Briefs have at most 6 facts and at most 1,200 characters, and contain no entity ids (parent §6.0).
- A menu shows at most 9 choices. Extra choices go into `Turn.extra` so typed commands still reach them.
- Every new event kind has a grammar table (a debug rule checks this). Every narrative sentence starts with a capital letter.
- Each seeded roll uses `rng_for(world.world_seed, <path>)`, with the paths given in the spec.
- Time is counted in watches, 4 per day. `HALF_LIFE = 360`, `HOP_WATCHES = 8`.
- Existing tests stay green. A test that assumed the 2b menus or verdict set is updated inside the task's patch script as a recorded ruling.
- Test command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.

## Review Focus

1. **Killing someone mid-conversation or while they are listed on screen.** The dead must disappear from menus, from `people_at`, from challenges and from road encounters, including roamers whose seed slot is reused. Task 5 pins this with `test_a_dead_roamer_is_never_met_again`.
2. **A masked player talking to someone who knows their face.** The greeting must treat them as a stranger unless they recognise the player. Task 8 pins this with `test_a_masked_player_is_greeted_as_a_stranger`.
3. **Old saves.** A version 1 save from 2b must open, keep its memories, and play on. Task 1 pins this with `test_a_version_1_save_is_upgraded_and_plays_on`.
4. **Menus crowding past 9** once news, tell, spar, challenge, learn and browse all apply. Task 7 pins this with `test_the_conversation_menu_never_shows_more_than_nine`.
5. **Names the player never learned leaking into text**, such as kin, far-off victims or the true face behind a persona. Task 10 pins this with the `check_names` rule, which runs in every fuzz turn.

## File map

| File | Status | Responsibility |
|---|---|---|
| `world/db.py` | modify | Schema v2, migration, `Fact`, `Belief`, fact and belief queries, `inherited_from` |
| `world/events.py` | modify | `listen` registry (listeners get the event id); `INDELIBLE_FEELINGS` forced on witnesses |
| `systems/memory.py` | create | `effective_intensity`, `HALF_LIFE`, `INDELIBLE` |
| `systems/beliefs.py` | create | `believe`, `knowledge_of`, confidence, `knows_identity`, `appears_as`, `apparent_to`, `identities`, `known_people` |
| `systems/facts.py` | create | Predicates, weights, `record_fact`, `ON_FACT` hooks, listeners that turn fights into facts |
| `systems/rumours.py` | create | Channels, `mutate`/`retell`, `catch_up`, `pick_news`, `news_about`, hearing, telling, exposure |
| `systems/attitude.py` | create | `attitude`, `afraid` |
| `systems/reputation.py` | create | `reputation` (renown, path, epithet) |
| `systems/kin.py` | create | `ensure_kin`, `kin_of`, `died` effect and inheritance, kin channel, `avengers_for` |
| `systems/masks.py` | create | Mask items, personas, wearing, recognition |
| `systems/duel.py`, `systems/encounters.py`, `systems/learning.py`, `systems/talk.py` | modify | Kill, left for dead, fear, avengers, rivals, backing off, dealings, masked greetings |
| `engine/hooks.py`, `engine/game.py`, `engine/fight.py`, `engine/roads.py`, `engine/dealings.py`, `engine/commands.py`, `engine/sheet.py` | modify | New hooks and verbs, and surfacing reputation |
| `engine/gossip.py`, `engine/masks.py` | create | Mixins for gossip and masks |
| `narrate/gossip_text.py`, `narrate/mask_text.py` | create | Outcome builders, `rumour_text`, summaries |
| `narrate/grammar/gossip.toml` | create | Grammar for the new events |
| `narrate/brief.py`, `narrate/procedural.py`, `narrate/combat_text.py`, `narrate/road_text.py`, `narrate/outcomes.py` | modify | Attitude facts, grammar keys, and kill, avenger and backing-off lines |
| `debug/invariants.py`, `docs/debugging.md` | modify | Knowledge and name rules |

Edits to existing files ship as `.patches/3a_taskN.py` scripts (git-ignored, as in 2b). Each edit must match exactly once, or the script stops.

---

### Task 1: Save format v2, listeners, fading memory

**Files:**
- Modify: `world/db.py`, `world/events.py` (via `.patches/3a_task1.py`)
- Create: `systems/memory.py`
- Test: `tests/test_storage_v2.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `world.db`:
    - `SCHEMA_VERSION = 2`.
    - `variant_key(variant: dict) -> str`.
    - Dataclass `Fact(id, subject, predicate, object: int|None, time, source_event, place, weight, is_true: bool, data)`, with property `.variant`.
    - Dataclass `Belief(knower, fact_id, variant_key, variant, source, confidence, learned_at, hops, channel)`.
    - `Memory` gains `inherited_from: int | None = None`.
  - `World` methods:
    - Facts: `add_fact(subject, predicate, obj, *, place=None, weight=1.0, is_true=True, data=None, source_event=None) -> int`, `fact(id)`, `facts(predicate=None, subject=None, is_true=None)`, `facts_unknown_to(knower, until)`.
    - Beliefs: `upsert_belief(knower, fact_id, variant, source, confidence, hops, channel) -> bool` (True if new), `beliefs(knower)`, `believers(fact_id)`, `all_beliefs()`, `known_facts(knower) -> list[tuple[Belief, Fact]]`.
    - Chronicle: `chronicle_entry(id)`, `acquaintances(entity) -> list[int]` (everyone sharing any chronicle entry, most recent first).
    - Memories: `witnesses_of(event_id) -> list[int]`, `memories_with_feeling(feeling)`, `memories_inherited()`, `add_memory(..., inherited_from=None, ignore_existing=False)`.
  - `world.events`: `INDELIBLE_FEELINGS`, `LISTENERS`, `listen(kind)`. A listener has the signature `(world, event, event_id) -> None` and runs after the event's effect.
  - `systems.memory`: `HALF_LIFE = 360`, `INDELIBLE`, `effective_intensity(memory, now) -> float`.

- [ ] **Step 1: Write the failing test** — `tests/test_storage_v2.py`
```python
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
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_storage_v2.py -q -p no:cacheprovider`
Expected: the tests fail with `ImportError: cannot import name 'effective_intensity'` (module `systems.memory` is missing) or `cannot import name 'variant_key'`.

- [ ] **Step 3: Write `systems/memory.py`** — `systems/memory.py`
```python
"""How memories fade (phase 3a spec §3.1). Nothing is deleted; strength is worked out when read."""

from world.events import INDELIBLE_FEELINGS

HALF_LIFE = 360  # watches: one season
INDELIBLE = INDELIBLE_FEELINGS


def effective_intensity(memory, now: int) -> float:
    """How strongly a memory is felt at `now`. Indelible memories never fade."""
    if memory.indelible:
        return memory.intensity
    age = max(0, now - memory.event.time)
    return memory.intensity * 0.5 ** (age / HALF_LIFE)
```

- [ ] **Step 4: Edit the storage and event modules** — `.patches/3a_task1.py`
```python
"""Task 1 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


DB = "world/db.py"
edit(DB, "SCHEMA_VERSION = 1\n", "SCHEMA_VERSION = 2\n")
edit(DB, '''create table if not exists memories(
    owner integer not null, event_id integer not null, feeling text not null,
    intensity real not null, indelible integer not null default 0,
    primary key(owner, event_id));
create table if not exists facts(
    id integer primary key, subject integer not null, predicate text not null,
    object text not null, time integer not null, source_event integer);
create table if not exists beliefs(
    knower integer not null, fact_id integer not null, variant text not null default '{}',
    source integer, confidence real not null, learned_at integer not null,
    primary key(knower, fact_id));
"""
''', '''create table if not exists memories(
    owner integer not null, event_id integer not null, feeling text not null,
    intensity real not null, indelible integer not null default 0, inherited_from integer,
    primary key(owner, event_id));
create table if not exists facts(
    id integer primary key, subject integer not null, predicate text not null,
    object text not null, time integer not null, source_event integer,
    place integer, weight real not null default 1, is_true integer not null default 1,
    data text not null default '{}');
create table if not exists beliefs(
    knower integer not null, fact_id integer not null, variant_key text not null,
    variant text not null default '{}', source integer, confidence real not null,
    learned_at integer not null, hops integer not null default 0, channel text not null default 'witness',
    primary key(knower, fact_id, variant_key));
"""

INDEXES = (
    "create index if not exists facts_subject on facts(subject)",
    "create index if not exists facts_time on facts(time)",
    "create index if not exists facts_place on facts(place)",
    "create index if not exists beliefs_fact on beliefs(fact_id)",
    "create index if not exists beliefs_knower on beliefs(knower)",
    "create index if not exists memories_feeling on memories(feeling)",
)
SCHEMA += ";\\n".join(INDEXES) + ";\\n"

# Statements that turn version N into N + 1, run in one transaction by World.open.
MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: (
        "alter table memories add column inherited_from integer",
        "alter table facts add column place integer",
        "alter table facts add column weight real not null default 1",
        "alter table facts add column is_true integer not null default 1",
        "alter table facts add column data text not null default '{}'",
        "create table beliefs_v2(knower integer not null, fact_id integer not null, variant_key text not null, "
        "variant text not null default '{}', source integer, confidence real not null, learned_at integer not null, "
        "hops integer not null default 0, channel text not null default 'witness', "
        "primary key(knower, fact_id, variant_key))",
        "insert into beliefs_v2(knower, fact_id, variant_key, variant, source, confidence, learned_at) "
        "select knower, fact_id, '', variant, source, confidence, learned_at from beliefs",
        "drop table beliefs",
        "alter table beliefs_v2 rename to beliefs",
    ) + INDEXES,
}
''')
edit(DB, '''_ENTRY_COLUMNS = "c.id, c.time, c.kind, c.actors, c.place, c.data, c.weight"
''', '''_ENTRY_COLUMNS = "c.id, c.time, c.kind, c.actors, c.place, c.data, c.weight"
_MEMORY_COLUMNS = "m.owner, m.feeling, m.intensity, m.indelible, m.inherited_from"
_FACT_COLUMNS = "f.id, f.subject, f.predicate, f.object, f.time, f.source_event, f.place, f.weight, f.is_true, f.data"
_BELIEF_COLUMNS = "b.knower, b.fact_id, b.variant_key, b.variant, b.source, b.confidence, b.learned_at, b.hops, b.channel"
''')
edit(DB, '''    feeling: str
    intensity: float
    indelible: bool


def _entry(row) -> ChronicleEntry:''', '''    feeling: str
    intensity: float
    indelible: bool
    inherited_from: int | None = None


@dataclass(frozen=True)
class Fact:
    """Ground truth. Only the knowledge layer (systems/beliefs.py) reads it for anything shown."""
    id: int
    subject: int
    predicate: str
    object: int | None
    time: int
    source_event: int | None
    place: int | None
    weight: float
    is_true: bool
    data: dict

    @property
    def variant(self) -> dict:
        """The story as it truly happened (as it looked to those present)."""
        return self.data.get("variant", {})


@dataclass(frozen=True)
class Belief:
    knower: int
    fact_id: int
    variant_key: str
    variant: dict
    source: int | None
    confidence: float
    learned_at: int
    hops: int
    channel: str


def variant_key(variant: dict) -> str:
    """A short stable key, so one knower can hold several versions of the same fact."""
    return hashlib.blake2b(json.dumps(variant, sort_keys=True).encode(), digest_size=6).hexdigest()


def _memory(row) -> Memory:
    return Memory(row[0], _entry(row[5:]), row[1], row[2], bool(row[3]), row[4])


def _fact(row) -> Fact:
    obj = row[3]
    return Fact(row[0], row[1], row[2], int(obj) if obj not in ("", None) else None, row[4], row[5], row[6],
                row[7], bool(row[8]), json.loads(row[9]))


def _belief(row) -> Belief:
    return Belief(row[0], row[1], row[2], json.loads(row[3]), row[4], row[5], row[6], row[7], row[8])


def _entry(row) -> ChronicleEntry:''')
edit(DB, '''        if version != SCHEMA_VERSION:
            conn.close()
            raise SaveError(f"{path.name} has save version {version}; this game reads version {SCHEMA_VERSION}")''',
     '''        upgradable = isinstance(version, int) and not isinstance(version, bool) and version in MIGRATIONS
        if version != SCHEMA_VERSION and not upgradable:
            conn.close()
            raise SaveError(f"{path.name} has save version {version}; this game reads version {SCHEMA_VERSION}")''')
edit(DB, '''        if problem != "ok":
            conn.close()
            raise SaveError(f"{path.name} is damaged ({problem})")
        return cls(conn, path)''', '''        if problem != "ok":
            conn.close()
            raise SaveError(f"{path.name} is damaged ({problem})")
        world = cls(conn, path)
        if version != SCHEMA_VERSION:
            world._migrate(version)
        return world

    def _migrate(self, version: int) -> None:
        """Bring an older save up to SCHEMA_VERSION, all or nothing."""
        with self.transaction():
            while version < SCHEMA_VERSION:
                for statement in MIGRATIONS[version]:
                    self._conn.execute(statement)
                version += 1
            self.set_meta("schema_version", SCHEMA_VERSION)''')
edit(DB, '''    def add_memory(self, owner: int, event_id: int, feeling: str, intensity: float, indelible: bool = False) -> None:
        self._conn.execute(
            "insert into memories(owner, event_id, feeling, intensity, indelible) values(?, ?, ?, ?, ?)",
            (owner, event_id, feeling, intensity, int(indelible)),
        )

    def memories(self, owner: int, about: int | None = None) -> list[Memory]:
        sql = (
            f"select m.owner, m.feeling, m.intensity, m.indelible, {_ENTRY_COLUMNS} "
            "from memories m join chronicle c on c.id = m.event_id where m.owner = ?"
        )
        params: list = [owner]
        if about is not None:
            sql += " and exists(select 1 from json_each(c.actors) where json_each.value = ?)"
            params.append(about)
        rows = self._conn.execute(sql + " order by c.id", params)
        return [Memory(row[0], _entry(row[4:]), row[1], row[2], bool(row[3])) for row in rows]''',
     '''    def add_memory(self, owner: int, event_id: int, feeling: str, intensity: float, indelible: bool = False,
                   inherited_from: int | None = None, ignore_existing: bool = False) -> None:
        verb = "insert or ignore" if ignore_existing else "insert"
        self._conn.execute(
            f"{verb} into memories(owner, event_id, feeling, intensity, indelible, inherited_from) values(?, ?, ?, ?, ?, ?)",
            (owner, event_id, feeling, intensity, int(indelible), inherited_from),
        )

    def memories(self, owner: int, about: int | None = None) -> list[Memory]:
        sql = (
            f"select {_MEMORY_COLUMNS}, {_ENTRY_COLUMNS} "
            "from memories m join chronicle c on c.id = m.event_id where m.owner = ?"
        )
        params: list = [owner]
        if about is not None:
            sql += " and exists(select 1 from json_each(c.actors) where json_each.value = ?)"
            params.append(about)
        rows = self._conn.execute(sql + " order by c.id", params)
        return [_memory(row) for row in rows]

    def memories_with_feeling(self, feeling: str) -> list[Memory]:
        rows = self._conn.execute(
            f"select {_MEMORY_COLUMNS}, {_ENTRY_COLUMNS} from memories m join chronicle c on c.id = m.event_id "
            "where m.feeling = ? order by c.id, m.owner", (feeling,))
        return [_memory(row) for row in rows]

    def memories_inherited(self) -> list[Memory]:
        rows = self._conn.execute(
            f"select {_MEMORY_COLUMNS}, {_ENTRY_COLUMNS} from memories m join chronicle c on c.id = m.event_id "
            "where m.inherited_from is not null order by c.id, m.owner")
        return [_memory(row) for row in rows]

    def witnesses_of(self, event_id: int) -> list[int]:
        """Everyone who holds a memory of this event."""
        rows = self._conn.execute("select owner from memories where event_id = ? order by owner", (event_id,))
        return [row[0] for row in rows]

    def acquaintances(self, entity_id: int) -> list[int]:
        """Everyone who shares any chronicle entry with this entity, most recent first."""
        rows = self._conn.execute(
            "select other.value, max(c.id) as last from chronicle c, json_each(c.actors) me, json_each(c.actors) other "
            "where me.value = ? and other.value != ? group by other.value order by last desc", (entity_id, entity_id))
        return [row[0] for row in rows]

    def chronicle_entry(self, event_id) -> ChronicleEntry | None:
        if not isinstance(event_id, int):
            return None
        row = self._conn.execute(f"select {_ENTRY_COLUMNS} from chronicle c where c.id = ?", (event_id,)).fetchone()
        return _entry(row) if row else None

    # --- facts & beliefs ------------------------------------------------------
    def add_fact(self, subject: int, predicate: str, obj: int | None, *, place: int | None = None,
                 weight: float = 1.0, is_true: bool = True, data: dict | None = None,
                 source_event: int | None = None) -> int:
        cursor = self._conn.execute(
            "insert into facts(subject, predicate, object, time, source_event, place, weight, is_true, data) "
            "values(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (subject, predicate, "" if obj is None else str(obj), self.time, source_event, place, weight,
             int(is_true), json.dumps(data or {})),
        )
        return cursor.lastrowid

    def fact(self, fact_id: int) -> Fact | None:
        row = self._conn.execute(f"select {_FACT_COLUMNS} from facts f where f.id = ?", (fact_id,)).fetchone()
        return _fact(row) if row else None

    def facts(self, predicate: str | None = None, subject: int | None = None, is_true: bool | None = None) -> list[Fact]:
        sql, params = f"select {_FACT_COLUMNS} from facts f where 1 = 1", []
        if predicate is not None:
            sql += " and f.predicate = ?"
            params.append(predicate)
        if subject is not None:
            sql += " and f.subject = ?"
            params.append(subject)
        if is_true is not None:
            sql += " and f.is_true = ?"
            params.append(int(is_true))
        return [_fact(row) for row in self._conn.execute(sql + " order by f.id", params)]

    def facts_unknown_to(self, knower: int, until: int) -> list[Fact]:
        """Facts no older than `until` that this knower holds no version of."""
        rows = self._conn.execute(
            f"select {_FACT_COLUMNS} from facts f where f.time <= ? and not exists("
            "select 1 from beliefs b where b.knower = ? and b.fact_id = f.id) order by f.id", (until, knower))
        return [_fact(row) for row in rows]

    def upsert_belief(self, knower: int, fact_id: int, variant: dict, source: int | None, confidence: float,
                      hops: int, channel: str) -> bool:
        """Add a belief; a version already held keeps whichever telling was surer. True if it was new."""
        key = variant_key(variant)
        row = self._conn.execute(
            "select confidence from beliefs where knower = ? and fact_id = ? and variant_key = ?",
            (knower, fact_id, key)).fetchone()
        if row is None:
            self._conn.execute(
                "insert into beliefs(knower, fact_id, variant_key, variant, source, confidence, learned_at, hops, channel) "
                "values(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (knower, fact_id, key, json.dumps(variant, sort_keys=True), source, confidence, self.time, hops, channel))
            return True
        if confidence > row[0]:
            self._conn.execute(
                "update beliefs set confidence = ?, source = ?, hops = ?, channel = ? "
                "where knower = ? and fact_id = ? and variant_key = ?",
                (confidence, source, hops, channel, knower, fact_id, key))
        return False

    def beliefs(self, knower: int) -> list[Belief]:
        rows = self._conn.execute(
            f"select {_BELIEF_COLUMNS} from beliefs b where b.knower = ? order by b.learned_at, b.fact_id, b.variant_key",
            (knower,))
        return [_belief(row) for row in rows]

    def believers(self, fact_id: int) -> list[Belief]:
        rows = self._conn.execute(
            f"select {_BELIEF_COLUMNS} from beliefs b where b.fact_id = ? order by b.knower, b.variant_key", (fact_id,))
        return [_belief(row) for row in rows]

    def all_beliefs(self) -> list[Belief]:
        rows = self._conn.execute(f"select {_BELIEF_COLUMNS} from beliefs b order by b.knower, b.fact_id")
        return [_belief(row) for row in rows]

    def known_facts(self, knower: int) -> list[tuple[Belief, Fact]]:
        """Each belief this knower holds, with its fact, oldest learned first."""
        rows = self._conn.execute(
            f"select {_BELIEF_COLUMNS}, {_FACT_COLUMNS} from beliefs b join facts f on f.id = b.fact_id "
            "where b.knower = ? order by b.learned_at, b.fact_id, b.variant_key", (knower,))
        return [(_belief(row[:9]), _fact(row[9:])) for row in rows]''')

EV = "world/events.py"
edit(EV, '''Effect = Callable[[World, Event], None]
EFFECTS: dict[str, Effect] = {}
''', '''Effect = Callable[[World, Event], None]
EFFECTS: dict[str, Effect] = {}
Listener = Callable[[World, Event, int], None]
LISTENERS: dict[str, list[Listener]] = {}
INDELIBLE_FEELINGS = frozenset({"hatred", "grief", "saved", "betrayed"})  # never fade (phase 3a spec §3.1)
''')
edit(EV, '''    return register


def commit(''', '''    return register


def listen(kind: str) -> Callable[[Listener], Listener]:
    """Register a reaction to an event kind, run after its effect, given the new event's id.

    Several listeners can watch one kind (facts, kin and masks each add their own).
    """
    def register(fn: Listener) -> Listener:
        LISTENERS.setdefault(kind, []).append(fn)
        return fn
    return register


def commit(''')
edit(EV, '''                world.add_memory(witness.owner, event_id, witness.feeling, witness.intensity, witness.indelible)
            apply = EFFECTS.get(event.kind)
            if apply is not None:
                apply(world, event)
            ids.append(event_id)''', '''                lasting = witness.indelible or witness.feeling in INDELIBLE_FEELINGS
                world.add_memory(witness.owner, event_id, witness.feeling, witness.intensity, lasting)
            apply = EFFECTS.get(event.kind)
            if apply is not None:
                apply(world, event)
            for react in LISTENERS.get(event.kind, ()):
                react(world, event, event_id)
            ids.append(event_id)''')
print("task 1 edits applied")
```

- [ ] **Step 5: Run the test to see it pass, then run the whole suite**

Run: `.venv/Scripts/python.exe .patches/3a_task1.py && .venv/Scripts/python.exe -m pytest tests/test_storage_v2.py -q -p no:cacheprovider`
Expected: `task 1 edits applied`, then `8 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass (261 + 8).

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: save format v2 - facts, beliefs, listeners, fading memory"`

---

### Task 2: Facts from deeds, and the knowledge layer

**Files:**
- Create: `systems/beliefs.py`, `systems/facts.py`, `systems/rumours.py` (channels 1–2 only; Task 3 extends it)
- Modify: `systems/duel.py` (import facts so they are recorded), via `.patches/3a_task2.py`
- Test: `tests/test_facts.py`

**Interfaces:**
- Consumes: Task 1 (`World.add_fact`, `upsert_belief`, `known_facts`, `witnesses_of`, `chronicle_entry`, `listen`).
- Produces:
  - `systems.beliefs`:
    - Beliefs and confidence: `CONF_DECAY = 0.85`, `believe(world, knower, fact_id, variant, source, confidence, hops, channel) -> bool`, `confidence_for(hops, trust=1.0) -> float`, `confidence_phrase(hops, confidence) -> str`, `confidence_word(belief) -> str`.
    - Knowledge: `home_of(world, person) -> int|None` (their town), `knowledge_of(world, knower) -> list[tuple[Belief, Fact]]`.
    - Masks and identity: `knows_identity(world, knower, persona) -> bool`, `appears_as(world, observer, event, true_id) -> int`, `seen_as(world, observer, event) -> int`, `apparent_to(world, observer, player) -> int`, `true_identity(world, subject) -> int`, `identities(world, knower, true_id) -> set[int]`.
    - `known_people(world, player) -> list[int]`.
  - `systems.facts`:
    - Tables: `WEIGHTS`, `FAMILY`, `VERDICT_FACTS`, `ON_FACT`.
    - Functions: `on_fact(fn)`, `make_variant(predicate, actor, target, *, place=None, realm=None, art=None, form=None, masked=False) -> dict`, `record_fact(world, subject, predicate, obj, *, place, variant, source_event=None, weight=None, is_true=True, extra=None, spread=True) -> int`, `apparent(event, person) -> int`, `place_name(world, place_id) -> str|None`.
    - Listeners on `duel_ended` and `encounter_resolved`.
  - `systems.rumours`: fact hooks `_witnesses` (channel 1) and `_town_gossip` (channel 2).
  - Variant keys: `predicate, actor, target, count, place, realm, art, form, masked, soft`.

- [ ] **Step 1: Write the failing test** — `tests/test_facts.py`
```python
import pytest

from engine.game import Game
from systems.beliefs import (
    CONF_DECAY, appears_as, confidence_phrase, identities, knowledge_of, knows_identity, known_people,
)
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event, Witness, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name="Bandit Ma", realm="mortal", occupation="bandit", traits=("greedy", "proud")):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": occupation, "traits": list(traits), "realm": realm, "surname": surname, "given": given,
        "gender": "man", "age": 30, "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def ended(game, opp, **changes):
    data = {"duel": None, "mode": "duel", "result": "won", "reason": "broken", "verdict": "rob", "by": "player",
            "silver": 0, "crippled": None, "loot": [], "insight": 1.0, "life_and_death": False,
            "fragment": None, "purpose": {}}
    data.update(changes)
    return Event("duel_ended", (game.player.id, opp), game.place.id, data, witnesses=(Witness(opp, "humiliated", 0.8),))


def test_robbing_someone_becomes_two_true_facts(game):
    opp = person(game)
    commit(game.world, [ended(game, opp)])
    facts = {f.predicate: f for f in game.world.facts()}
    assert set(facts) == {"defeated", "robbed"}
    robbed = facts["robbed"]
    assert (robbed.subject, robbed.object, robbed.weight, robbed.is_true) == (game.player.id, opp, 1.0, True)
    assert robbed.variant["place"] == game.place.name and robbed.variant["actor"] == game.player.id
    assert facts["defeated"].weight == 0.5


def test_a_realm_gap_makes_a_heavier_story(game):
    opp = person(game, realm="second-rate")
    commit(game.world, [ended(game, opp, verdict="spare")])
    defeated = game.world.facts(predicate="defeated")[0]
    assert defeated.weight == pytest.approx(0.5 + 0.75 * 2)
    assert defeated.variant["realm"] == "second-rate"
    assert game.world.facts(predicate="spared")[0].weight == 0.5


def test_witnesses_know_first_hand_and_the_town_talks(game):
    opp = person(game)
    onlooker = person(game, "Old Wu", occupation="innkeeper", traits=("kind", "honest"))
    commit(game.world, [Event("duel_ended", (game.player.id, opp), game.place.id,
                              ended(game, opp).data, witnesses=(Witness(onlooker, "witnessed_duel", 0.2),))])
    robbed = game.world.facts(predicate="robbed")[0]
    firsthand = {b.knower: b for b in game.world.believers(robbed.id)}
    for knower in (game.player.id, opp, onlooker):
        assert firsthand[knower].hops == 0 and firsthand[knower].confidence == 1.0
        assert firsthand[knower].channel == "witness"
    pool = firsthand[game.place.id]
    assert (pool.hops, pool.confidence, pool.channel) == (1, CONF_DECAY, "gossip")


def test_spars_and_tests_make_no_facts(game):
    opp = person(game)
    commit(game.world, [ended(game, opp, mode="spar", result="spar_won", verdict=None)])
    assert game.world.facts() == []


def test_losing_makes_the_winner_the_subject(game):
    opp = person(game)
    commit(game.world, [ended(game, opp, result="lost", by="opponent", verdict="rob")])
    robbed = game.world.facts(predicate="robbed")[0]
    assert (robbed.subject, robbed.object) == (opp, game.player.id)


def test_a_beast_is_never_the_subject(game):
    wolf = game.world.add_entity("person", "a grey wolf", {"beast": True, "realm": "mortal", "occupation": "grey wolf"})
    game.world.relate(wolf, game.place.id, "located_in")
    commit(game.world, [ended(game, wolf, result="lost", by="opponent", verdict="spare")])
    assert game.world.facts() == []


def test_town_gossip_reaches_townsfolk_one_retelling_further(game):
    opp = person(game)
    listener = person(game, "Old Wu", occupation="innkeeper", traits=("kind", "honest"))
    commit(game.world, [ended(game, opp)])
    heard = {f.predicate: b for b, f in knowledge_of(game.world, listener)}
    assert heard["robbed"].hops == 2
    assert heard["robbed"].confidence == pytest.approx(round(CONF_DECAY * CONF_DECAY, 3))
    assert heard["robbed"].source == game.place.id


def test_masked_deeds_are_credited_to_the_persona_until_someone_knows(game):
    opp = person(game)
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    event = ended(game, opp)
    event = Event(event.kind, event.actors, event.place, {**event.data, "as": persona}, witnesses=event.witnesses)
    [eid] = commit(game.world, [event])
    robbed = game.world.facts(predicate="robbed")[0]
    assert robbed.subject == persona and robbed.variant["masked"] is True
    entry = game.world.chronicle_entry(eid)
    assert appears_as(game.world, opp, entry, game.player.id) == persona
    assert appears_as(game.world, game.player.id, entry, game.player.id) == game.player.id
    assert knows_identity(game.world, game.player.id, persona)
    assert not knows_identity(game.world, opp, persona)
    record_fact(game.world, persona, "is", game.player.id, place=game.place.id,
                variant=make_variant("is", persona, game.player.id))
    assert knows_identity(game.world, opp, persona)  # the town pool now carries it
    assert appears_as(game.world, opp, entry, game.player.id) == game.player.id
    assert identities(game.world, opp, game.player.id) == {game.player.id, persona}


def test_confidence_words():
    assert confidence_phrase(0, 1.0) == "you saw it yourself"
    assert confidence_phrase(1, 0.85) == "from a witness"
    assert confidence_phrase(3, 0.6) == "hearsay"
    assert confidence_phrase(6, 0.3) == "doubtful"


def test_known_people_are_those_met_or_heard_of(game):
    stranger = person(game, "Far Away")
    met = next(p for p in game.world.sources(game.place.id, "located_in")
               if not game.world.entity(p).data.get("is_player") and p != stranger)
    from engine.game import Action
    game.perform(Action("talk", met))
    assert met in known_people(game.world, game.player.id)
    assert stranger not in known_people(game.world, game.player.id)
    record_fact(game.world, stranger, "robbed", met, place=game.place.id,
                variant=make_variant("robbed", stranger, met))
    fact = game.world.facts(predicate="robbed")[0]
    game.world.upsert_belief(game.player.id, fact.id, fact.variant, None, 0.5, 2, "told")
    assert stranger in known_people(game.world, game.player.id)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_facts.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.beliefs'`.

- [ ] **Step 3: Write the knowledge layer** — `systems/beliefs.py`
```python
"""What people believe (phase 3a spec §4.2): beliefs, knowledge, confidence, and seeing through masks.

Nothing shown to the player reads facts directly: everything goes through a
knower's beliefs. Ground truth (the chronicle, facts.is_true, a persona's `of`)
stays behind this layer; `of` is read only to ask "is the reader the wearer?".
"""

from dataclasses import replace

from world.db import Belief, Fact, World

CONF_DECAY = 0.85


def believe(world: World, knower: int, fact_id: int, variant: dict, source: int | None,
            confidence: float, hops: int, channel: str) -> bool:
    confidence = round(max(0.0, min(1.0, confidence)), 3)
    return world.upsert_belief(knower, fact_id, variant, source, confidence, max(0, hops), channel)


def confidence_for(hops: int, trust: float = 1.0) -> float:
    return 1.0 if hops == 0 else round(CONF_DECAY ** hops * trust, 3)


def confidence_phrase(hops: int, confidence: float) -> str:
    if hops == 0:
        return "you saw it yourself"
    if confidence >= 0.75:
        return "from a witness"
    if confidence >= 0.45:
        return "hearsay"
    return "doubtful"


def confidence_word(belief: Belief) -> str:
    return confidence_phrase(belief.hops, belief.confidence)


def home_of(world: World, person_id: int) -> int | None:
    """The town a person is in, or None (the dead, roamers of the wilds)."""
    for place_id in world.targets(person_id, "located_in"):
        place = world.entity(place_id)
        if place is not None and place.kind == "town":
            return place.id
    return None


def knowledge_of(world: World, knower_id: int) -> list[tuple[Belief, Fact]]:
    """A person's own beliefs plus their town's gossip, one retelling further. A town knows its pool."""
    own = world.known_facts(knower_id)
    entity = world.entity(knower_id)
    if entity is None or entity.kind != "person":
        return own
    town = home_of(world, knower_id)
    if town is None:
        return own
    held = {(b.fact_id, b.variant_key) for b, _ in own}
    pool = [
        (replace(b, knower=knower_id, source=town, hops=b.hops + 1,
                 confidence=round(b.confidence * CONF_DECAY, 3), channel="gossip"), f)
        for b, f in world.known_facts(town) if (b.fact_id, b.variant_key) not in held
    ]
    return own + pool


def knows_identity(world: World, knower_id: int, persona_id: int | None) -> bool:
    """Does this knower know who wears the mask? The wearer always does."""
    if persona_id is None:
        return False
    persona = world.entity(persona_id)
    if persona is None:
        return False
    if persona.data.get("of") == knower_id:
        return True
    return any(f.predicate == "is" and f.subject == persona_id for _, f in knowledge_of(world, knower_id))


def appears_as(world: World, observer: int, event, true_id: int) -> int:
    """Who `observer` takes `true_id` to be in this event: the persona while masked and unrecognised."""
    data = event.data if isinstance(event.data, dict) else {}
    persona = data.get("as")
    if persona and event.actors and true_id == event.actors[0] and observer != true_id \
            and not knows_identity(world, observer, persona):
        return persona
    return true_id


def seen_as(world: World, observer: int, event) -> int:
    return appears_as(world, observer, event, event.actors[0])


def apparent_to(world: World, observer: int, player_id: int) -> int:
    """Who the player seems to be to `observer` right now: their worn persona unless recognised."""
    persona = world.entity(player_id).data.get("masked")
    if persona and not knows_identity(world, observer, persona):
        return persona
    return player_id


def true_identity(world: World, subject_id: int) -> int:
    entity = world.entity(subject_id)
    if entity is not None and entity.kind == "persona":
        return entity.data.get("of", subject_id)
    return subject_id


def identities(world: World, knower_id: int, true_id: int) -> set[int]:
    """The ids this knower attributes to `true_id`: themselves plus any persona known to be them."""
    ids = {true_id}
    for persona in world.entities("persona"):
        if persona.data.get("of") == true_id and knows_identity(world, knower_id, persona.id):
            ids.add(persona.id)
    return ids


def known_people(world: World, player_id: int) -> list[int]:
    """Everyone the player has met or heard of (people and personas), most recent first."""
    seen: list[int] = world.acquaintances(player_id)  # all of history, not just recent pages
    for belief, _ in reversed(world.known_facts(player_id)):
        for someone in (belief.variant.get("actor"), belief.variant.get("target")):
            if someone is not None and someone != player_id and someone not in seen:
                seen.append(someone)
    out = []
    for someone in seen:
        entity = world.entity(someone)
        if entity is not None and entity.kind in ("person", "persona"):
            out.append(someone)
    return out
```

- [ ] **Step 4: Write the fact recorder** — `systems/facts.py`
```python
"""Deeds become facts (phase 3a spec §4.1). Listeners on committed events write them.

A fact is ground truth. Its `variant` is the story as it looked to those present
(a masked deed names the persona). Fact hooks (ON_FACT) spread it as beliefs.
"""

from collections.abc import Callable

from systems.realms import realm_index
from world.db import Fact, World
from world.events import listen

WEIGHTS = {
    "killed": 3.0, "crippled": 2.0, "robbed": 1.0, "spared": 0.5, "fled_from": 0.5, "paid_off": 0.3,
    "is": 2.0, "lied_about": 1.5, "left_for_dead": 1.5, "owns_manual": 0.5, "defeated": 0.5,
}
FAMILY = {
    "killed": "harm", "crippled": "harm", "robbed": "harm", "left_for_dead": "harm", "defeated": "harm",
    "spared": "mercy", "fled_from": "flight", "paid_off": "flight", "is": "identity",
    "lied_about": "deceit", "owns_manual": "possession",
}
VERDICT_FACTS = {"kill": "killed", "cripple": "crippled", "rob": "robbed", "spare": "spared",
                 "leave_for_dead": "left_for_dead"}
FIGHT_MODES = ("duel", "encounter")
ON_FACT: list[Callable[[World, Fact], None]] = []


def on_fact(fn: Callable[[World, Fact], None]) -> Callable[[World, Fact], None]:
    """Register a channel that reacts to every new (spreading) fact."""
    ON_FACT.append(fn)
    return fn


def make_variant(predicate: str, actor: int | None, target: int | None, *, place: str | None = None,
                 realm: str | None = None, art: str | None = None, form: str | None = None,
                 masked: bool = False) -> dict:
    return {"predicate": predicate, "actor": actor, "target": target, "count": 1, "place": place,
            "realm": realm, "art": art, "form": form, "masked": masked, "soft": False}


def record_fact(world: World, subject: int, predicate: str, obj: int | None, *, place: int | None, variant: dict,
                source_event: int | None = None, weight: float | None = None, is_true: bool = True,
                extra: dict | None = None, spread: bool = True) -> int:
    weight = WEIGHTS.get(predicate, 1.0) if weight is None else weight
    fact_id = world.add_fact(subject, predicate, obj, place=place, weight=weight, is_true=is_true,
                             data={"variant": variant, **(extra or {})}, source_event=source_event)
    if spread:
        fact = world.fact(fact_id)
        for channel in ON_FACT:
            channel(world, fact)
    return fact_id


def apparent(event, person_id: int) -> int:
    """The id a deed is credited to: the persona while the player (actors[0]) wears a mask."""
    persona = event.data.get("as")
    return persona if persona and event.actors and person_id == event.actors[0] else person_id


def place_name(world: World, place_id: int | None) -> str | None:
    entity = world.entity(place_id) if place_id else None
    return entity.name if entity else None


def _arts(world: World, data: dict) -> dict:
    """side -> (art name, form) as the fight began."""
    started = world.chronicle_entry(data.get("duel"))
    out = {"player": (None, None), "opponent": (None, None)}
    if started is None or started.kind != "duel_started":
        return out
    for side, key in (("player", "technique"), ("opponent", "opponent_technique")):
        technique = world.entity(started.data.get(key)) if started.data.get(key) else None
        if technique is not None:
            out[side] = (technique.name, technique.data.get("form"))
    return out


@listen("duel_ended")
def _fight_facts(world: World, event, event_id: int) -> None:
    d = event.data
    if d.get("mode") not in FIGHT_MODES:
        return
    player, opponent = event.actors
    beast = bool(world.entity(opponent).data.get("beast"))
    me = apparent(event, player)
    where = place_name(world, event.place)
    result = d.get("result")
    if result == "fled":
        record_fact(world, me, "fled_from", opponent, place=event.place, source_event=event_id,
                    variant=make_variant("fled_from", me, opponent, place=where, masked=me != player))
        return
    if result == "won":
        winner, loser, true_winner, true_loser, side = me, opponent, player, opponent, "player"
    elif result == "lost" and not beast:
        winner, loser, true_winner, true_loser, side = opponent, me, opponent, player, "opponent"
    else:
        return
    loser_realm = world.entity(true_loser).data.get("realm", "mortal")
    gap = max(0, realm_index(loser_realm) - realm_index(world.entity(true_winner).data.get("realm", "mortal")))
    art, form = _arts(world, d)[side]
    masked = winner == me and me != player
    story = dict(place=where, realm=loser_realm, art=art, form=form, masked=masked)
    if not beast:
        record_fact(world, winner, "defeated", loser, place=event.place, source_event=event_id,
                    weight=0.5 + 0.75 * gap, variant=make_variant("defeated", winner, loser, **story))
    predicate = VERDICT_FACTS.get(d.get("verdict"))
    if predicate and (not beast or predicate == "killed"):
        record_fact(world, winner, predicate, loser, place=event.place, source_event=event_id,
                    weight=0.5 if beast else None, variant=make_variant(predicate, winner, loser, **story))
    if result == "won":
        for item in d.get("loot") or []:
            manual = world.entity(item)
            if manual is not None:
                record_fact(world, me, "owns_manual", None, place=event.place, source_event=event_id,
                            variant=make_variant("owns_manual", me, None, place=where, art=manual.name,
                                                 masked=me != player))


@listen("encounter_resolved")
def _paid_off(world: World, event, event_id: int) -> None:
    if event.data.get("how") != "paid":
        return
    player, bandit = event.actors
    me = apparent(event, player)
    record_fact(world, me, "paid_off", bandit, place=event.place, source_event=event_id,
                variant=make_variant("paid_off", me, bandit, place=place_name(world, event.place), masked=me != player))


# Channels register themselves on import (like narrate/outcomes.py). Later tasks add theirs here.
import systems.rumours  # noqa: E402,F401
```

- [ ] **Step 5: Write the first two rumour channels** — `systems/rumours.py`
```python
"""How news travels (phase 3a spec §5): witnesses, town gossip, kin, distance and telling."""

from systems.beliefs import CONF_DECAY, believe
from systems.facts import on_fact


@on_fact
def _witnesses(world, fact) -> None:
    """Channel 1: everyone who took part in or saw the deed knows it first-hand."""
    if fact.source_event is None:
        return
    entry = world.chronicle_entry(fact.source_event)
    people = set(world.witnesses_of(fact.source_event)) | set(entry.actors if entry else ())
    for person_id in sorted(people):
        person = world.entity(person_id)
        if person is None or person.kind != "person" or person.data.get("dead") or person.data.get("beast"):
            continue
        believe(world, person_id, fact.id, fact.variant, None, 1.0, 0, "witness")


@on_fact
def _town_gossip(world, fact) -> None:
    """Channel 2: the town where it happened talks about it at once."""
    town = world.entity(fact.place) if fact.place else None
    if town is None or town.kind != "town":
        return
    believe(world, town.id, fact.id, fact.variant, None, CONF_DECAY, 1, "gossip")
```

- [ ] **Step 6: Make fights record facts** — `.patches/3a_task2.py`
```python
"""Task 2 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


# Fights are the first deeds worth talking about: importing the recorder registers its listeners.
edit("systems/duel.py", "from world.seed import rng_for\n", "from world.seed import rng_for\nimport systems.facts  # noqa: E402,F401  (deeds become facts)\n")
print("task 2 edits applied")
```

- [ ] **Step 7: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3a_task2.py && .venv/Scripts/python.exe -m pytest tests/test_facts.py -q -p no:cacheprovider`
Expected: `10 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 8: Commit**

Run: `git add -A && git commit -m "feat: deeds become facts; witnesses and town gossip believe them"`

---
### Task 3: Rumours that travel and change

**Files:**
- Modify: `systems/rumours.py`. This task rewrites the whole file, and keeps channels 1–2 from Task 2.
- Test: `tests/test_rumours.py`

**Interfaces:**
- Consumes: Task 2 (`believe`, `confidence_for`, `knowledge_of`, `identities`, `true_identity`, `on_fact`, `make_variant`, `record_fact`).
- Produces (all in `systems.rumours`):
  - Constants: `BASE_MUTATION = 0.25`, `HOP_WATCHES = 8`, `REACH_FACTOR = 1.5`.
  - Mutation: `mutation_chance(traits) -> float`, `mutate(variant, rng, hops) -> dict`, `retell(variant, fact_id, knower, world_seed, first_hop, last_hop, traits=()) -> dict`.
  - Distance: `region_distance(town_a, town_b) -> int`, `reach(weight) -> int`, `catch_up(world, town_id, now=None) -> list[int]` (the ids of facts that newly arrived).
  - News: `pick_news(world, npc, player) -> (Belief, Fact) | None` and `news_about(world, npc, subject) -> (Belief, Fact) | None`.
  - Events: `heard_events(world, player, npc, place, belief, fact) -> [Event("heard")]` and `no_news_events(player, npc, place, about=None) -> [Event("no_news")]`.
  - Effect `heard`: writes the player's belief with `channel "told"` and `source = npc`.

- [ ] **Step 1: Write the failing test** — `tests/test_rumours.py`
```python
import random
import time

import pytest

from engine.game import Game
from systems.beliefs import CONF_DECAY
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.rumours import (
    HOP_WATCHES, catch_up, heard_events, mutate, mutation_chance, news_about, no_news_events, pick_news, retell,
)
from world.events import commit
from world.gen.materialize import ensure_town

STORY = make_variant("killed", 101, 102, place="Rivermouth", realm="third-rate", art="Iron Tiger Fist",
                     form="fist", masked=True)


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("kind", "honest")):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {"occupation": "innkeeper", "traits": list(traits), "realm": "mortal",
                                                 "surname": surname, "given": given})
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def far_fact(game, weight, x=2, y=0, **data):
    origin = ensure_town(game.world, x, y, 0)
    with game.world.transaction():
        fid = game.world.add_fact(101, "killed", 102, place=origin, weight=weight,
                                  data={"variant": STORY, **data}, is_true=data.get("liar") is None)
    return fid, origin


def test_mutation_never_changes_who_did_what_to_whom():
    for seed in range(2000):
        story = mutate(STORY, random.Random(seed), hops=3)
        assert story["predicate"] == "killed" and story["target"] == 102
        assert story["actor"] in (101, None)
        assert story["count"] in (1, 2, 3)


def test_identity_is_never_retold_differently():
    story = make_variant("is", 7, 8)
    for seed in range(200):
        assert mutate(story, random.Random(seed), hops=5) == story


def test_a_masked_actor_is_only_forgotten_after_two_retellings():
    for seed in range(300):
        assert mutate(STORY, random.Random(seed), hops=1)["actor"] == 101


def test_retelling_is_seeded_and_honest_tellers_change_less():
    assert retell(STORY, 5, 9, 11, 1, 4) == retell(STORY, 5, 9, 11, 1, 4)
    assert mutation_chance(("honest",)) < mutation_chance(()) < mutation_chance(("cheerful",))

    def changed(traits):
        return sum(retell(STORY, n, 1, 11, 1, 3, traits) != STORY for n in range(400))
    assert changed(("honest", "secretive")) < changed(("cheerful", "cunning"))


def test_big_news_reaches_far_towns_after_travel_time(game):
    fid, origin = far_fact(game, 3.0)
    here, t0 = game.place.id, game.world.time
    assert catch_up(game.world, here, now=t0 + 2 * HOP_WATCHES - 1) == []
    assert catch_up(game.world, here, now=t0 + 2 * HOP_WATCHES) == [fid]
    [belief] = game.world.beliefs(here)
    assert (belief.hops, belief.channel, belief.source) == (3, "distance", origin)
    assert belief.confidence == pytest.approx(round(CONF_DECAY ** 3, 3))
    assert catch_up(game.world, here, now=t0 + 100) == []


def test_small_news_stays_local(game):
    far_fact(game, 1.0)
    assert catch_up(game.world, game.place.id, now=game.world.time + 1000) == []


def test_rejected_lies_do_not_travel(game):
    far_fact(game, 3.0, x=1, liar=1, spread=False)
    assert catch_up(game.world, game.place.id, now=game.world.time + 1000) == []


def test_catching_up_on_500_facts_is_quick(game):
    origin = ensure_town(game.world, 1, 0, 0)
    with game.world.transaction():
        for _ in range(500):
            game.world.add_fact(101, "killed", 102, place=origin, weight=3.0, data={"variant": STORY})
    start = time.perf_counter()
    added = catch_up(game.world, game.place.id, now=game.world.time + 100)
    elapsed = time.perf_counter() - start
    assert len(added) == 500
    assert elapsed < 0.05, f"catch_up took {elapsed * 1000:.0f} ms"


def test_news_prefers_the_biggest_story_about_others_and_is_not_repeated(game):
    teller = person(game, "Old Wu")
    small = record_fact(game.world, 101, "robbed", 102, place=game.place.id, variant=make_variant("robbed", 101, 102))
    big = record_fact(game.world, 101, "killed", 102, place=game.place.id, variant=make_variant("killed", 101, 102))
    mine = record_fact(game.world, game.player.id, "killed", 102, place=game.place.id, weight=9.0,
                       variant=make_variant("killed", game.player.id, 102))
    order = []
    while (found := pick_news(game.world, teller, game.player.id)) is not None:
        belief, fact = found
        [event] = heard_events(game.world, game.player.id, teller, game.place.id, belief, fact)
        commit(game.world, [event])
        order.append(fact.id)
        assert len(order) < 10
    assert order == [big, small, mine]
    heard = {b.fact_id: b for b in game.world.beliefs(game.player.id)}
    assert heard[big].source == teller and heard[big].channel == "told" and heard[big].hops == 3


def test_with_nothing_new_the_answer_is_nothing(game):
    teller = person(game, "Old Wu")
    assert pick_news(game.world, teller, game.player.id) is None
    [event] = no_news_events(game.player.id, teller, game.place.id, about="Wang Li")
    assert event.kind == "no_news" and event.data == {"about": "Wang Li"}


def test_news_about_someone_gives_the_surest_story(game):
    teller = person(game, "Old Wu")
    target = person(game, "Ma Bo", traits=("greedy", "proud"))
    record_fact(game.world, 101, "robbed", target, place=game.place.id, variant=make_variant("robbed", 101, target))
    _, fact = news_about(game.world, teller, target)
    assert fact.object == target
    assert news_about(game.world, teller, person(game, "No Body")) is None
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rumours.py -q -p no:cacheprovider`
Expected: the collection error `ImportError: cannot import name 'HOP_WATCHES' from 'systems.rumours'`.

- [ ] **Step 3: Write the full rumours module** — `systems/rumours.py`
```python
"""How news travels (phase 3a spec §5): witnesses, town gossip, kin, distance and telling.

Channels 1-2 react to new facts (kin is channel 3, in systems/kin.py). Channel 4
(distance) runs lazily: a town catches up on what has reached it when the player
arrives or asks. Every retelling may change the story, seeded so a world always
tells it the same way.
"""

from systems.beliefs import CONF_DECAY, believe, confidence_for, identities, knowledge_of, true_identity
from systems.facts import on_fact
from systems.realms import REALMS, realm_index
from world.events import Event, Witness, effect
from world.seed import rng_for

BASE_MUTATION = 0.25
HOP_WATCHES = 8        # two days per region crossed
REACH_FACTOR = 1.5     # a fact of weight w travels floor(1.5 * w) regions
NEWS_HALF_LIFE = 360   # watches; older news is less worth telling
LOUD = frozenset({"cheerful", "cunning"})
CAREFUL = frozenset({"honest", "secretive"})


# --- channels 1 and 2 ------------------------------------------------------------------

@on_fact
def _witnesses(world, fact) -> None:
    """Channel 1: everyone who took part in or saw the deed knows it first-hand."""
    if fact.source_event is None:
        return
    entry = world.chronicle_entry(fact.source_event)
    people = set(world.witnesses_of(fact.source_event)) | set(entry.actors if entry else ())
    for person_id in sorted(people):
        person = world.entity(person_id)
        if person is None or person.kind != "person" or person.data.get("dead") or person.data.get("beast"):
            continue
        believe(world, person_id, fact.id, fact.variant, None, 1.0, 0, "witness")


@on_fact
def _town_gossip(world, fact) -> None:
    """Channel 2: the town where it happened talks about it at once."""
    town = world.entity(fact.place) if fact.place else None
    if town is None or town.kind != "town":
        return
    believe(world, town.id, fact.id, fact.variant, None, CONF_DECAY, 1, "gossip")


# --- retelling --------------------------------------------------------------------------

def mutation_chance(traits=()) -> float:
    traits = set(traits)
    chance = BASE_MUTATION
    if LOUD & traits:
        chance *= 1.5
    if CAREFUL & traits:
        chance *= 0.5
    return chance


def mutate(variant: dict, rng, hops: int) -> dict:
    """One change to a story. Never the deed's family, never who was harmed, never truth into lie."""
    story = dict(variant)
    if story.get("predicate") == "is":
        return story
    options = ["exaggerate", "blur_place", "blur_art"]
    if story.get("masked") and story.get("actor") is not None and hops >= 2:
        options.append("misattribute")
    if story.get("predicate") == "killed" and not story.get("soft"):
        options.append("soften")
    choice = rng.choice(options)
    if choice == "exaggerate":
        if story.get("count", 1) == 1 and story.get("target") is not None:
            story["count"] = rng.choice((2, 3))
        elif story.get("realm") and realm_index(story["realm"]) < len(REALMS) - 1:
            story["realm"] = REALMS[realm_index(story["realm"]) + 1].label
    elif choice == "blur_place":
        story["place"] = None
    elif choice == "blur_art":
        story["art"], story["form"] = None, None
    elif choice == "misattribute":
        story["actor"] = None
    else:
        story["soft"] = True
    return story


def retell(variant: dict, fact_id: int, knower: int, world_seed: int, first_hop: int, last_hop: int,
           traits=()) -> dict:
    """The story after retellings first_hop..last_hop on its way to `knower`."""
    story = dict(variant)
    chance = mutation_chance(traits)
    for hop in range(first_hop, last_hop + 1):
        rng = rng_for(world_seed, f"rumour:{fact_id}:{knower}:{hop}")
        if rng.random() < chance:
            story = mutate(story, rng, hop)
    return story


# --- channel 4: distance --------------------------------------------------------------------

def region_distance(town_a, town_b) -> int:
    return max(abs(town_a.data["x"] - town_b.data["x"]), abs(town_a.data["y"] - town_b.data["y"]))


def reach(weight: float) -> int:
    return int(weight * REACH_FACTOR)


def catch_up(world, town_id: int, now: int | None = None) -> list[int]:
    """Let this town hear every fact that has had time to travel here. Returns the facts that arrived."""
    town = world.entity(town_id)
    if town is None or town.kind != "town":
        return []
    now = world.time if now is None else now
    origins: dict = {}
    added = []
    with world.transaction():
        for fact in world.facts_unknown_to(town_id, until=now - HOP_WATCHES):
            if fact.place is None or fact.place == town_id or fact.data.get("spread") is False:
                continue
            if fact.place not in origins:
                origins[fact.place] = world.entity(fact.place)
            origin = origins[fact.place]
            if origin is None or origin.kind != "town":
                continue
            distance = region_distance(origin, town)
            if distance > reach(fact.weight) or now < fact.time + distance * HOP_WATCHES:
                continue
            hops = distance + 1
            story = retell(fact.variant, fact.id, town_id, world.world_seed, 1, hops)
            believe(world, town_id, fact.id, story, origin.id, confidence_for(hops), hops, "distance")
            added.append(fact.id)
    return added


# --- telling the player ------------------------------------------------------------------------

def pick_news(world, npc_id: int, player_id: int):
    """The story this person would pass on now: heaviest and newest, about others before the player."""
    now = world.time
    mine = world.beliefs(player_id)
    held = {(b.fact_id, b.variant_key) for b in mine}
    told_me = {b.fact_id for b in mine if b.source == npc_id}
    me = identities(world, player_id, player_id)
    fresh = [(b, f) for b, f in knowledge_of(world, npc_id)
             if (b.fact_id, b.variant_key) not in held and f.id not in told_me and f.data.get("liar") != player_id]
    others = [(b, f) for b, f in fresh if f.subject not in me and f.object not in me]
    pool = others or fresh
    if not pool:
        return None
    return max(pool, key=lambda p: (p[1].weight * 0.5 ** (max(0, now - p[1].time) / NEWS_HALF_LIFE),
                                    p[1].id, p[0].variant_key))


def news_about(world, npc_id: int, subject_id: int):
    """This person's surest story about someone, or None if they have never heard of them."""
    true_id = true_identity(world, subject_id)
    ids = identities(world, npc_id, true_id) if subject_id == true_id else {subject_id}
    found = [(b, f) for b, f in knowledge_of(world, npc_id)
             if b.variant.get("actor") in ids or b.variant.get("target") in ids]
    if not found:
        return None
    return max(found, key=lambda p: (p[0].confidence * p[1].weight, p[1].id, p[0].variant_key))


def heard_events(world, player: int, npc: int, place: int, belief, fact) -> list[Event]:
    teller = world.entity(npc)
    traits = teller.data.get("traits", ())
    hops = belief.hops + 1
    story = retell(belief.variant, fact.id, player, world.world_seed, hops, hops, traits)
    trust = 0.9 if "cunning" in traits else 1.0
    data = {"fact": fact.id, "variant": story, "confidence": confidence_for(hops, trust), "hops": hops}
    return [Event("heard", (player, npc), place, data, witnesses=(Witness(npc, "engaged", 0.1),))]


def no_news_events(player: int, npc: int, place: int, about: str | None = None) -> list[Event]:
    return [Event("no_news", (player, npc), place, {"about": about})]


@effect("heard")
def _heard(world, event) -> None:
    d = event.data
    believe(world, event.actors[0], d["fact"], d["variant"], event.actors[1], d["confidence"], d["hops"], "told")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rumours.py tests/test_facts.py -q -p no:cacheprovider`
Expected: `21 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 5: Commit**

Run: `git add -A && git commit -m "feat: rumours travel by distance, change as they are retold, and can be heard"`

---

### Task 4: Attitude and reputation

**Files:**
- Create: `systems/attitude.py`, `systems/reputation.py`
- Test: `tests/test_attitude.py`

**Interfaces:**
- Consumes: Task 2 (`appears_as`, `identities`, `knowledge_of`, `true_identity`) and Task 1 (`effective_intensity`).
- Produces:
  - `systems.attitude`:
    - `Attitude(score: float, word: str, reason: str | None)`.
    - `attitude(world, npc, subject) -> Attitude`, `word_for(score) -> str`, `afraid(world, npc, subject) -> bool`, `is_bandit(entity) -> bool`.
    - `FEELING_VALUE`, `JUDGEMENT`, `VERBS`.
  - `systems.reputation`:
    - `Reputation(renown: float, word: str, path: str, epithet: str | None)`.
    - `reputation(world, town, subject) -> Reputation`.
    - `EPITHET_RENOWN = 6.0`.
    - `renown_word(renown) -> str`, which gives "unknown", "little known", "known", "renowned" or "famous".

- [ ] **Step 1: Write the failing test** — `tests/test_attitude.py`
```python
import pytest

from engine.game import Game
from systems.attitude import Attitude, afraid, attitude, word_for
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.reputation import Reputation, reputation
from world.events import Event, Witness, commit

RIGHTEOUS = ("Jade", "Azure", "White", "Upright")
RUTHLESS = ("Crimson", "Blood", "Black", "Iron")


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("curious", "lazy"), realm="mortal", occupation="innkeeper"):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {"occupation": occupation, "traits": list(traits), "realm": realm,
                                                 "surname": surname, "given": given})
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def deed(game, actor, predicate, target, **story):
    return record_fact(game.world, actor, predicate, target, place=game.place.id,
                       variant=make_variant(predicate, actor, target, place=game.place.name, **story))


def test_bands():
    assert [word_for(s) for s in (1.2, 0.5, 0.0, -0.5, -1.5, -2.5)] == \
        ["warm", "friendly", "neutral", "wary", "hostile", "hateful"]


def test_a_stranger_with_no_history_is_neutral(game):
    assert attitude(game.world, person(game, "Hu Mei"), game.player.id) == Attitude(0.0, "neutral", None)


def test_gratitude_fades_with_the_seasons(game):
    npc = person(game, "Hu Mei")
    commit(game.world, [Event("helped", (game.player.id, npc), game.place.id, {},
                              witnesses=(Witness(npc, "grateful", 1.0),))])
    now = attitude(game.world, npc, game.player.id)
    assert now.word == "warm" and now.reason == "you showed them mercy"
    game.world.set_time(game.world.time + 720)
    assert attitude(game.world, npc, game.player.id).word == "neutral"


def test_rumours_of_a_killing_turn_the_kind_hateful_and_the_greedy_hostile(game):
    victim = person(game, "Wang Li")
    kind = person(game, "Old Wu", traits=("kind", "honest"))
    greedy = person(game, "Ma Bo", traits=("greedy", "lazy"))
    deed(game, game.player.id, "killed", victim)
    heard = attitude(game.world, kind, game.player.id)
    assert heard.word == "hateful"
    assert heard.reason == f"heard you killed Wang Li in {game.place.name}"
    assert attitude(game.world, greedy, game.player.id).word == "hostile"


def test_a_persona_is_judged_apart_from_the_player(game):
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    victim = person(game, "Wang Li")
    townsman = person(game, "Old Wu", traits=("kind", "honest"))
    deed(game, persona, "killed", victim, masked=True)
    assert attitude(game.world, townsman, game.player.id).word == "neutral"
    assert attitude(game.world, townsman, persona).word == "hateful"
    deed(game, persona, "is", game.player.id)
    assert attitude(game.world, townsman, game.player.id).word == "hateful"


def test_fear_needs_a_killing_and_a_stronger_believed_realm(game):
    weak = person(game, "Hu Mei")
    strong = person(game, "Iron Gu", realm="first-rate")
    victim = person(game, "Wang Li", realm="third-rate")
    deed(game, game.player.id, "defeated", victim, realm="third-rate")
    assert not afraid(game.world, weak, game.player.id)
    deed(game, game.player.id, "killed", victim, realm="third-rate")
    assert afraid(game.world, weak, game.player.id)
    assert not afraid(game.world, strong, game.player.id)


def test_a_town_that_has_heard_nothing_knows_nothing(game):
    assert reputation(game.world, game.place.id, game.player.id) == Reputation(0.0, "unknown", "hard to read", None)


def test_killing_bandits_makes_a_righteous_name(game):
    for name in ("Ma Bo", "Ma Da", "Ma San"):
        bandit = person(game, name, occupation="bandit")
        deed(game, game.player.id, "killed", bandit, form="fist")
    rep = reputation(game.world, game.place.id, game.player.id)
    assert rep.word == "renowned" and rep.path == "righteous"
    adjective, noun, of, place = rep.epithet.split(" ", 3)
    assert adjective in RIGHTEOUS and noun == "Fist" and of == "of" and place == game.place.name
    assert reputation(game.world, game.place.id, game.player.id) == rep


def test_killing_townsfolk_makes_a_ruthless_name(game):
    for name in ("Wang Li", "Hu Mei", "Old Wu"):
        deed(game, game.player.id, "killed", person(game, name), form="palm")
    rep = reputation(game.world, game.place.id, game.player.id)
    assert rep.path == "ruthless" and rep.epithet.split(" ")[0] in RUTHLESS and rep.epithet.split(" ")[1] == "Palm"


def test_masked_deeds_count_for_the_persona_until_the_town_knows(game):
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    deed(game, persona, "killed", person(game, "Ma Bo", occupation="bandit"), masked=True)
    assert reputation(game.world, game.place.id, persona).renown > 0
    assert reputation(game.world, game.place.id, game.player.id).renown == 0
    deed(game, persona, "is", game.player.id)
    assert reputation(game.world, game.place.id, game.player.id).renown > 0
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_attitude.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.attitude'`.

- [ ] **Step 3: Write attitude** — `systems/attitude.py`
```python
"""How someone feels about someone else (phase 3a spec §3.2): computed when asked, never stored.

Four things add up: what they remember (fading), what they have heard (judged
by their nature), the grief and grudges their family passed on (as memories),
and their temperament. The strongest term gives the reason, so a narrator can
say *why*.
"""

from dataclasses import dataclass

from systems.beliefs import appears_as, identities, knowledge_of, true_identity
from systems.memory import effective_intensity
from systems.realms import realm_index

FEELING_VALUE = {
    "grateful": 1.0, "saved": 1.0, "respect": 0.6, "amused": 0.3,
    "sparred": 0.1, "conversed": 0.1, "met": 0.1, "curious": 0.1, "familiar": 0.1,
    "annoyed": -0.4, "contempt": -0.3, "humiliated": -0.8, "hatred": -1.5, "grief": -1.5, "wronged": -1.2,
}
JUDGEMENT = {
    "killed": -1.0, "crippled": -0.7, "robbed": -0.5, "defeated": 0.0, "spared": 0.4, "fled_from": -0.2,
    "lied_about": -0.6, "owns_manual": 0.0, "paid_off": -0.1, "left_for_dead": -0.8, "is": 0.0,
}
HARSH = frozenset({"killed", "crippled", "robbed"})
HARM = frozenset({"killed", "crippled"})
REASONS = {
    "grateful": "you showed them mercy", "saved": "you saved them", "respect": "they respect your skill",
    "amused": "you amused them", "annoyed": "you annoyed them", "contempt": "they look down on you",
    "humiliated": "you humiliated them", "hatred": "you wronged them", "wronged": "you spread lies about them",
}
VERBS = {
    "killed": "killed", "crippled": "crippled", "robbed": "robbed", "spared": "spared", "defeated": "beat",
    "fled_from": "fled from", "lied_about": "spread lies about", "left_for_dead": "left", "paid_off": "paid off",
}


@dataclass(frozen=True)
class Attitude:
    score: float
    word: str
    reason: str | None


def word_for(score: float) -> str:
    if score >= 1.0:
        return "warm"
    if score >= 0.3:
        return "friendly"
    if score > -0.3:
        return "neutral"
    if score > -1.0:
        return "wary"
    if score > -2.0:
        return "hostile"
    return "hateful"


def is_bandit(entity) -> bool:
    return entity is not None and (entity.data.get("occupation") == "bandit" or entity.data.get("roamer_kind") == "bandit")


def judgement(world, predicate: str, target_id, traits: set, weight: float) -> float:
    """How bad (or good) a deed seems to someone of these traits."""
    value = JUDGEMENT.get(predicate, 0.0)
    target = world.entity(target_id) if isinstance(target_id, int) else None
    if predicate == "killed" and target is not None:
        if target.data.get("beast"):
            value = 0.2
        elif is_bandit(target):
            value = -0.5
    if predicate == "robbed" and is_bandit(target):
        value = -0.3
    if predicate in HARSH and value < 0:
        if traits & {"kind", "honest"}:
            value *= 2
        elif traits & {"greedy", "cunning"}:
            value *= 0.5
    if predicate == "defeated" and "proud" in traits and weight > 0.5:
        value += 0.2  # the proud respect whoever beats a stronger fighter
    return value


def _role(world, owner: int, other) -> str | None:
    for kin, _, data in world.relations_from(owner, "kin_of"):
        if kin == other:
            return data.get("role")
    return None


def _memory_reason(world, owner: int, memory) -> str | None:
    event = memory.event
    if memory.feeling == "grief":
        role = _role(world, owner, event.actors[1] if len(event.actors) > 1 else None)
        return f"you killed their {role}" if role else "you killed someone dear to them"
    if memory.inherited_from is not None:
        return "their family has not forgotten what you did"
    if event.kind == "duel_ended" and event.data.get("verdict") == "cripple" and owner in event.actors[1:]:
        return "you crippled them"
    return REASONS.get(memory.feeling)


def _belief_reason(world, variant: dict) -> str | None:
    predicate = variant.get("predicate")
    verb = VERBS.get(predicate)
    if verb is None:
        return None
    if predicate == "killed" and variant.get("soft"):
        verb = "nearly killed"
    target = world.entity(variant["target"]) if isinstance(variant.get("target"), int) else None
    whom = target.name if target else "someone"
    tail = " for dead" if predicate == "left_for_dead" else ""
    where = f" in {variant['place']}" if variant.get("place") else ""
    return f"heard you {verb} {whom}{tail}{where}"


def attitude(world, npc_id: int, subject_id: int) -> Attitude:
    npc = world.entity(npc_id)
    traits = set(npc.data.get("traits", ()))
    true_id = true_identity(world, subject_id)
    now = world.time
    terms: list[tuple[float, str | None]] = []
    for memory in world.memories(npc_id, about=true_id):
        if appears_as(world, npc_id, memory.event, true_id) != subject_id:
            continue
        value = FEELING_VALUE.get(memory.feeling, 0.0) * effective_intensity(memory, now)
        if value:
            terms.append((value, _memory_reason(world, npc_id, memory)))
    seen = identities(world, npc_id, true_id) if subject_id == true_id else {subject_id}
    best: dict[int, tuple[float, str | None]] = {}
    for belief, fact in knowledge_of(world, npc_id):
        if belief.variant.get("actor") not in seen or fact.object == npc_id:
            continue  # things done to them are already in their memories
        value = judgement(world, fact.predicate, belief.variant.get("target"), traits, fact.weight) \
            * belief.confidence * fact.weight
        if value and (fact.id not in best or abs(value) > abs(best[fact.id][0])):
            best[fact.id] = (value, _belief_reason(world, belief.variant))
    terms += list(best.values())
    if "kind" in traits:
        terms.append((0.2, None))
    if "hot-tempered" in traits:
        terms.append((-0.1, None))
    if subject_id != true_id:
        terms.append((-0.2, "you hide your face"))
    score = round(sum(value for value, _ in terms), 3)
    reasons = sorted(((abs(value), reason) for value, reason in terms if reason), key=lambda p: -p[0])
    return Attitude(score, word_for(score), reasons[0][1] if reasons else None)


def afraid(world, npc_id: int, subject_id: int) -> bool:
    """Weaker than the subject is believed to be, and has heard they kill or cripple."""
    npc = world.entity(npc_id)
    true_id = true_identity(world, subject_id)
    seen = identities(world, npc_id, true_id) if subject_id == true_id else {subject_id}
    harmful, believed = False, 0
    for belief, fact in knowledge_of(world, npc_id):
        if belief.variant.get("actor") not in seen:
            continue
        harmful = harmful or fact.predicate in HARM
        if fact.predicate in ("defeated", "killed", "crippled") and belief.variant.get("realm"):
            believed = max(believed, realm_index(belief.variant["realm"]))
    for memory in world.memories(npc_id, about=true_id):
        if memory.event.kind == "duel_ended" and appears_as(world, npc_id, memory.event, true_id) == subject_id:
            believed = max(believed, realm_index(world.entity(true_id).data.get("realm", "mortal")))
    return harmful and realm_index(npc.data.get("realm", "mortal")) < believed
```

- [ ] **Step 4: Write reputation** — `systems/reputation.py`
```python
"""What a town thinks of someone (phase 3a spec §9), read only from that town's gossip pool."""

from dataclasses import dataclass

from systems.attitude import is_bandit
from systems.beliefs import identities, true_identity
from world.seed import rng_for

EPITHET_RENOWN = 6.0
RENOWN_WORDS = ((2.0, "little known"), (6.0, "known"), (15.0, "renowned"))
PATH_VALUE = {"crippled": -0.7, "spared": 0.5, "defeated": 0.0, "fled_from": -0.2, "lied_about": -0.5,
              "paid_off": -0.1, "left_for_dead": -0.8, "owns_manual": 0.0}
ADJECTIVES = {
    "righteous": ("Jade", "Azure", "White", "Upright"),
    "ruthless": ("Crimson", "Blood", "Black", "Iron"),
    "hard to read": ("Wandering", "Grey", "Silent"),
}
FORM_NOUNS = {"fist": "Fist", "palm": "Palm", "sword": "Sword", "saber": "Blade", "spear": "Spear", "staff": "Staff"}


@dataclass(frozen=True)
class Reputation:
    renown: float
    word: str
    path: str
    epithet: str | None


def renown_word(renown: float) -> str:
    if renown <= 0:
        return "unknown"
    for limit, word in RENOWN_WORDS:
        if renown < limit:
            return word
    return "famous"


def path_value(world, predicate: str, target_id) -> float:
    target = world.entity(target_id) if isinstance(target_id, int) else None
    if predicate == "killed":
        if target is not None and target.data.get("beast"):
            return 0.3
        return 1.0 if is_bandit(target) else -1.0
    if predicate == "robbed":
        return 0.2 if is_bandit(target) else -0.6
    return PATH_VALUE.get(predicate, 0.0)


def reputation(world, town_id: int, subject_id: int) -> Reputation:
    true_id = true_identity(world, subject_id)
    seen = identities(world, town_id, true_id) if subject_id == true_id else {subject_id}
    best: dict = {}
    for belief, fact in world.known_facts(town_id):
        if belief.variant.get("actor") not in seen or fact.predicate == "is":
            continue
        if fact.id not in best or belief.confidence > best[fact.id][0].confidence:
            best[fact.id] = (belief, fact)
    renown = round(sum(f.weight * b.confidence for b, f in best.values()), 3)
    if renown <= 0:
        return Reputation(0.0, "unknown", "hard to read", None)
    lean = sum(path_value(world, f.predicate, b.variant.get("target")) * f.weight * b.confidence
               for b, f in best.values()) / renown
    path = "righteous" if lean >= 0.3 else "ruthless" if lean <= -0.3 else "hard to read"
    epithet = None
    if renown >= EPITHET_RENOWN:
        belief, _ = max(best.values(), key=lambda p: (p[1].weight * p[0].confidence, p[1].id))
        rng = rng_for(world.world_seed, f"epithet:{subject_id}:{town_id}")
        noun = FORM_NOUNS.get(belief.variant.get("form"), "Hand")
        place = belief.variant.get("place") or world.entity(town_id).name
        epithet = f"{rng.choice(ADJECTIVES[path])} {noun} of {place}"
    return Reputation(renown, renown_word(renown), path, epithet)
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_attitude.py -q -p no:cacheprovider`
Expected: `10 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: attitudes and town reputations computed from memories and rumours"`

---

### Task 5: Killing, kin, inheritance, left for dead

**Files:**
- Create: `systems/kin.py`
- Modify (via `.patches/3a_task5.py`):
  - `systems/duel.py`, `systems/encounters.py`, `systems/facts.py`
  - `engine/fight.py`, `engine/commands.py`, `engine/game.py` (help line)
  - `narrate/combat_text.py`, `narrate/grammar/combat.toml`
  - `debug/invariants.py` (the dead are buried, not placed)
  - `tests/test_fight_flow.py` (verdict menu ruling)
- Test: `tests/test_kin.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces:
  - `systems.kin`:
    - `KIN_ROLES`, `INVERSE`, `PAUSE_WATCHES = 360`.
    - `kin_slots(world, npc) -> list[dict]`, `ensure_kin(world, npc_id, origin=None) -> list[(kin_id, role)]`, `kin_of(world, npc_id) -> list[(kin_id, role)]` (living only, materialized only).
    - `avengers_for(world, player) -> list[int]`, `grief_role(world, avenger, player) -> str | None`.
    - Effect `died`, listener `died` (inheritance), a kin channel `on_fact`, and a listener `duel_ended` (sparing an avenger pauses the hunt).
  - `systems.duel`:
    - `VERDICTS = ("spare", "rob", "cripple", "kill")`, `BEAST_VERDICTS = ("spare", "kill")`, `HATEFUL`.
    - `verdict_events(..., "kill")` returns `[duel_ended, died]`.
    - `npc_verdict(rng, opponent, player_silver, hateful=False)` can return `"leave_for_dead"`.
    - `duel_ended` data gains `killed` and `left_for_dead`.
  - `systems.encounters._free_roamer_slot(world, region) -> int`.
  - Relation `kin_of` (a → b, `data={"role": r}`) means "b is a's r". The `died` event actors are `(killer, victim)`.

- [ ] **Step 1: Write the failing test** — `tests/test_kin.py`
```python
import pytest

import systems.duel as duel
import systems.encounters as encounters
from engine.commands import parse
from engine.game import Action, Game
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.kin import avengers_for, ensure_kin, kin_of
from systems.realms import realm_index
from world.events import Event, Witness, commit
from world.gen.materialize import people_at, region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("curious", "lazy"), realm="mortal", seed=None):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": "innkeeper", "traits": list(traits), "realm": realm, "surname": surname, "given": given,
        "gender": "man", "age": 40, "portrait": {"hair": 0, "face": 0, "robe": 0}}, seed)
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def at_mercy(game, npc):
    [sid] = commit(game.world, duel.start_events(game.world, game.player.id, npc, game.place.id, "duel"))
    d = duel.Duel.from_event(sid, game.world.chronicle_entry(sid))
    d.stage, d.harm = "verdict", {"player": 10.0, "opponent": 90.0}
    return d


def test_killing_leaves_a_body_a_fact_and_a_grieving_family(game):
    victim = person(game, "Wang Li")
    events = duel.verdict_events(game.world, at_mercy(game, victim), "kill")
    assert [e.kind for e in events] == ["duel_ended", "died"]
    commit(game.world, events)
    assert game.world.entity(victim).data["dead"]
    assert game.world.targets(victim, "located_in") == []
    assert game.world.targets(victim, "buried_at") == [game.place.id]
    assert victim not in [p.id for p in people_at(game.world, game.place.id)]
    killed = game.world.facts(predicate="killed")[0]
    assert (killed.subject, killed.object, killed.weight) == (game.player.id, victim, 3.0)
    family = kin_of(game.world, victim)
    assert 1 <= len(family) <= 3
    for relative, _role in family:
        memories = game.world.memories(relative)
        assert any(m.feeling == "grief" and m.indelible for m in memories)
        assert any(m.inherited_from == victim and m.feeling == "hatred" for m in memories)
        assert [b.channel for b in game.world.beliefs(relative) if b.fact_id == killed.id] == ["kin"]
    assert set(avengers_for(game.world, game.player.id)) == {r for r, _ in family}


def test_kin_are_seeded_and_share_a_surname_by_blood(game, tmp_path):
    victim = person(game, "Wang Li", seed="test/wang")
    family = ensure_kin(game.world, victim)
    for relative, role in family:
        entity = game.world.entity(relative)
        if role in ("sibling", "parent", "child"):
            assert entity.data["surname"] == "Wang"
        if role == "master":
            assert realm_index(entity.data["realm"]) >= 1
        assert (victim, {"sibling": "sibling", "parent": "child", "child": "parent",
                         "master": "disciple", "disciple": "master"}[role]) in kin_of(game.world, relative)
    assert ensure_kin(game.world, victim) == family
    other = Game.new(tmp_path / "h.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    twin = person(other, "Wang Li", seed="test/wang")
    assert [other.world.entity(r).name for r, _ in ensure_kin(other.world, twin)] == \
        [game.world.entity(r).name for r, _ in family]
    other.close()


def test_a_hateful_foe_leaves_you_for_dead(game):
    foe = person(game, "Iron Gu", traits=("proud", "honest"), realm="first-rate")
    commit(game.world, [Event("insulted", (game.player.id, foe), game.place.id, {},
                              witnesses=(Witness(foe, "hatred", 1.0),))])
    d = at_mercy(game, foe)
    d.stage = "fighting"
    [end] = duel.yield_events(game.world, d)
    assert end.data["verdict"] == "leave_for_dead" and end.data["left_for_dead"]
    commit(game.world, [end])
    body = load_body(game.world, game.player.id)
    assert any(i.location == "torso" and i.kind == "internal" and i.severity == 4 for i in body.injuries)
    assert game.world.facts(predicate="left_for_dead")[0].subject == foe


def test_sparing_an_avenger_calls_off_the_hunt_for_a_season(game):
    victim = person(game, "Wang Li")
    commit(game.world, duel.verdict_events(game.world, at_mercy(game, victim), "kill"))
    avenger = avengers_for(game.world, game.player.id)[0]
    game.world.unrelate(avenger, "located_in")
    game.world.relate(avenger, game.place.id, "located_in")
    commit(game.world, duel.verdict_events(game.world, at_mercy(game, avenger), "spare"))
    assert avenger not in avengers_for(game.world, game.player.id)
    game.world.set_time(game.world.time + 361)
    assert avenger in avengers_for(game.world, game.player.id)


def test_a_masked_killer_is_not_hunted_by_those_who_do_not_know(game):
    victim = person(game, "Wang Li")
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    events = [Event(e.kind, e.actors, e.place, {**e.data, "as": persona}, witnesses=e.witnesses)
              for e in duel.verdict_events(game.world, at_mercy(game, victim), "kill")]
    commit(game.world, events)
    assert game.world.facts(predicate="killed")[0].subject == persona
    assert kin_of(game.world, victim)
    assert avengers_for(game.world, game.player.id) == []


def test_beasts_can_be_killed_but_not_robbed(game):
    wolf = game.world.add_entity("person", "a grey wolf", {"beast": True, "realm": "mortal", "occupation": "grey wolf",
                                                          "traits": ["hot-tempered"]})
    game.world.relate(wolf, game.place.id, "located_in")
    d = at_mercy(game, wolf)
    assert duel.verdict_events(game.world, d, "rob") == []
    commit(game.world, duel.verdict_events(game.world, d, "kill"))
    assert game.world.entity(wolf).data["dead"]
    assert game.world.facts(predicate="killed")[0].weight == 0.5
    assert kin_of(game.world, wolf) == []


def test_a_dead_roamer_is_never_met_again(game):
    region = region_of(game.world, game.place.id)
    first = encounters.make_roamer(game.world, region, "bandit", 0, 0.1)
    commit(game.world, [Event("died", (game.player.id, first), game.place.id, {"cause": "killed"})])
    assert encounters.roamers(game.world, region.id) == []
    slot = encounters._free_roamer_slot(game.world, region)
    assert slot == 1
    assert encounters.make_roamer(game.world, region, "bandit", slot, 0.1) != first


def test_the_verdict_menu_offers_kill_and_the_word_works(game):
    victim = person(game, "Wang Li", traits=("proud", "honest"))
    game.perform(Action("challenge", victim))
    game.combat.stage, game.combat.harm = "verdict", {"player": 0.0, "opponent": 90.0}
    turn = game.perform(Action("look"))
    assert Action("verdict", "kill") in [c.action for c in turn.choices]
    turn = game.perform(Action("verdict", "kill"))
    assert "You kill Wang Li." in [text for text, _ in turn.lines]
    assert game.world.entity(victim).data["dead"]
    assert parse("kill", [], []) == Action("verdict", "kill")
    assert any("Killed Wang Li." in text for text, _ in game.perform(Action("journal")).lines)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_kin.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.kin'`.

- [ ] **Step 3: Write kin** — `systems/kin.py`
```python
"""Families and teachers (phase 3a spec §6): generated only when needed, and heirs to grudges.

Relation kin_of (a -> b, data {"role": r}) reads "b is a's r". A death passes the
victim's indelible memories to their kin, who also grieve; kin hear of anything
done to or by their family at once, wherever they live (channel 3).
"""

from systems.beliefs import CONF_DECAY, appears_as, believe
from systems.facts import on_fact
from systems.realms import REALMS, realm_index
from world.events import effect, listen
from world.gen.materialize import ensure_town, region_of
from world.gen.names import person_name
from world.gen.npc import OCCUPATIONS, PORTRAIT_PARTS, TRAITS
from world.gen.npc import REALMS as NPC_REALMS
from world.gen.region import region_spec
from world.seed import rng_for

KIN_ROLES = ("sibling", "parent", "child", "master", "disciple")
INVERSE = {"sibling": "sibling", "parent": "child", "child": "parent", "master": "disciple", "disciple": "master"}
BLOOD = frozenset({"sibling", "parent", "child"})
NEAR_CHANCE = 0.7
FAR = 2                 # regions
PAUSE_WATCHES = 360     # a spared avenger stops hunting for a season
AGE_SHIFT = {"parent": (18, 30), "child": (-30, -18), "sibling": (-8, 8), "master": (10, 30), "disciple": (-20, -5)}


def _key(npc) -> str:
    return npc.seed_path or f"person:{npc.id}"


def kin_slots(world, npc) -> list[dict]:
    rng = rng_for(world.world_seed, f"{_key(npc)}/kin")
    return [{"i": i, "role": rng.choice(KIN_ROLES), "near": rng.random() < NEAR_CHANCE,
             "dx": rng.randint(-FAR, FAR), "dy": rng.randint(-FAR, FAR), "town": rng.randrange(8)}
            for i in range(rng.randint(1, 3))]


def _home(world, origin_id: int, slot: dict) -> int:
    origin = world.entity(origin_id)
    if slot["near"] and origin.kind == "town":
        return origin.id
    region = origin if origin.kind == "region" else region_of(world, origin.id)
    if slot["near"]:
        return ensure_town(world, region.data["x"], region.data["y"], 0)
    x, y = region.data["x"] + slot["dx"], region.data["y"] + slot["dy"]
    return ensure_town(world, x, y, slot["town"] % region_spec(world.world_seed, x, y).town_count)


def _make_kin(world, npc, slot: dict, path: str, home: int) -> int:
    rng = rng_for(world.world_seed, path)
    surname, given = person_name(rng)
    if slot["role"] in BLOOD and npc.data.get("surname"):
        surname = npc.data["surname"]
    low, high = AGE_SHIFT[slot["role"]]
    age = max(8, min(90, int(npc.data.get("age", 30)) + rng.randint(low, high)))
    realm = rng.choice(NPC_REALMS)
    if slot["role"] == "master":
        realm = REALMS[min(realm_index(npc.data.get("realm", "mortal")) + 1, 3)].label
    data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": age,
            "occupation": rng.choice(OCCUPATIONS), "traits": rng.sample(TRAITS, 2), "realm": realm,
            "portrait": {part: rng.randrange(count) for part, count in PORTRAIT_PARTS.items()}}
    person = world.add_entity("person", f"{surname} {given}", data, path)
    world.relate(person, home, "located_in")
    return person


def kin_of(world, npc_id: int) -> list[tuple[int, str]]:
    """Living kin already in the world."""
    out = []
    for kin, _, data in world.relations_from(npc_id, "kin_of"):
        entity = world.entity(kin)
        if entity is not None and not entity.data.get("dead"):
            out.append((kin, data.get("role")))
    return out


def ensure_kin(world, npc_id: int, origin: int | None = None) -> list[tuple[int, str]]:
    """Materialize this person's seeded kin once (at a death, a question, a rumour)."""
    npc = world.entity(npc_id)
    if npc is None or npc.kind != "person" or npc.data.get("beast") or npc.data.get("is_player"):
        return []
    if npc.data.get("kin_ready"):
        return kin_of(world, npc_id)
    origin = origin or next(iter(world.targets(npc_id, "located_in")), None)
    with world.transaction():
        if origin is not None:
            for slot in kin_slots(world, npc):
                path = f"{_key(npc)}/kin:{slot['i']}"
                found = world.entity_by_seed(path)
                person = found.id if found else _make_kin(world, npc, slot, path, _home(world, origin, slot))
                world.relate(npc_id, person, "kin_of", data={"role": slot["role"]})
                world.relate(person, npc_id, "kin_of", data={"role": INVERSE[slot["role"]]})
        world.update_data(npc_id, kin_ready=True)
    return kin_of(world, npc_id)


@effect("died")
def _died(world, event) -> None:
    _killer, victim = event.actors
    world.update_data(victim, dead=True, died_at=world.time)
    world.unrelate(victim, "located_in")
    if event.place is not None:
        world.relate(victim, event.place, "buried_at")


@listen("died")
def _inherit(world, event, event_id: int) -> None:
    killer, victim = event.actors
    for relative, _role in ensure_kin(world, victim, origin=event.place):
        if relative == killer:
            continue
        for memory in world.memories(victim):
            if memory.indelible:
                world.add_memory(relative, memory.event.id, memory.feeling, memory.intensity, True,
                                 inherited_from=victim, ignore_existing=True)
        world.add_memory(relative, event_id, "grief", 1.0, True, ignore_existing=True)


@on_fact
def _kin_hear(world, fact) -> None:
    """Channel 3: kin hear of what was done to or by their family, wherever they are."""
    if fact.predicate == "killed" and fact.object is not None:
        ensure_kin(world, fact.object, origin=fact.place)
    for someone in (fact.subject, fact.object):
        entity = world.entity(someone) if someone is not None else None
        if entity is None or entity.kind != "person":
            continue
        for relative, _role in kin_of(world, someone):
            if relative in (fact.subject, fact.object):
                continue
            believe(world, relative, fact.id, fact.variant, someone, CONF_DECAY, 1, "kin")


def avengers_for(world, player_id: int) -> list[int]:
    """Living people grieving a killing they know the player did, and not resting from the hunt."""
    now, found = world.time, []
    for memory in world.memories_with_feeling("grief"):
        if memory.event.kind != "died" or memory.event.actors[0] != player_id or memory.owner in found:
            continue
        person = world.entity(memory.owner)
        if person is None or person.kind != "person" or person.data.get("dead"):
            continue
        if person.data.get("pursuit_paused_until", -1) > now:
            continue
        if appears_as(world, memory.owner, memory.event, player_id) != player_id:
            continue  # they grieve, but do not know it was you
        found.append(memory.owner)
    return found


def grief_role(world, avenger: int, player_id: int) -> str | None:
    """Who the player killed, as this avenger would say it: 'my brother' -> 'sibling'."""
    for memory in world.memories(avenger, about=player_id):
        if memory.feeling == "grief" and memory.event.kind == "died":
            for kin, _, data in world.relations_from(avenger, "kin_of"):
                if kin == memory.event.actors[1]:
                    return data.get("role")
    return None


@listen("duel_ended")
def _avenger_spared(world, event, event_id: int) -> None:
    d = event.data
    if d.get("result") == "won" and d.get("verdict") == "spare":
        opponent = event.actors[1]
        if opponent in avengers_for(world, event.actors[0]):
            world.update_data(opponent, pursuit_paused_until=world.time + PAUSE_WATCHES)
```

- [ ] **Step 4: Edit the existing files** — `.patches/3a_task5.py`
```python
"""Task 5 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    file = Path(path)
    file.write_text(file.read_text(encoding="utf-8").rstrip("\n") + "\n" + text, encoding="utf-8", newline="\n")


DUEL = "systems/duel.py"
edit(DUEL, 'LEGS = ("left leg", "right leg")\n', '''LEGS = ("left leg", "right leg")
VERDICTS = ("spare", "rob", "cripple", "kill")
BEAST_VERDICTS = ("spare", "kill")
HATEFUL = frozenset({"hatred", "grief", "wronged"})  # a foe who feels this leaves you for dead
''')
edit(DUEL, '''def npc_verdict(rng, opponent, player_silver: int) -> tuple[str, int, list | None]:''',
     '''def npc_verdict(rng, opponent, player_silver: int, hateful: bool = False) -> tuple[str, int, list | None]:''')
edit(DUEL, '''    amount = int(player_silver * rng.uniform(0.3, 1.0)) if greedy else 0
''', '''    amount = int(player_silver * rng.uniform(0.3, 1.0)) if greedy else 0
    if hateful:
        return "leave_for_dead", amount, None  # a grudge wants you broken (phase 3a spec 6.2)
''')
edit(DUEL, '''        "fragment": None, "purpose": d.purpose,
    }''', '''        "fragment": None, "purpose": d.purpose, "killed": False, "left_for_dead": False,
    }''')
edit(DUEL, '''        chosen, amount, crippled = npc_verdict(rng, opponent, silver_of(world, d.player))
        data.update(verdict=chosen, by="opponent", silver=amount, crippled=crippled,
                    insight=5.0 * gap if gap > 0 else 0.0)''', '''        hateful = any(m.feeling in HATEFUL for m in world.memories(d.opponent, about=d.player))
        chosen, amount, crippled = npc_verdict(rng, opponent, silver_of(world, d.player), hateful)
        data.update(verdict=chosen, by="opponent", silver=amount, crippled=crippled,
                    insight=5.0 * gap if gap > 0 else 0.0, left_for_dead=chosen == "leave_for_dead")''')
edit(DUEL, '''        if verdict == "rob":
            data["silver"] = silver_of(world, d.opponent)''', '''        if verdict in ("rob", "kill"):
            data["silver"] = silver_of(world, d.opponent)''')
edit(DUEL, '''            "cripple": ("hatred", 1.0, True),
        }[verdict]
        witnesses.append(Witness(d.opponent, feeling, weight, lasting))''', '''            "cripple": ("hatred", 1.0, True),
            "kill": ("hatred", 1.0, True),
        }[verdict]
        witnesses.append(Witness(d.opponent, feeling, weight, lasting))
        data["killed"] = verdict == "kill"''')
edit(DUEL, '''def verdict_events(world, d: Duel, choice: str) -> list[Event]:
    if d.stage != "verdict" or choice not in ("spare", "rob", "cripple"):
        return []
    rng = rng_for(world.world_seed, f"duel:{d.duel_id}:verdict")
    reason = "broken" if d.harm["opponent"] >= BROKEN else "yielded"
    return [_end_event(world, d, "won", reason, rng, d.harm, d.exchange, verdict=choice)]''',
     '''def verdict_events(world, d: Duel, choice: str) -> list[Event]:
    beast = bool(world.entity(d.opponent).data.get("beast"))
    if d.stage != "verdict" or choice not in (BEAST_VERDICTS if beast else VERDICTS):
        return []
    if choice == "kill" and d.mode not in ("duel", "encounter"):
        return []
    rng = rng_for(world.world_seed, f"duel:{d.duel_id}:verdict")
    reason = "broken" if d.harm["opponent"] >= BROKEN else "yielded"
    events = [_end_event(world, d, "won", reason, rng, d.harm, d.exchange, verdict=choice)]
    if choice == "kill":
        events.append(Event("died", (d.player, d.opponent), d.place, {"cause": "killed"}))
    return events''')
edit(DUEL, '''    for item in data["loot"]:
        world.unrelate(opponent, "owns", item)''', '''    if data.get("left_for_dead"):
        body = load_body(world, player)
        add_injury(body, "torso", "internal", 4, world.time, f"being left for dead by {world.entity(opponent).name}")
        save_body(world, player, body)
    for item in data["loot"]:
        world.unrelate(opponent, "owns", item)''')

ENC = "systems/encounters.py"
edit(ENC, '''        person = make_roamer(world, region, kind, len(roamers(world, region.id)), danger)''',
     '''        person = make_roamer(world, region, kind, _free_roamer_slot(world, region), danger)''')
edit(ENC, '''def encounter_events(''', '''def _free_roamer_slot(world, region) -> int:
    """The next roamer seed slot whose person is not dead: the dead are never met again."""
    index = len(roamers(world, region.id))
    while (someone := world.entity_by_seed(f"{region.seed_path}/roamer:{index}")) is not None \\
            and someone.data.get("dead"):
        index += 1
    return index


def encounter_events(''')

edit("systems/facts.py", "import systems.rumours  # noqa: E402,F401\n",
     "import systems.rumours  # noqa: E402,F401\nimport systems.kin  # noqa: E402,F401\n")

FIGHT = "engine/fight.py"
edit(FIGHT, '''            return [Choice(f"Let {opponent.name} limp away", Action("verdict", "spare"))]''',
     '''            return [Choice(f"Let {opponent.name} limp away", Action("verdict", "spare")),
                    Choice(f"Kill {opponent.name}", Action("verdict", "kill"))]''')
edit(FIGHT, '''            Choice(f"Cripple {opponent.name}", Action("verdict", "cripple")),
        ]''', '''            Choice(f"Cripple {opponent.name}", Action("verdict", "cripple")),
            Choice(f"Kill {opponent.name}", Action("verdict", "kill")),
        ]''')
edit(FIGHT, '''"Spare, rob or cripple?"''', '''"Spare, rob, cripple or kill?"''')
edit(FIGHT, '''            return self._turn([("Spare, rob, cripple or kill?", "system")])
        lines = self._commit(events)
        return self._turn(lines + self._finish_duel(events[-1].data))''', '''            return self._turn([("Spare, rob, cripple or kill?", "system")])
        lines = self._commit(events)
        return self._turn(lines + self._finish_duel(events[0].data))  # a kill adds a `died` event after it''')

edit("engine/commands.py", '''"cripple": Action("verdict", "cripple"),''',
     '''"cripple": Action("verdict", "cripple"), "kill": Action("verdict", "kill"),''')
edit("engine/game.py", '''flee | yield | spare | rob | cripple"''', '''flee | yield | spare | rob | cripple | kill"''')

CT = "narrate/combat_text.py"
edit(CT, '''        if d["verdict"] == "spare":
            lines.append("You let them go.")
        if d["silver"] or d["loot"]:''', '''        if d["verdict"] == "spare":
            lines.append("You let them go.")
        if d["verdict"] == "kill":
            lines.append(f"You kill {name}.")
        if d["silver"] or d["loot"]:''')
edit(CT, '''        if d["verdict"] == "spare":
            lines.append("They let you go.")''', '''        if d["verdict"] == "spare":
            lines.append("They let you go.")
        if d["verdict"] == "leave_for_dead":
            lines.append("They leave you for dead.")''')
edit(CT, '''def _ended_line(world, entry, names, place, other):
    return cap(RESULT_WORDS[entry.data["result"]].format(other=other))''', '''def _ended_line(world, entry, names, place, other):
    if entry.data.get("killed"):
        return f"Killed {other}."
    return cap(RESULT_WORDS[entry.data["result"]].format(other=other))


@outcome("died", body_facts=False)
def _died(world, event):
    return [f"{cap(_name(world, event))} is dead."], {}


@summary("died")
def _died_line(world, entry, names, place, other):
    return f"{cap(other)} died by your hand."''')
append("narrate/grammar/combat.toml", '''
[died]
colour = "default"
lines = ["The body goes still.", "It is over; the dust settles on the body.", "Silence falls where the fight was.", "The last breath goes out of them.", "Somewhere a door closes, and then nothing.", "No one moves for a long moment."]
''')

edit("debug/invariants.py", '''        places = world.targets(person.id, "located_in")
        if len(places) != 1:
            problems.append(f"{person.name} (#{person.id}) has {len(places)} locations")''', '''        places = world.targets(person.id, "located_in")
        if person.data.get("dead"):
            if places or len(world.targets(person.id, "buried_at")) != 1:
                problems.append(f"{person.name} (#{person.id}) is dead but not properly buried")
        elif len(places) != 1:
            problems.append(f"{person.name} (#{person.id}) has {len(places)} locations")''')

# Ruling: the 2b verdict menu gains Kill (phase 3a spec 6.2).
edit("tests/test_fight_flow.py", '''[Action("verdict", "spare"), Action("verdict", "rob"), Action("verdict", "cripple")]''',
     '''[Action("verdict", "spare"), Action("verdict", "rob"), Action("verdict", "cripple"), Action("verdict", "kill")]''')
print("task 5 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3a_task5.py && .venv/Scripts/python.exe -m pytest tests/test_kin.py -q -p no:cacheprovider`
Expected: `task 5 edits applied`, then `8 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass, including the fuzz tests. Random verdict presses can now kill, and the dead-are-buried rule holds.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: kill verdict, kin who inherit grudges, avengers, left for dead"`

---
### Task 6: The world reacts: fear, avengers, rivals, bandits backing off, refusals

**Files:**
- Modify (via `.patches/3a_task6.py`):
  - `systems/encounters.py`, `systems/duel.py`, `systems/learning.py`
  - `engine/roads.py`, `engine/fight.py`, `engine/dealings.py`
  - `narrate/road_text.py`, `narrate/combat_text.py`, `narrate/grammar/roads.toml`
- Test: `tests/test_reactions.py`

**Interfaces:**
- Consumes: Task 4 (`afraid`, `attitude`, `reputation`, `EPITHET_RENOWN`), Task 5 (`avengers_for`, `grief_role`) and Task 2 (`apparent_to`, `home_of`, `appears_as`).
- Produces:
  - `systems.encounters`:
    - Constants: `AVENGER_CHANCE = 0.6`, `RIVAL_CHANCE = 0.2`, `AVENGER_ROAD_CHANCE = 0.25`, `AVENGER_RANGE = 3`, and `GRUDGE_FEELINGS`, which gains `grief` and `wronged`.
    - Functions: `backs_off(world, bandit, player, town_id) -> bool`, `encounter_events(..., extra=None)`, `talk_succeeds(world, person, player, kind=None)`.
    - Encounter kind `avenger`, with data `{"role"}`, and resolution `how="backed_off"`.
  - `systems.duel`: `refusal_events(player, npc, place, mode, reason="unwilling")`. `accepts` returns False when the NPC is afraid.
  - `systems.learning`: `will_deal(world, npc, player) -> bool` and `will_teach(world, npc, player, town) -> bool`.
  - `engine.roads.RoadsMixin._grudges() -> list[Line]`, which runs on arrival and on look.

- [ ] **Step 1: Write the failing test** — `tests/test_reactions.py`
```python
import pytest

import systems.encounters as encounters
import systems.learning as learning
from engine.game import Action, Game
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event, Witness, commit
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("curious", "lazy"), realm="mortal", occupation="innkeeper", town=None):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": occupation, "traits": list(traits), "realm": realm, "surname": surname, "given": given,
        "gender": "man", "age": 40, "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, town or game.place.id, "located_in")
    return pid


def grieving(game, name="Wang Da", traits=("curious", "lazy")):
    """Someone whose brother the player killed, and who knows it."""
    npc = person(game, name, traits=traits)
    victim = game.world.add_entity("person", "Wang Li", {"dead": True, "realm": "mortal"})
    game.world.relate(victim, game.place.id, "buried_at")
    game.world.relate(npc, victim, "kin_of", data={"role": "sibling"})
    with game.world.transaction():
        eid = game.world.append_chronicle("died", (game.player.id, victim), game.place.id, {"cause": "killed"}, 1.0)
        game.world.add_memory(npc, eid, "grief", 1.0, True)
    return npc


def deed(game, actor, predicate, target, **story):
    return record_fact(game.world, actor, predicate, target, place=game.place.id,
                       variant=make_variant(predicate, actor, target, place=game.place.name, **story))


def renowned(game):
    for name in ("Ma Bo", "Ma Da", "Ma San"):
        deed(game, game.player.id, "killed", person(game, name, occupation="bandit"), form="fist")


def north(game):
    return next(c.action for c in game.start().all_choices if c.action.verb == "travel" and "north" in c.label)


def test_an_avenger_in_town_calls_you_out(game, monkeypatch):
    monkeypatch.setattr(encounters, "AVENGER_CHANCE", 1.0)
    npc = grieving(game)
    game.perform(Action("look"))
    assert game.challenger == npc


def test_an_avenger_hunts_you_on_the_road(game, monkeypatch):
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "AVENGER_ROAD_CHANCE", 1.0)
    road = north(game)  # before the avenger exists: in town they would call you out on look
    npc = grieving(game)
    turn = game.perform(road)
    assert game.encounter == {"person": npc, "kind": "avenger", "toll": 0}
    assert any('"You killed my sibling."' in text for text, _ in turn.lines)
    assert "road" in {c.action.verb for c in turn.choices}
    game.perform(Action("road", "talk"))
    assert game.combat is not None and game.combat.opponent == npc


def test_the_afraid_refuse_to_fight(game):
    weak = person(game, "Hu Mei")
    deed(game, game.player.id, "killed", person(game, "Wang Li", realm="third-rate"), realm="third-rate")
    game.perform(Action("talk", weak))
    turn = game.perform(Action("challenge", weak))
    assert game.combat is None
    assert "Hu Mei backs away; they want no part of you." in [text for text, _ in turn.lines]


def test_hostile_people_neither_teach_nor_sell(game):
    npc = person(game, "Old Wu", occupation="merchant")
    commit(game.world, [Event("insulted", (game.player.id, npc), game.place.id, {},
                              witnesses=(Witness(npc, "hatred", 1.0),))])
    assert not learning.will_deal(game.world, npc, game.player.id)
    turn = game.perform(Action("talk", npc))
    assert not {"learn_menu", "browse"} & {c.action.verb for c in turn.all_choices}
    assert game.perform(Action("browse")).lines[-1][1] == "system"


def test_the_honest_will_not_teach_a_ruthless_name(game):
    teacher = person(game, "Old Wu", traits=("honest", "greedy"))
    deed(game, game.player.id, "robbed", person(game, "Hu Mei"))
    assert learning.will_deal(game.world, teacher, game.player.id)
    assert not learning.will_teach(game.world, teacher, game.player.id, game.place.id)
    greedy = person(game, "Ma Bo", traits=("greedy", "lazy"))
    assert learning.will_teach(game.world, greedy, game.player.id, game.place.id)


def test_bandits_back_off_from_a_renowned_fighter(game):
    renowned(game)
    game.world.update_data(game.player.id, realm="third-rate")
    region = encounters.region_of(game.world, game.place.id)
    bandit = encounters.make_roamer(game.world, region, "bandit", 0, 0.1)
    game.world.update_data(bandit, realm="mortal")
    assert encounters.backs_off(game.world, bandit, game.player.id, game.place.id)
    events = encounters.encounter_events(game.player.id, bandit, game.place.id, "bandit", 5) + \
        encounters.resolved_events(game.player.id, bandit, game.place.id, "backed_off", "bandit")
    lines = game._commit(events)
    assert encounters.pending_encounter(game.world, game.player.id) is None
    assert any("thinks better of it" in text for text, _ in lines)
    game.world.update_data(bandit, realm="first-rate")
    assert not encounters.backs_off(game.world, bandit, game.player.id, game.place.id)


def test_a_proud_stronger_rival_calls_out_the_renowned(game, monkeypatch):
    monkeypatch.setattr(encounters, "RIVAL_CHANCE", 1.0)
    renowned(game)
    person(game, "Iron Gu", traits=("proud", "lazy"), realm="second-rate")
    picked = game.world.entity(encounters.challenge_from(game.world, game.player.id, game.place.id))
    assert "proud" in picked.data["traits"] and picked.data["realm"] != "mortal"


def test_grudges_are_answered_on_arrival_too(game, monkeypatch):
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 1.0)
    road = north(game)
    town = ensure_town(game.world, *road.target)
    hothead = person(game, "Hot Wu", traits=("hot-tempered", "lazy"), town=town)
    commit(game.world, [Event("parted", (game.player.id, hothead), town, {},
                              witnesses=(Witness(hothead, "annoyed", 0.5),))])
    game.perform(road)
    assert game.challenger == hothead
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_reactions.py -q -p no:cacheprovider`
Expected: failures, including `AttributeError: module 'systems.encounters' has no attribute 'AVENGER_CHANCE'` and `module 'systems.learning' has no attribute 'will_deal'`.

- [ ] **Step 3: Edit the existing files** — `.patches/3a_task6.py`
```python
"""Task 6 edits to existing files. Each edit must match `count` times (default once)."""
from pathlib import Path


def edit(path: str, old: str, new: str, count: int = 1) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != count:
        raise SystemExit(f"{path}: expected {count} match(es) for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def append(path: str, text: str) -> None:
    file = Path(path)
    file.write_text(file.read_text(encoding="utf-8").rstrip("\n") + "\n" + text, encoding="utf-8", newline="\n")


ENC = "systems/encounters.py"
edit(ENC, '''from systems.duel import fighter_for
''', '''from systems.beliefs import appears_as, apparent_to, home_of
from systems.duel import fighter_for
from systems.kin import avengers_for, grief_role
from systems.reputation import EPITHET_RENOWN, reputation
''')
edit(ENC, '''GRUDGE_FEELINGS = frozenset({"annoyed", "humiliated", "hatred"})  # spec §10; contempt is theirs, not a grudge
''', '''GRUDGE_FEELINGS = frozenset({"annoyed", "humiliated", "hatred", "grief", "wronged"})  # contempt is theirs, not a grudge
AVENGER_CHANCE = 0.6        # an avenger in town calls you out
RIVAL_CHANCE = 0.2          # a proud, stronger fighter calls out a renowned one
AVENGER_ROAD_CHANCE = 0.25  # an avenger from elsewhere finds you on the road
AVENGER_RANGE = 3           # regions from their home
''')
edit(ENC, '''    if rng.random() >= danger * ENCOUNTER_CHANCE:
        return []''', '''    if rng.random() >= danger * ENCOUNTER_CHANCE:
        return _avenger_events(world, player, town, rng)''')
edit(ENC, '''    toll = max(5, int(silver_of(world, player) * 0.2)) if kind == "bandit" else 0
    return encounter_events(player, person, town.id, kind, toll)''', '''    toll = max(5, int(silver_of(world, player) * 0.2)) if kind == "bandit" else 0
    if kind == "bandit" and backs_off(world, person, player, town.id):
        return (encounter_events(player, person, town.id, kind, toll)
                + resolved_events(player, person, town.id, "backed_off", kind))
    return encounter_events(player, person, town.id, kind, toll)


def backs_off(world, bandit: int, player: int, town_id: int) -> bool:
    """A weaker bandit who has heard of a renowned fighter thinks better of it (phase 3a spec 9)."""
    known_as = apparent_to(world, town_id, player)
    if reputation(world, town_id, known_as).renown < EPITHET_RENOWN:
        return False
    theirs = realm_index(world.entity(bandit).data.get("realm", "mortal"))
    return theirs < realm_index(world.entity(player).data.get("realm", "mortal"))


def _avenger_events(world, player: int, town, rng) -> list[Event]:
    """Someone who grieves at your hand may be waiting on the road (phase 3a spec 6.3)."""
    here = region_of(world, town.id).data
    for avenger in avengers_for(world, player):
        home = home_of(world, avenger)
        if home is None or home == town.id:
            continue  # at home they call you out in town instead
        there = region_of(world, home).data
        if max(abs(there["x"] - here["x"]), abs(there["y"] - here["y"])) > AVENGER_RANGE:
            continue
        if rng.random() < AVENGER_ROAD_CHANCE:
            role = grief_role(world, avenger, player) or "kin"
            return encounter_events(player, avenger, town.id, "avenger", 0, {"role": role})
    return []''')
edit(ENC, '''def encounter_events(player: int, person: int, place: int, kind: str, toll: int) -> list[Event]:
    return [Event("encounter", (player, person), place, {"kind": kind, "toll": int(toll)})]''',
     '''def encounter_events(player: int, person: int, place: int, kind: str, toll: int, extra: dict | None = None) -> list[Event]:
    return [Event("encounter", (player, person), place, {"kind": kind, "toll": int(toll), **(extra or {})})]''')
edit(ENC, '''    feeling = {"paid": "contempt", "fled": "contempt", "talked": "amused"}.get(how)''',
     '''    feeling = {"paid": "contempt", "fled": "contempt", "talked": "amused", "backed_off": "respect"}.get(how)''')
edit(ENC, '''def talk_succeeds(world, person: int, player: int) -> bool:
    entity = world.entity(person)
    if entity.data.get("beast"):
        return False
    rng = rng_for(world.world_seed, f"roadtalk:{person}:{world.time}")''', '''def talk_succeeds(world, person: int, player: int, kind: str | None = None) -> bool:
    entity = world.entity(person)
    if entity.data.get("beast"):
        return False
    rng = rng_for(world.world_seed, f"roadtalk:{person}:{world.time}")
    if kind == "avenger":
        return "kind" in entity.data.get("traits", ()) and rng.random() < 0.5''')
edit(ENC, '''def challenge_from(world, player: int, place: int) -> int | None:
    rng = rng_for(world.world_seed, f"challenge:{player}:{place}:{world.time}")
    settled = {e.actors[1] for e in world.chronicle_about(player, limit=20)
               if e.kind in ("challenge_issued", "declined_challenge") and e.time == world.time}
    for person in people_at(world, place, exclude=player):
        if person.id in settled:
            continue  # already challenged you this very moment
        if not set(person.data.get("traits", ())) & {"proud", "hot-tempered"}:
            continue
        grudges = [m for m in world.memories(person.id, about=player) if m.feeling in GRUDGE_FEELINGS]
        if grudges and rng.random() < CHALLENGE_CHANCE:
            return person.id
    return None''', '''def challenge_from(world, player: int, place: int) -> int | None:
    """Someone here who calls the player out: an avenger, a grudge-holder, or a proud rival."""
    rng = rng_for(world.world_seed, f"challenge:{player}:{place}:{world.time}")
    settled = {e.actors[1] for e in world.chronicle_about(player, limit=20)
               if e.kind in ("challenge_issued", "declined_challenge") and e.time == world.time}
    avengers = set(avengers_for(world, player))
    my_realm = realm_index(world.entity(player).data.get("realm", "mortal"))
    renowned = None
    for person in people_at(world, place, exclude=player):
        if person.id in settled:
            continue  # already challenged you this very moment
        if person.id in avengers:
            if rng.random() < AVENGER_CHANCE:
                return person.id
            continue
        traits = set(person.data.get("traits", ()))
        if not traits & {"proud", "hot-tempered"}:
            continue
        seen = apparent_to(world, person.id, player)
        grudges = [m for m in world.memories(person.id, about=player)
                   if m.feeling in GRUDGE_FEELINGS and appears_as(world, person.id, m.event, player) == seen]
        if grudges and rng.random() < CHALLENGE_CHANCE:
            return person.id
        if "proud" in traits and realm_index(person.data.get("realm", "mortal")) > my_realm:
            if renowned is None:
                renowned = reputation(world, place, apparent_to(world, place, player)).renown >= EPITHET_RENOWN
            if renowned and rng.random() < RIVAL_CHANCE:
                return person.id
    return None''')

DUEL = "systems/duel.py"
edit(DUEL, '''from systems.bodies import load_body, save_body
''', '''from systems.attitude import afraid
from systems.beliefs import apparent_to
from systems.bodies import load_body, save_body
''')
edit(DUEL, '''def accepts(world, npc_id: int, player_id: int, mode: str) -> bool:
    npc = world.entity(npc_id)''', '''def accepts(world, npc_id: int, player_id: int, mode: str) -> bool:
    if afraid(world, npc_id, apparent_to(world, npc_id, player_id)):
        return False
    npc = world.entity(npc_id)''')
edit(DUEL, '''def refusal_events(player: int, npc: int, place: int, mode: str) -> list[Event]:
    return [Event("refused_duel", (player, npc), place, {"mode": mode})]''',
     '''def refusal_events(player: int, npc: int, place: int, mode: str, reason: str = "unwilling") -> list[Event]:
    return [Event("refused_duel", (player, npc), place, {"mode": mode, "reason": reason})]''')

LEARN = "systems/learning.py"
edit(LEARN, '''from systems.duel import ensure_npc_arts
''', '''from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.duel import ensure_npc_arts
from systems.reputation import reputation
''')
edit(LEARN, '''def can_ask_to_learn(''', '''def will_deal(world, npc_id: int, player_id: int) -> bool:
    """The hostile will neither teach nor sell (phase 3a spec 3.2)."""
    return attitude(world, npc_id, apparent_to(world, npc_id, player_id)).score > -1.0


def will_teach(world, npc_id: int, player_id: int, town_id: int) -> bool:
    """And the kind and honest will not teach a name this town calls ruthless."""
    if not will_deal(world, npc_id, player_id):
        return False
    if {"kind", "honest"} & set(world.entity(npc_id).data.get("traits", ())):
        return reputation(world, town_id, apparent_to(world, town_id, player_id)).path != "ruthless"
    return True


def can_ask_to_learn(''')

ROADS = "engine/roads.py"
edit(ROADS, '''        events = encounters.road_encounter_events(self.world, self.player.id, self.place)
        if events:
            lines += self._commit(events)
            self.encounter = encounters.encounter_state(events[0])
        return lines

    def _after_look(self) -> list:
        lines = super()._after_look()
        npc = encounters.challenge_from(self.world, self.player.id, self.place.id)
        if npc is not None:
            lines += self._commit(encounters.challenge_events(self.player.id, npc, self.place.id))
            self.challenger = npc
        return lines''', '''        events = encounters.road_encounter_events(self.world, self.player.id, self.place)
        if events:
            lines += self._commit(events)
            if events[-1].kind == "encounter":
                self.encounter = encounters.encounter_state(events[-1])
        if self.encounter is None:
            lines += self._grudges()
        return lines

    def _after_look(self) -> list:
        return super()._after_look() + self._grudges()

    def _grudges(self) -> list:
        """Someone here with a grudge, a dead kinsman or a rival's pride may call you out."""
        npc = encounters.challenge_from(self.world, self.player.id, self.place.id)
        if npc is None:
            return []
        lines = self._commit(encounters.challenge_events(self.player.id, npc, self.place.id))
        self.challenger = npc
        return lines''')
edit(ROADS, '''            if encounters.talk_succeeds(self.world, person, me):''',
     '''            if encounters.talk_succeeds(self.world, person, me, e["kind"]):''')

FIGHT = "engine/fight.py"
edit(FIGHT, '''from systems.combat_core import INTENTS, QI_OUTPUTS, condition_of
''', '''from systems.attitude import afraid
from systems.beliefs import apparent_to
from systems.combat_core import INTENTS, QI_OUTPUTS, condition_of
''')
edit(FIGHT, '''        if not duel.accepts(self.world, npc_id, self.player.id, mode):
            return self._turn(self._commit(duel.refusal_events(self.player.id, npc_id, self.place.id, mode)))''',
     '''        if not duel.accepts(self.world, npc_id, self.player.id, mode):
            scared = afraid(self.world, npc_id, apparent_to(self.world, npc_id, self.player.id))
            events = duel.refusal_events(self.player.id, npc_id, self.place.id, mode, "afraid" if scared else "unwilling")
            return self._turn(self._commit(events))''')

DEAL = "engine/dealings.py"
edit(DEAL, '''        if learning.can_ask_to_learn(self.world, npc.id, self.player.id):
            extras.append(Choice("Ask to learn an art...", Action("learn_menu")))''', '''        if not learning.will_deal(self.world, npc.id, self.player.id):
            return extras
        if learning.can_ask_to_learn(self.world, npc.id, self.player.id) \\
                and learning.will_teach(self.world, npc.id, self.player.id, self.place.id):
            extras.append(Choice("Ask to learn an art...", Action("learn_menu")))''')
edit(DEAL, '''        if self.focus is None or not learning.can_ask_to_learn(self.world, self.focus, self.player.id):''',
     '''        if self.focus is None or not learning.can_ask_to_learn(self.world, self.focus, self.player.id) \\
                or not learning.will_teach(self.world, self.focus, self.player.id, self.place.id):''')
edit(DEAL, '''        if self.focus is None or not learning.ensure_goods(self.world, self.focus):''',
     '''        if self.focus is None or not learning.will_deal(self.world, self.focus, self.player.id) \\
                or not learning.ensure_goods(self.world, self.focus):''')
edit(DEAL, '''        if self.focus is None:
            return self._turn([("Learn from whom?", "system")])''', '''        if self.focus is None or not learning.will_teach(self.world, self.focus, self.player.id, self.place.id):
            return self._turn([("Learn from whom?", "system")])''', count=2)
edit(DEAL, '''        if self.focus is None:
            return self._turn([("Buy from whom?", "system")])''', '''        if self.focus is None or not learning.will_deal(self.world, self.focus, self.player.id):
            return self._turn([("Buy from whom?", "system")])''')

RT = "narrate/road_text.py"
edit(RT, '''    "fled": "You slip away from {name}.", "fight": "There is no way around it: you fight.",
}''', '''    "fled": "You slip away from {name}.", "fight": "There is no way around it: you fight.",
    "backed_off": "{name} recognises you, thinks better of it and slips away.",
}''')
edit(RT, '''        "wanderer": f"{cap(name)}, a wandering swordsman, bars the road and looks you over.",
    }[d["kind"]]''', '''        "wanderer": f"{cap(name)}, a wandering swordsman, bars the road and looks you over.",
        "avenger": f'{cap(name)} steps into the road. "You killed my {d.get("role") or "kin"}."',
    }[d["kind"]]''')
edit(RT, '''    return [HOW[event.data["how"]].format(name=_name(world, event))], {}''',
     '''    return [cap(HOW[event.data["how"]].format(name=_name(world, event)))], {}''')
append("narrate/grammar/roads.toml", '''
["encounter.avenger"]
colour = "default"
lines = ["#roadside# #bravado#", "#bravado# #roadside#"]
''')

CT = "narrate/combat_text.py"
edit(CT, '''def _refused(world, event):
    what = "to spar" if event.data["mode"] == "spar" else "your challenge"''', '''def _refused(world, event):
    if event.data.get("reason") == "afraid":
        return [f"{cap(_name(world, event))} backs away; they want no part of you."], {}
    what = "to spar" if event.data["mode"] == "spar" else "your challenge"''')
print("task 6 edits applied")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3a_task6.py && .venv/Scripts/python.exe -m pytest tests/test_reactions.py -q -p no:cacheprovider`
Expected: `task 6 edits applied`, then `8 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass. `tests/test_review_2b.py` still holds: a declined challenge does not return at once, and contempt alone is no grudge.

- [ ] **Step 5: Commit**

Run: `git add -A && git commit -m "feat: fear, avengers on the road, rivals, bandits who back off, refusals"`

---

### Task 7: Gossip in the engine: news, asking about people, telling, lying, the Rumours page

**Files:**
- Create: `systems/telling.py`, `engine/gossip.py`, `narrate/gossip_text.py`, `narrate/grammar/gossip.toml`
- Modify (via `.patches/3a_task7.py`):
  - `engine/hooks.py`, `engine/game.py`, `engine/commands.py`
  - `narrate/outcomes.py`, `narrate/brief.py`, `narrate/procedural.py`
  - `tests/test_game.py` (conversation verbs ruling)
- Test: `tests/test_gossip.py`

**Interfaces:**
- Consumes: Tasks 2–5 (`knowledge_of`, `known_people`, `confidence_word`, `catch_up`, `pick_news`, `news_about`, `heard_events`, `no_news_events`, `attitude`, `ensure_kin`, `make_variant`, `record_fact`, `FAMILY`).
- Produces:
  - `systems.telling`:
    - Constants: `INVENTABLE`, `NEEDS_OBJECT`.
    - Functions: `acceptance(world, listener, speaker_as, variant) -> float`, `tell_events(world, player, listener, place, variant, fact_id=None, speaker_as=None) -> [Event("told")]`, `exposure_events(world, player, town_id) -> [Event("lie_exposed")]`.
    - Listeners on `told` (writes beliefs, and a false fact with `data.liar` and `data.spread` for inventions) and on `lie_exposed` (writes a `lied_about` fact).
  - `narrate.gossip_text`: `rumour_text(world, variant, viewer) -> str`, `who(world, entity_id, viewer) -> str`, plus outcomes and summaries for `heard`, `no_news`, `told` and `lie_exposed`.
  - `engine.gossip.GossipMixin`:
    - Verbs: `news`, `ask_about`, `tell_menu`, `tell`, `invent_menu`, `invent_pred`, `invent_subject`, `invent_object`, `rumours`.
    - Hooks: `_conversation_hidden`, `_general_extras`, `_after_arrival` (`catch_up` plus exposures), `_restore` (`catch_up`), `_exposures()`.
  - `engine.hooks.GameHooks`: `_conversation_hidden(npc) -> list` and `_general_extras() -> list`.
  - `engine.game.Game`:
    - `_patience(npc) -> int` and `_lost_patience(npc, topic) -> Turn | None`.
    - Conversation menus fold past 9 choices into `extra`.
    - Base classes are now `(GossipMixin, InventingMixin, DealingsMixin, RoadsMixin, FightMixin, GameHooks)`.
  - `engine.commands`: `PREFIX_VERBS["ask"] = ("ask", "ask_about", "news")`. GLOBAL gains `news`, `rumours`/`rumors`/`gossip` and `tell`.

- [ ] **Step 1: Write the failing test** — `tests/test_gossip.py`
```python
import pytest

import systems.telling as telling
from engine.commands import parse
from engine.game import Action, Game
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.gen.materialize import ensure_town, people_at


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("kind", "honest"), occupation="innkeeper", town=None):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": occupation, "traits": list(traits), "realm": "mortal", "surname": surname, "given": given,
        "gender": "man", "age": 40, "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, town or game.place.id, "located_in")
    return pid


def lines(turn):
    return [text for text, _ in turn.lines]


def test_asking_for_news_passes_on_a_story(game):
    teller, a, b = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    fid = record_fact(game.world, a, "robbed", b, place=game.place.id,
                      variant=make_variant("robbed", a, b, place=game.place.name))
    game.perform(Action("talk", teller))
    turn = game.perform(Action("news"))
    assert any(text.startswith("Old Wu tells you: Ma Bo robbed Hu Mei") for text in lines(turn))
    [belief] = [x for x in game.world.beliefs(game.player.id) if x.fact_id == fid]
    assert belief.source == teller and belief.hops == 3
    assert "They have heard nothing new." in lines(game.perform(Action("news")))


def test_news_wears_out_patience(game):
    teller = person(game, "Old Wu", traits=("hot-tempered", "lazy"))
    game.perform(Action("talk", teller))
    for _ in range(4):
        game.perform(Action("news"))
    assert game.focus is None


def test_asking_about_someone_by_name(game):
    teller, a, far = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    record_fact(game.world, a, "robbed", far, place=game.place.id, variant=make_variant("robbed", a, far))
    turn = game.perform(Action("talk", teller))
    action = parse("ask about hu mei", turn.choices, turn.extra)
    assert action == Action("ask_about", far)
    assert any("Ma Bo robbed Hu Mei" in text for text in lines(game.perform(action)))
    assert "They have never heard of you." in lines(game.perform(Action("ask_about", game.player.id)))


def test_the_conversation_menu_never_shows_more_than_nine(game):
    for npc in people_at(game.world, game.place.id, exclude=game.player.id):
        for _ in range(3):
            turn = game.perform(Action("talk", npc.id))
            assert len(turn.choices) <= 9 and turn.choices[-1].action == Action("farewell")
            assert {"news", "tell_menu"} <= {c.action.verb for c in turn.choices}
            game.perform(Action("farewell"))


def test_telling_a_true_story_spreads_it(game, monkeypatch):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 1.0)
    listener, a, b = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    fid = record_fact(game.world, a, "robbed", b, place=None, variant=make_variant("robbed", a, b))
    game.world.upsert_belief(game.player.id, fid, make_variant("robbed", a, b), None, 1.0, 0, "witness")
    game.perform(Action("talk", listener))
    turn = game.perform(Action("tell_menu"))
    tell = next(c for c in turn.choices if c.action.verb == "tell")
    assert tell.label.startswith("Tell them: Ma Bo robbed Hu Mei")
    assert "Old Wu takes it in and nods." in lines(game.perform(tell.action))
    assert [x.channel for x in game.world.beliefs(listener) if x.fact_id == fid] == ["told"]
    assert any(x.fact_id == fid for x in game.world.beliefs(game.place.id))


def test_a_story_they_reject_annoys_them(game, monkeypatch):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 0.0)
    listener, a, b = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    fid = record_fact(game.world, a, "robbed", b, place=None, variant=make_variant("robbed", a, b))
    game.world.upsert_belief(game.player.id, fid, make_variant("robbed", a, b), None, 1.0, 0, "witness")
    game.perform(Action("talk", listener))
    turn = game.perform(Action("tell", (fid, game.world.beliefs(game.player.id)[0].variant_key)))
    assert "Old Wu doesn't believe you." in lines(turn)
    assert any(m.feeling == "annoyed" for m in game.world.memories(listener))


def test_a_lie_told_where_its_victim_lives_is_found_out(game, monkeypatch):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 1.0)
    listener, victim, other = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    for someone in (victim, other):
        game.perform(Action("talk", someone))
        game.perform(Action("farewell"))
    game.perform(Action("talk", listener))
    game.perform(Action("invent_menu"))
    game.perform(Action("invent_pred", "robbed"))
    game.perform(Action("invent_subject", victim))
    turn = game.perform(Action("invent_object", other))
    [lie] = game.world.facts(is_true=False)
    assert (lie.subject, lie.predicate, lie.object) == (victim, "robbed", other)
    assert lie.data["liar"] == game.player.id and lie.source_event is not None
    assert not any(b.fact_id == lie.id for b in game.world.beliefs(game.player.id))
    assert any(b.fact_id == lie.id for b in game.world.beliefs(listener))
    assert "Ma Bo has learned that you lied about them." in lines(turn)
    assert game.world.facts(predicate="lied_about")[0].object == victim
    assert any(m.feeling == "wronged" for m in game.world.memories(victim))


def test_a_lie_about_someone_far_away_is_not_found_out_yet(game, monkeypatch):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 1.0)
    far_town = ensure_town(game.world, 3, 0, 0)
    victim = person(game, "Ma Bo", town=far_town)
    other = person(game, "Hu Mei")
    fid = record_fact(game.world, victim, "spared", other, place=None, variant=make_variant("spared", victim, other))
    game.world.upsert_belief(game.player.id, fid, make_variant("spared", victim, other), None, 1.0, 0, "witness")
    listener = person(game, "Old Wu")
    game.perform(Action("talk", listener))
    game.perform(Action("invent_menu"))
    game.perform(Action("invent_pred", "killed"))
    game.perform(Action("invent_subject", victim))
    turn = game.perform(Action("invent_object", other))
    assert game.world.facts(is_true=False)
    assert not any("lied about" in text for text in lines(turn))
    assert game.world.facts(predicate="lied_about") == []


def test_the_rumours_page_groups_stories_and_shows_doubt(game):
    a, b, teller = person(game, "Ma Bo"), person(game, "Hu Mei"), person(game, "Old Wu")
    fid = record_fact(game.world, a, "robbed", b, place=None, variant=make_variant("robbed", a, b))
    game.world.upsert_belief(game.player.id, fid, make_variant("robbed", a, b), teller, 0.85, 1, "told")
    game.world.upsert_belief(game.player.id, fid, dict(make_variant("robbed", a, b), count=3), game.place.id, 0.4, 5,
                             "distance")
    page = lines(game.perform(Action("rumours")))
    assert "About Ma Bo:" in page
    assert "  Ma Bo robbed Hu Mei. (from a witness, told by Old Wu) Settled." in page
    assert f"    or: Ma Bo robbed Hu Mei and two others. (doubtful, gossip in {game.place.name})" in page
    assert parse("rumours", [], []) == Action("rumours")
    assert "rumours" in {c.action.verb for c in game.perform(Action("look")).all_choices}
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_gossip.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.telling'`.

- [ ] **Step 3: Write telling and lying** — `systems/telling.py`
```python
"""Telling people things, true or invented, and lies found out (phase 3a spec 7.3)."""

from systems.attitude import attitude
from systems.beliefs import CONF_DECAY, believe, knowledge_of
from systems.facts import FAMILY, make_variant, place_name, record_fact
from world.db import variant_key
from world.events import Event, Witness, listen
from world.gen.materialize import people_at
from world.seed import rng_for

INVENTABLE = ("killed", "robbed", "fled_from", "owns_manual")
NEEDS_OBJECT = frozenset({"killed", "robbed", "fled_from"})


def acceptance(world, listener_id: int, speaker_as: int, variant: dict) -> float:
    """How likely the listener is to believe this. Zero if they know otherwise first-hand."""
    if listener_id in (variant.get("actor"), variant.get("target")):
        return 0.0  # they know what happened to them
    family = FAMILY.get(variant.get("predicate"))
    for belief, fact in knowledge_of(world, listener_id):
        if belief.hops == 0 and fact.subject == variant.get("actor") and fact.object == variant.get("target") \
                and FAMILY.get(fact.predicate) != family:
            return 0.0
    traits = set(world.entity(listener_id).data.get("traits", ()))
    score = max(-1.0, min(1.0, attitude(world, listener_id, speaker_as).score))
    chance = 0.5 + 0.2 * score + (0.2 if "honest" in traits else 0.0) - (0.3 if "cunning" in traits else 0.0)
    return max(0.0, min(1.0, chance))


def tell_events(world, player: int, listener: int, place: int, variant: dict, fact_id: int | None = None,
                speaker_as: int | None = None) -> list[Event]:
    key = fact_id if fact_id is not None else variant_key(variant)
    rng = rng_for(world.world_seed, f"tell:{key}:{listener}:{world.time}")
    accepted = rng.random() < acceptance(world, listener, speaker_as or player, variant)
    witness = Witness(listener, "engaged", 0.1) if accepted else Witness(listener, "annoyed", 0.3)
    data = {"fact": fact_id, "variant": variant, "invented": fact_id is None, "accepted": accepted}
    return [Event("told", (player, listener), place, data, witnesses=(witness,))]


@listen("told")
def _told(world, event, event_id: int) -> None:
    player, listener = event.actors
    d = event.data
    fact_id = d["fact"]
    if d["invented"]:
        story = d["variant"]
        fact_id = record_fact(world, story["actor"], story["predicate"], story.get("target"), place=event.place,
                              variant=story, source_event=event_id, is_true=False,
                              extra={"liar": player, "spread": d["accepted"]}, spread=False)
    if not d["accepted"]:
        return
    believe(world, listener, fact_id, d["variant"], player, CONF_DECAY, 1, "told")
    town = world.entity(event.place) if event.place else None
    if town is not None and town.kind == "town":
        believe(world, town.id, fact_id, d["variant"], player, CONF_DECAY ** 2, 2, "told")


def exposure_events(world, player: int, town_id: int) -> list[Event]:
    """The player's lies that have reached, here, someone who knows the truth first-hand."""
    done = {e.data.get("fact") for e in world.chronicle_about(player, limit=400) if e.kind == "lie_exposed"}
    here = {p.id for p in people_at(world, town_id, exclude=player)}
    pool = {b.fact_id for b in world.beliefs(town_id)}
    events = []
    for lie in world.facts(is_true=False):
        if lie.data.get("liar") != player or lie.id in done:
            continue
        victim = world.entity(lie.subject)
        if victim is None or victim.kind != "person" or victim.data.get("dead"):
            continue
        knowers = {lie.subject} & here
        for truth in world.facts(subject=lie.subject, is_true=True):
            if truth.object == lie.object and FAMILY.get(truth.predicate) != FAMILY.get(lie.predicate):
                knowers |= {b.knower for b in world.believers(truth.id) if b.hops == 0} & here
        if not knowers:
            continue
        heard = lie.id in pool or any(b.fact_id == lie.id for k in knowers for b in world.beliefs(k))
        if heard:
            events.append(Event("lie_exposed", (player, lie.subject), town_id,
                                {"fact": lie.id, "predicate": lie.predicate},
                                witnesses=(Witness(lie.subject, "wronged", 0.9),)))
    return events


@listen("lie_exposed")
def _exposed(world, event, event_id: int) -> None:
    player, victim = event.actors
    record_fact(world, player, "lied_about", victim, place=event.place, source_event=event_id,
                variant=make_variant("lied_about", player, victim, place=place_name(world, event.place)))
```

- [ ] **Step 4: Write the gossip mixin** — `engine/gossip.py`
```python
"""News, telling and the Rumours page in the engine (phase 3a spec 7)."""

import systems.rumours as rumours
import systems.talk as talk
import systems.telling as telling
from engine.actions import Action, Choice
from narrate.gossip_text import rumour_text, who
from systems.beliefs import confidence_word, knowledge_of, known_people
from systems.facts import make_variant
from systems.kin import ensure_kin
from world.events import Event, Witness
from world.gen.materialize import people_at

MAX_PASS_ON = 7
MAX_PEOPLE = 8
MAX_RUMOURS = 20
INVENT_LABELS = {
    "killed": "Say that someone killed someone", "robbed": "Say that someone robbed someone",
    "fled_from": "Say that someone fled from a fight", "owns_manual": "Say that someone owns a secret manual",
}
GOSSIP_MENUS = ("tell", "invent_pred", "invent_subject", "invent_object")


class GossipMixin:
    _invent: dict | None = None

    # --- state ------------------------------------------------------------------------------
    def _restore(self) -> None:
        super()._restore()
        rumours.catch_up(self.world, self.place.id)

    def _after_arrival(self) -> list:
        lines = super()._after_arrival()
        rumours.catch_up(self.world, self.place.id)
        if self.encounter is None:
            lines += self._exposures()
        return lines

    def _exposures(self) -> list:
        events = telling.exposure_events(self.world, self.player.id, self.place.id)
        return self._commit(events) if events else []

    # --- menus --------------------------------------------------------------------------------
    def _conversation_extras(self, npc) -> list:
        return [Choice("Ask for news", Action("news")), Choice("Tell them something...", Action("tell_menu"))] \
            + super()._conversation_extras(npc)

    def _conversation_hidden(self, npc) -> list:
        hidden = super()._conversation_hidden(npc)
        here = [p.id for p in people_at(self.world, self.place.id, exclude=self.player.id)]
        for someone in dict.fromkeys([self.player.id, *here, *known_people(self.world, self.player.id)]):
            if someone != npc.id:
                name = self.world.entity(someone).name
                hidden.append(Choice(f"Ask what they know of {name}", Action("ask_about", someone)))
        return hidden

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        if self.world.beliefs(self.player.id):
            extras.append(Choice("Rumours you have heard", Action("rumours")))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None and self.submenu in GOSSIP_MENUS:
            options[self.submenu] = self._gossip_menu(self.submenu)
        return options

    def _gossip_menu(self, name: str):
        if name == "tell":
            return self._tell_choices(), Action("talk_menu")
        if name == "invent_pred":
            return [Choice(label, Action("invent_pred", p)) for p, label in INVENT_LABELS.items()], Action("tell_menu")
        exclude = ((self._invent or {}).get("subject"),) if name == "invent_object" else ()
        return [Choice(self.world.entity(p).name, Action(name, p)) for p in self._candidates(exclude)], \
            Action("invent_menu")

    def _tell_choices(self) -> list[Choice]:
        theirs = {(b.fact_id, b.variant_key) for b, _ in knowledge_of(self.world, self.focus)}
        mine = [(b, f) for b, f in self.world.known_facts(self.player.id) if (b.fact_id, b.variant_key) not in theirs]
        mine.sort(key=lambda p: (-p[1].time, -p[1].id))
        choices = [Choice(f"Tell them: {rumour_text(self.world, b.variant, self.player.id)}",
                          Action("tell", (b.fact_id, b.variant_key))) for b, _ in mine[:MAX_PASS_ON]]
        return choices + [Choice("Invent a rumour...", Action("invent_menu"))]

    def _candidates(self, exclude=()) -> list[int]:
        """People the player could tell tales about: met or heard of, alive, not the listener."""
        out = []
        for someone in known_people(self.world, self.player.id):
            entity = self.world.entity(someone)
            if entity.kind == "person" and not entity.data.get("dead") and not entity.data.get("beast") \
                    and someone not in exclude and someone != self.focus:
                out.append(someone)
        return out[:MAX_PEOPLE]

    # --- hearing --------------------------------------------------------------------------------
    def _do_news(self, _target):
        if self.focus is None:
            return self._turn([("Ask whom?", "system")])
        npc, me, place = self.world.entity(self.focus), self.player.id, self.place.id
        if (lost := self._lost_patience(npc, "news")) is not None:
            return lost
        rumours.catch_up(self.world, place)
        found = rumours.pick_news(self.world, npc.id, me)
        events = talk.ask_events(me, npc.id, place, "news")
        events += rumours.heard_events(self.world, me, npc.id, place, *found) if found \
            else rumours.no_news_events(me, npc.id, place)
        return self._turn(self._commit(events) + self._exposures())

    def _do_ask_about(self, someone):
        if self.focus is None:
            return self._turn([("Ask whom?", "system")])
        subject = self.world.entity(someone) if isinstance(someone, int) else None
        if subject is None or subject.kind not in ("person", "persona") or someone == self.focus:
            return self._turn([("Ask about whom?", "system")])
        npc, me, place = self.world.entity(self.focus), self.player.id, self.place.id
        topic = f"about {subject.name}"
        if (lost := self._lost_patience(npc, topic)) is not None:
            return lost
        rumours.catch_up(self.world, place)
        ensure_kin(self.world, subject.id)
        found = rumours.news_about(self.world, npc.id, subject.id)
        # The one asked about is a third actor: asking makes them someone the player has heard of.
        events = [Event("asked", (me, npc.id, subject.id), place, {"topic": topic},
                        witnesses=(Witness(npc.id, "engaged", 0.1),))]
        events += rumours.heard_events(self.world, me, npc.id, place, *found) if found \
            else rumours.no_news_events(me, npc.id, place, subject.name)
        return self._turn(self._commit(events) + self._exposures())

    # --- telling ----------------------------------------------------------------------------------
    def _do_tell_menu(self, _target):
        if self.focus is None:
            return self._turn([("Tell whom?", "system")])
        self.submenu = "tell"
        return self._turn([("What will you tell them?", "system")])

    def _do_tell(self, key):
        if self.focus is None:
            return self._turn([("Tell whom?", "system")])
        belief = next((b for b in self.world.beliefs(self.player.id)
                       if isinstance(key, tuple) and (b.fact_id, b.variant_key) == tuple(key)), None)
        if belief is None:
            return self._turn([("You don't know that.", "system")])
        events = telling.tell_events(self.world, self.player.id, self.focus, self.place.id, belief.variant,
                                     belief.fact_id, self._speaker())
        self.submenu = None
        return self._turn(self._commit(events) + self._exposures())

    def _do_invent_menu(self, _target):
        if self.focus is None:
            return self._turn([("Tell whom?", "system")])
        self._invent = {}
        self.submenu = "invent_pred"
        return self._turn([("What will you claim?", "system")])

    def _do_invent_pred(self, predicate):
        if self.focus is None or predicate not in INVENT_LABELS:
            return self._turn([("Claim what?", "system")])
        self._invent = {"pred": predicate}
        self.submenu = "invent_subject"
        return self._turn([("About whom?", "system")])

    def _do_invent_subject(self, someone):
        if self.focus is None or not self._invent or someone not in self._candidates():
            return self._turn([("About whom?", "system")])
        self._invent["subject"] = someone
        if self._invent["pred"] in telling.NEEDS_OBJECT:
            self.submenu = "invent_object"
            return self._turn([("And who was on the other end of it?", "system")])
        return self._tell_lie()

    def _do_invent_object(self, someone):
        if self.focus is None or not self._invent or "subject" not in self._invent \
                or someone not in self._candidates((self._invent["subject"],)):
            return self._turn([("Who, then?", "system")])
        self._invent["object"] = someone
        return self._tell_lie()

    def _tell_lie(self):
        claim, self._invent, self.submenu = self._invent, None, None
        story = make_variant(claim["pred"], claim["subject"], claim.get("object"), place=self.place.name)
        events = telling.tell_events(self.world, self.player.id, self.focus, self.place.id, story, None,
                                     self._speaker())
        return self._turn(self._commit(events) + self._exposures())

    def _speaker(self) -> int:
        """Who the listener takes the teller to be (Task 8 makes this the persona while masked)."""
        return self.player.id

    # --- the Rumours page ----------------------------------------------------------------------
    def _do_rumours(self, _target):
        me = self.player.id
        by_fact: dict = {}
        for belief, fact in self.world.known_facts(me):
            by_fact.setdefault(fact.id, (fact, []))[1].append(belief)
        if not by_fact:
            return self._turn([("You have heard no rumours yet.", "system")])
        groups: dict = {}
        for fact, beliefs in sorted(by_fact.values(), key=lambda p: (-p[0].time, -p[0].id))[:MAX_RUMOURS]:
            beliefs.sort(key=lambda b: -b.confidence)
            groups.setdefault(beliefs[0].variant.get("actor"), []).append(beliefs)
        lines = [("Rumours you have heard:", "heading")]
        for actor, stories in groups.items():
            lines.append((f"About {who(self.world, actor, me)}:", "heading"))
            for beliefs in stories:
                settled = any(b.hops == 0 or b.confidence >= 0.75 for b in beliefs)
                for n, belief in enumerate(beliefs):
                    lead = "  " if n == 0 else "    or: "
                    mark = " Settled." if settled and n == 0 and len(beliefs) > 1 else ""
                    text = rumour_text(self.world, belief.variant, me)
                    lines.append((f"{lead}{text} ({self._provenance(belief)}){mark}", "dim"))
        return self._turn(lines)

    def _provenance(self, belief) -> str:
        word = confidence_word(belief)
        source = self.world.entity(belief.source) if belief.source is not None else None
        if belief.hops == 0 or source is None:
            return word
        if source.kind == "town":
            return f"{word}, gossip in {source.name}"
        return f"{word}, told by {source.name}"
```

- [ ] **Step 5: Write the gossip narration** — `narrate/gossip_text.py`
```python
"""What the player is told about rumours: built from a story variant, never from the fact behind it."""

from narrate.outcomes import cap, outcome, summary
from systems.beliefs import confidence_phrase
from systems.realms import REALMS, realm_index

VERBS = {
    "killed": "killed", "crippled": "crippled", "robbed": "robbed", "spared": "spared", "defeated": "defeated",
    "fled_from": "fled from", "left_for_dead": "left", "paid_off": "paid off", "lied_about": "spread lies about",
}
COUNT_WORDS = {2: "one other", 3: "two others"}
REALM_DEEDS = frozenset({"defeated", "killed", "crippled", "robbed", "spared", "left_for_dead"})


def who(world, entity_id, viewer: int) -> str:
    if entity_id is None:
        return "a masked fighter"
    if entity_id == viewer:
        return "you"
    entity = world.entity(entity_id)
    return entity.name if entity else "someone"


def rumour_text(world, variant: dict, viewer: int) -> str:
    """One plain sentence for a story, as this viewer would hear it."""
    actor = who(world, variant.get("actor"), viewer)
    predicate = variant.get("predicate")
    target = who(world, variant["target"], viewer) if variant.get("target") is not None else None
    if predicate == "is":
        return cap(f"{actor} is really {target}.")
    if predicate == "owns_manual":
        has = "have" if actor == "you" else "has"
        return cap(f"{actor} {has} the {variant['art']}.") if variant.get("art") else cap(f"{actor} {has} a secret manual.")
    verb = "nearly killed" if predicate == "killed" and variant.get("soft") else VERBS.get(predicate, predicate)
    whom = target or "someone"
    if variant.get("count", 1) > 1:
        whom += f" and {COUNT_WORDS.get(variant['count'], 'others')}"
    text = f"{actor} {verb} {whom}"
    if predicate == "left_for_dead":
        text += " for dead"
    realm = variant.get("realm")
    if realm and realm_index(realm) > 0 and predicate in REALM_DEEDS:
        text += f" (a {REALMS[realm_index(realm)].name} fighter)"
    if variant.get("art") and predicate != "owns_manual":
        text += f" with the {variant['art']}"
    if variant.get("place"):
        text += f" in {variant['place']}"
    return cap(text + ".")


@outcome("heard", body_facts=False)
def _heard(world, event):
    d = event.data
    teller = world.entity(event.actors[1]).name
    text = rumour_text(world, d["variant"], event.actors[0])
    return [f"{cap(teller)} tells you: {text} ({confidence_phrase(d['hops'], d['confidence'])})"], {}


@outcome("no_news", body_facts=False)
def _no_news(world, event):
    about = event.data.get("about")
    if about is None:
        return ["They have heard nothing new."], {}
    if about == world.entity(event.actors[0]).name:
        return ["They have never heard of you."], {}
    return [f"They have never heard of {about}."], {}


@outcome("told", body_facts=False)
def _told(world, event):
    name = cap(world.entity(event.actors[1]).name)
    return ([f"{name} takes it in and nods."] if event.data["accepted"] else [f"{name} doesn't believe you."]), {}


@outcome("lie_exposed", body_facts=False)
def _exposed(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} has learned that you lied about them."], {}


@summary("heard")
def _heard_line(world, entry, names, place, other):
    return f"Heard news from {other}."


@summary("no_news")
def _no_news_line(world, entry, names, place, other):
    return f"{cap(other)} had no news for you."


@summary("told")
def _told_line(world, entry, names, place, other):
    return f"Spread a lie to {other}." if entry.data.get("invented") else f"Told {other} a rumour."


@summary("lie_exposed")
def _exposed_line(world, entry, names, place, other):
    return f"{cap(other)} found out you lied about them."
```

- [ ] **Step 6: Write the gossip grammar** — `narrate/grammar/gossip.toml`
```toml
[symbols]
gossip_ask_open = ["You ask {npc} what news there is.", "You ask {npc} what people are saying.", "\"Any news?\" you ask {npc}.", "You ask {npc} whether anything has happened lately.", "You ask {npc} for the latest talk."]
gossip_ask_again = ["You press {npc} for more news.", "You ask {npc} again what people are saying.", "\"Anything else?\" you ask {npc}.", "You try {npc} once more for news."]
gossip_ask_who = ["You ask {npc} {topic}.", "You ask {npc} what they know {topic}.", "You ask {npc} what they have heard {topic}.", "You bring up a name with {npc}, asking {topic}."]
gossip_lean = ["They lean closer.", "They glance around first.", "They lower their voice.", "They take a moment to remember.", "They wipe their hands and think."]
gossip_murmur = ["\"Listen to this.\"", "\"You didn't hear it from me.\"", "\"People are saying things.\"", "\"Have you heard?\"", "\"It is all anyone talks about.\""]
gossip_shrug = ["They shrug.", "They shake their head.", "They spread their hands.", "They frown, then give up."]
gossip_nothing = ["Nothing comes to mind.", "It has been quiet.", "They have nothing for you.", "No one has said much of anything."]
gossip_confide = ["You lower your voice.", "You pick your words carefully.", "You lean in close.", "You glance around before speaking."]
gossip_listen = ["{npc} listens.", "{npc} raises an eyebrow.", "{npc} says nothing for a moment.", "{npc} rubs their chin."]
gossip_cold = ["{npc}'s face hardens.", "{npc} will not meet your eyes.", "{npc} goes very still.", "{npc}'s jaw tightens."]
gossip_cold_after = ["The words you spread have come home.", "Someone has told them everything.", "There is no taking it back.", "They know what you said."]

["asked.news"]
colour = "npc"
lines = ["#gossip_ask_open#", "#gossip_ask_open# #gossip_lean#"]

["asked.news.again"]
colour = "npc"
lines = ["#gossip_ask_again#", "#gossip_ask_again# #gossip_lean#"]

["asked.about"]
colour = "npc"
lines = ["#gossip_ask_who#", "#gossip_ask_who# #gossip_lean#"]

["asked.about.again"]
colour = "npc"
lines = ["#gossip_ask_who# #gossip_lean#", "#gossip_ask_again#"]

[heard]
colour = "npc"
lines = ["#gossip_lean# #gossip_murmur#", "#gossip_murmur# #gossip_lean#"]

[no_news]
colour = "npc"
lines = ["#gossip_shrug# #gossip_nothing#", "#gossip_nothing# #gossip_shrug#"]

[told]
colour = "npc"
lines = ["#gossip_confide# #gossip_listen#", "#gossip_listen# #gossip_confide#"]

[lie_exposed]
colour = "npc"
lines = ["#gossip_cold# #gossip_cold_after#", "#gossip_cold_after# #gossip_cold#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/3a_task7.py`
```python
"""Task 7 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("engine/hooks.py", '''    def _conversation_extras(self, npc) -> list:
        return []
''', '''    def _conversation_extras(self, npc) -> list:
        return []

    def _conversation_hidden(self, npc) -> list:
        """Choices valid in conversation but reached only by typing (ask about <name>)."""
        return []

    def _general_extras(self) -> list:
        """Extra entries for the main menu's general group (rumours, masks)."""
        return []
''')

GAME = "engine/game.py"
edit(GAME, '''from engine.fight import FightMixin
''', '''from engine.fight import FightMixin
from engine.gossip import GossipMixin
''')
edit(GAME, '''class Game(InventingMixin, DealingsMixin, RoadsMixin, FightMixin, GameHooks):''',
     '''class Game(GossipMixin, InventingMixin, DealingsMixin, RoadsMixin, FightMixin, GameHooks):''')
edit(GAME, '''    ("  challenge | spar | strike | feint | guard | probe | flee | yield | spare | rob | cripple | kill", "system"),''',
     '''    ("  challenge | spar | strike | feint | guard | probe | flee | yield | spare | rob | cripple | kill", "system"),
    ("  news | ask about <name> | tell | rumours", "system"),''')
edit(GAME, '''        npc, me = self.world.entity(self.focus), self.player.id
        if talk.repeats_if_asked(self.world, npc.id, me, topic) > talk.patience_of(npc):
            lines = self._commit(talk.lost_patience_events(me, npc.id, self.place.id, topic))
            self.focus = None
            return self._turn(lines)
        return self._turn(self._commit(talk.ask_events(me, npc.id, self.place.id, topic)))''', '''        npc, me = self.world.entity(self.focus), self.player.id
        if (lost := self._lost_patience(npc, topic)) is not None:
            return lost
        return self._turn(self._commit(talk.ask_events(me, npc.id, self.place.id, topic)))

    def _patience(self, npc) -> int:
        return talk.patience_of(npc)

    def _lost_patience(self, npc, topic: str):
        """A Turn if this question is one too many for them, else None."""
        me = self.player.id
        if talk.repeats_if_asked(self.world, npc.id, me, topic) <= self._patience(npc):
            return None
        lines = self._commit(talk.lost_patience_events(me, npc.id, self.place.id, topic))
        self.focus = None
        return self._turn(lines)''')
edit(GAME, '''            npc = self.world.entity(self.focus)
            return [
                Choice("Ask about their work", Action("ask", "work")),
                Choice(f"Ask about {self.place.name}", Action("ask", "town")),
                *self._conversation_extras(npc),
                Choice("Say farewell", Action("farewell")),
            ], []''', '''            npc = self.world.entity(self.focus)
            options = [
                Choice("Ask about their work", Action("ask", "work")),
                Choice(f"Ask about {self.place.name}", Action("ask", "town")),
                *self._conversation_extras(npc),
            ]
            shown = options[: MAX_SHOWN - 1] + [Choice("Say farewell", Action("farewell"))]
            return shown, options[MAX_SHOWN - 1:] + self._conversation_hidden(npc)''')
edit(GAME, '''        general = [Choice("Look around", Action("look")), Choice("Read your journal", Action("journal"))]''',
     '''        general = [Choice("Look around", Action("look")), Choice("Read your journal", Action("journal"))]
        general += self._general_extras()''')

CMD = "engine/commands.py"
edit(CMD, '''    "spar": Action("spar"), "challenge": Action("challenge"),
}''', '''    "spar": Action("spar"), "challenge": Action("challenge"),
    "news": Action("news"), "rumours": Action("rumours"), "rumors": Action("rumours"), "gossip": Action("rumours"),
    "tell": Action("tell_menu"),
}''')
edit(CMD, '''"go": "travel", "travel": "travel", "walk": "travel", "ask": "ask",''',
     '''"go": "travel", "travel": "travel", "walk": "travel", "ask": ("ask", "ask_about", "news"),''')
edit(CMD, '''    verb = PREFIX_VERBS.get(head)
    wanted = [w for w in _words(rest) if w not in FILLER]
    if verb is None or not wanted:
        return Action("unknown", cleaned)
    pool = [c for c in [*choices, *extra] if c.action.verb == verb]''', '''    verbs = PREFIX_VERBS.get(head)
    verbs = (verbs,) if isinstance(verbs, str) else verbs
    wanted = [w for w in _words(rest) if w not in FILLER]
    if verbs is None or not wanted:
        return Action("unknown", cleaned)
    pool = [c for c in [*choices, *extra] if c.action.verb in verbs]''')

edit("narrate/outcomes.py", '''import narrate.invent_text  # noqa: E402,F401
''', '''import narrate.invent_text  # noqa: E402,F401
import narrate.gossip_text  # noqa: E402,F401
''')
edit("engine/journal.py", '''            text = f"Asked {other} about {data.get('topic', 'things')}."''',
     '''            topic = str(data.get("topic", "things"))
            text = f"Asked {other} {topic}." if topic.startswith("about ") else f"Asked {other} about {topic}."''')
edit("narrate/brief.py", '''                about = "their work" if details["topic"] == "work" else world.entity(event.place).name''',
     '''                topic = details["topic"]
                about = {"work": "their work", "news": "the news"}.get(topic) \\
                    or (topic[len("about "):] if topic.startswith("about ") else world.entity(event.place).name)''')
edit("narrate/procedural.py", '''        if brief.kind == "asked":
            key = f"asked.{brief.details.get('topic', '')}"''', '''        if brief.kind == "asked":
            topic = brief.details.get("topic", "")
            key = f"asked.{'about' if topic.startswith('about ') else topic}"''')

# Ruling: conversations now also offer news and telling (phase 3a spec 7).
edit("tests/test_game.py", '''{"ask", "farewell", "challenge", "spar", "learn_menu", "browse"}''',
     '''{"ask", "farewell", "challenge", "spar", "learn_menu", "browse", "news", "tell_menu"}''')
print("task 7 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3a_task7.py && .venv/Scripts/python.exe -m pytest tests/test_gossip.py -q -p no:cacheprovider`
Expected: `task 7 edits applied`, then `9 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass, including the fuzz tests: random presses now reach news, telling and inventing.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: ask for news, ask about people, tell and lie, rumours page"`

---
### Task 8: Masks and recognition

**Files:**
- Create: `systems/masks.py`, `engine/masks.py`, `narrate/mask_text.py`, `narrate/grammar/masks.toml`
- Modify (via `.patches/3a_task8.py`):
  - `engine/hooks.py`, `engine/game.py`, `engine/gossip.py`, `engine/dealings.py`, `engine/commands.py`
  - `systems/talk.py`
  - `narrate/outcomes.py`
- Test: `tests/test_masks.py`

**Interfaces:**
- Consumes: Task 2 (`knows_identity`, `apparent_to`, `record_fact`, `make_variant`, `place_name`), Task 6 (`learning.will_deal`) and `systems.duel.best_art`.
- Produces:
  - `systems.masks`:
    - Constants: `MASK_PRICE = 5`, `ART_CHANCE = 0.5`, `VOICE_CHANCE = 0.3`, `CHANGE_CHANCE = 0.5`, `UNSTAMPED`.
    - Masks: `masks_of(world, person) -> list[Entity]`, `worn_persona(world, player) -> int | None`, `persona_for(world, player, mask_id) -> int`.
    - Events: `buy_mask_events`, `wear_events(world, player, place, mask_id)`, `remove_events(world, player, place)`.
    - Recognition: `onlookers(world, player, place, persona, putting_on) -> list[int]`, `recognition_events(world, player, ids, events) -> list[Event]`.
    - Effects `mask_bought`, `mask_on` and `mask_off`, and a listener `recognised` that writes the `is` fact.
  - `engine.hooks.GameHooks`: `_stamp(events) -> list`, `_after_commit(ids, events) -> list[Line]` and `_status_suffix() -> str`.
  - `engine.game.Game._commit` stamps events, commits them, narrates them, then adds `_after_commit` lines. It keeps `self._last_ids` as the ids of the caller's own events.
  - Persona entities have `kind="persona"`, a name of the form `the <Colour>-Masked <Style>` and `data={"of": player, "mask": id}`. While a mask is worn, the player data holds `masked=persona_id`.

- [ ] **Step 1: Write the failing test** — `tests/test_masks.py`
```python
import pytest

import systems.masks as masks
from engine.commands import parse
from engine.game import Action, Game
from systems.attitude import attitude
from systems.beliefs import knows_identity
from systems.creation import CreationChoice
from systems.purse import silver_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture
def unseen(monkeypatch):
    for name in ("ART_CHANCE", "VOICE_CHANCE", "CHANGE_CHANCE"):
        monkeypatch.setattr(masks, name, 0.0)


def person(game, name, traits=("kind", "honest"), occupation="innkeeper"):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": occupation, "traits": list(traits), "realm": "mortal", "surname": surname, "given": given,
        "gender": "man", "age": 40, "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def give_mask(game):
    with game.world.transaction():
        mask = game.world.add_entity("mask", "plain mask", {"persona": None})
        game.world.relate(game.player.id, mask, "owns")
    return mask


def win(game, npc, verdict):
    game.perform(Action("challenge", npc))
    game.combat.stage, game.combat.harm = "verdict", {"player": 0.0, "opponent": 90.0}
    return game.perform(Action("verdict", verdict))


def test_buying_a_mask_from_a_merchant(game):
    merchant = person(game, "Qian Duo", occupation="merchant")
    game.world.update_data(game.player.id, silver=20)
    turn = game.perform(Action("talk", merchant))
    assert "browse" in {c.action.verb for c in turn.all_choices}
    turn = game.perform(Action("browse"))
    buy = next(c for c in turn.choices if c.action.verb == "buy_mask")
    game.perform(buy.action)
    assert silver_of(game.world, game.player.id) == 15
    assert len(masks.masks_of(game.world, game.player.id)) == 1


def test_wearing_a_mask_makes_a_persona_that_sticks(game, unseen):
    give_mask(game)
    assert "wear_mask" in {c.action.verb for c in game.perform(Action("look")).all_choices}
    turn = game.perform(Action("wear_mask"))
    persona = game.world.entity(game.player.id).data["masked"]
    name = game.world.entity(persona).name
    assert name.startswith("the ") and "-Masked " in name
    assert "(masked)" in turn.status
    assert f"You are now {name}." in [text for text, _ in turn.lines]
    game.perform(Action("remove_mask"))
    assert "(masked)" not in game.perform(Action("look")).status
    game.perform(Action("wear_mask"))
    assert game.world.entity(game.player.id).data["masked"] == persona
    assert parse("wear mask", [], []) == Action("wear_mask")
    assert parse("remove mask", [], []) == Action("remove_mask")


def test_a_masked_player_is_greeted_as_a_stranger(game, unseen):
    friend = person(game, "Old Wu")
    for _ in range(3):
        game.perform(Action("talk", friend))
        game.perform(Action("farewell"))
    give_mask(game)
    game.perform(Action("wear_mask"))
    game.perform(Action("talk", friend))
    last = game.world.chronicle_about(game.player.id, limit=1)[0]
    assert last.kind == "met"
    assert last.data["as"] == game.world.entity(game.player.id).data["masked"]


def test_a_masked_robbery_is_credited_to_the_persona(game, unseen):
    victim = person(game, "Ma Bo", traits=("proud", "honest"))
    give_mask(game)
    game.perform(Action("wear_mask"))
    persona = game.world.entity(game.player.id).data["masked"]
    win(game, victim, "rob")
    assert game.world.facts(predicate="robbed")[0].subject == persona
    assert attitude(game.world, victim, game.player.id).word == "neutral"
    assert attitude(game.world, victim, persona).word == "wary"


def test_a_fighting_style_gives_the_wearer_away(game, monkeypatch):
    monkeypatch.setattr(masks, "ART_CHANCE", 1.0)
    monkeypatch.setattr(masks, "VOICE_CHANCE", 0.0)
    monkeypatch.setattr(masks, "CHANGE_CHANCE", 0.0)
    rival = person(game, "Iron Gu", traits=("proud", "honest"))
    win(game, rival, "spare")
    give_mask(game)
    game.perform(Action("wear_mask"))
    persona = game.world.entity(game.player.id).data["masked"]
    turn = win(game, rival, "spare")
    assert knows_identity(game.world, rival, persona)
    assert game.world.facts(predicate="is")[0].subject == persona
    assert any("Iron Gu looks hard at you" in text for text, _ in turn.lines)


def test_changing_in_public_can_be_seen(game, monkeypatch):
    monkeypatch.setattr(masks, "CHANGE_CHANCE", 1.0)
    friend = person(game, "Old Wu")
    game.perform(Action("talk", friend))
    game.perform(Action("farewell"))
    give_mask(game)
    label = next(c.label for c in game.perform(Action("look")).all_choices if c.action.verb == "wear_mask")
    assert label == "Wear your mask (1 here know your face)"
    game.perform(Action("wear_mask"))
    assert knows_identity(game.world, friend, game.world.entity(game.player.id).data["masked"])
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_masks.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.masks'`.

- [ ] **Step 3: Write masks** — `systems/masks.py`
```python
"""Masks and the identities behind them (phase 3a spec 8).

While the player wears a mask the engine stamps data["as"] = persona on their
events. Witnesses remember the persona, facts name it, and only those who
recognise the wearer (an `is` fact they believe) connect it to the player.
"""

from systems.beliefs import knows_identity
from systems.duel import best_art
from systems.facts import make_variant, place_name, record_fact
from systems.purse import payment_events
from world.events import Event, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

MASK_PRICE = 5
ART_CHANCE = 0.5      # someone who knows your art sees it through the mask
VOICE_CHANCE = 0.3    # someone who has talked with you often knows your voice
CHANGE_CHANCE = 0.5   # someone who knows the face sees the mask go on or come off
COLOURS = ("Grey", "White", "Black", "Crimson", "Jade", "Bronze", "Silver")
STYLES = {"sword": "Swordsman", "fist": "Fist", "palm": "Palm", "saber": "Blade", "spear": "Spear"}
VOICE_KINDS = frozenset({"met", "conversed", "asked", "heard", "told", "no_news"})
TALK_KINDS = frozenset({"met", "conversed", "asked"})
UNSTAMPED = frozenset({"mask_on", "mask_off", "recognised"})


def masks_of(world, person_id: int) -> list:
    owned = (world.entity(item) for item in world.targets(person_id, "owns"))
    return [item for item in owned if item is not None and item.kind == "mask"]


def worn_persona(world, player_id: int) -> int | None:
    return world.entity(player_id).data.get("masked")


def buy_mask_events(player: int, seller: int, place: int) -> list[Event]:
    return payment_events(player, seller, place, MASK_PRICE, "mask") + [Event("mask_bought", (player, seller), place, {})]


@effect("mask_bought")
def _bought(world, event) -> None:
    mask = world.add_entity("mask", "plain mask", {"persona": None})
    world.relate(event.actors[0], mask, "owns")


def persona_for(world, player_id: int, mask_id: int) -> int:
    """The identity this mask gives its wearer: made on first wearing, the same ever after."""
    mask = world.entity(mask_id)
    if mask.data.get("persona"):
        return mask.data["persona"]
    rng = rng_for(world.world_seed, f"persona:{mask_id}")
    art = best_art(world, player_id)
    style = STYLES.get(art.form if art else None, "Stranger")
    with world.transaction():
        persona = world.add_entity("persona", f"the {rng.choice(COLOURS)}-Masked {style}",
                                   {"of": player_id, "mask": mask_id})
        world.update_data(mask_id, persona=persona)
    return persona


def wear_events(world, player: int, place: int, mask_id: int) -> list[Event]:
    return [Event("mask_on", (player,), place, {"mask": mask_id, "persona": persona_for(world, player, mask_id)})]


def remove_events(world, player: int, place: int) -> list[Event]:
    return [Event("mask_off", (player,), place, {"persona": worn_persona(world, player)})]


@effect("mask_on")
def _on(world, event) -> None:
    world.update_data(event.actors[0], masked=event.data["persona"])


@effect("mask_off")
def _off(world, event) -> None:
    world.update_data(event.actors[0], masked=None)


def onlookers(world, player: int, place: int, persona: int | None, putting_on: bool) -> list[int]:
    """People here who know the identity being hidden (or, taking it off, the mask being dropped)."""
    out = []
    for someone in people_at(world, place, exclude=player):
        memories = world.memories(someone.id, about=player)
        if putting_on:
            knows = any(not m.event.data.get("as") for m in memories)
        else:
            knows = any(m.event.data.get("as") == persona for m in memories)
        if knows and not knows_identity(world, someone.id, persona):
            out.append(someone.id)
    return out


def _technique(world, duel_id):
    entry = world.chronicle_entry(duel_id)
    return entry.data.get("technique") if entry is not None and entry.kind == "duel_started" else None


def _clue(world, player: int, witness: int, event) -> str | None:
    unmasked = [m for m in world.memories(witness, about=player) if not m.event.data.get("as")]
    if event.kind == "duel_ended":
        art = _technique(world, event.data.get("duel"))
        if art is not None and any(m.event.kind == "duel_ended" and _technique(world, m.event.data.get("duel")) == art
                                   for m in unmasked):
            return "art"
    if event.kind in VOICE_KINDS and sum(1 for m in unmasked if m.event.kind in TALK_KINDS) >= 3:
        return "voice"
    return None


def _recognised(player: int, witness: int, place, persona: int, how: str) -> Event:
    return Event("recognised", (player, witness), place, {"persona": persona, "how": how})


def recognition_events(world, player: int, ids: list[int], events: list) -> list[Event]:
    """Anyone who, at these just-committed moments, sees through the player's mask."""
    found = []
    for event_id, event in zip(ids, events):
        if event.kind in ("mask_on", "mask_off"):
            persona = event.data["persona"]
            for witness in onlookers(world, player, event.place, persona, event.kind == "mask_on"):
                if rng_for(world.world_seed, f"recognise:{event_id}:{witness}").random() < CHANGE_CHANCE:
                    found.append(_recognised(player, witness, event.place, persona, "changing"))
            continue
        persona = event.data.get("as")
        if not persona or not event.actors or event.actors[0] != player:
            continue
        for witness in sorted(set(world.witnesses_of(event_id)) | set(event.actors[1:2])):  # [2] is only talked about
            entity = world.entity(witness)
            if entity is None or entity.kind != "person" or entity.data.get("dead") or entity.data.get("beast") \
                    or knows_identity(world, witness, persona):
                continue
            chance = {"art": ART_CHANCE, "voice": VOICE_CHANCE}.get(_clue(world, player, witness, event), 0.0)
            if chance and rng_for(world.world_seed, f"recognise:{event_id}:{witness}").random() < chance:
                found.append(_recognised(player, witness, event.place, persona, _clue(world, player, witness, event)))
    return found


@listen("recognised")
def _identity_fact(world, event, event_id: int) -> None:
    player, _witness = event.actors
    persona = event.data["persona"]
    record_fact(world, persona, "is", player, place=event.place, source_event=event_id,
                variant=make_variant("is", persona, player, place=place_name(world, event.place)))
```

- [ ] **Step 4: Write the masks mixin** — `engine/masks.py`
```python
"""Masks in the engine (phase 3a spec 8): buying, wearing, removing, and being recognised."""

from dataclasses import replace

import systems.learning as learning
import systems.masks as masks
from engine.actions import Action, Choice
from systems.purse import silver_of


class MasksMixin:
    def _stamp(self, events: list) -> list:
        events = super()._stamp(events)
        persona = masks.worn_persona(self.world, self.player.id)
        if not persona:
            return events
        me = self.player.id
        return [replace(e, data={**e.data, "as": persona})
                if e.actors and e.actors[0] == me and e.kind not in masks.UNSTAMPED and "as" not in e.data else e
                for e in events]

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        found = masks.recognition_events(self.world, self.player.id, ids, events)
        return lines + (self._commit(found) if found else [])

    def _status_suffix(self) -> str:
        return super()._status_suffix() + (" (masked)" if masks.worn_persona(self.world, self.player.id) else "")

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        me, place = self.player.id, self.place.id
        persona = masks.worn_persona(self.world, me)
        if persona:
            n = len(masks.onlookers(self.world, me, place, persona, False))
            extras.append(Choice("Remove your mask" + (f" ({n} here would know you)" if n else ""), Action("remove_mask")))
        elif owned := masks.masks_of(self.world, me):
            n = len(masks.onlookers(self.world, me, place, owned[0].data.get("persona"), True))
            extras.append(Choice("Wear your mask" + (f" ({n} here know your face)" if n else ""), Action("wear_mask")))
        return extras

    def _goods_choices(self) -> list:
        choices = super()._goods_choices()
        if self.world.entity(self.focus).data.get("occupation") == "merchant":
            choices.append(Choice(f"Buy a mask ({masks.MASK_PRICE} silver)", Action("buy_mask")))
        return choices

    def _do_buy_mask(self, _target):
        if self.focus is None or self.world.entity(self.focus).data.get("occupation") != "merchant" \
                or not learning.will_deal(self.world, self.focus, self.player.id):
            return self._turn([("No one here sells masks.", "system")])
        if silver_of(self.world, self.player.id) < masks.MASK_PRICE:
            return self._turn([("You cannot afford it.", "system")])
        return self._turn(self._commit(masks.buy_mask_events(self.player.id, self.focus, self.place.id)))

    def _do_wear_mask(self, _target):
        if busy := self._busy():
            return busy
        me = self.player.id
        if masks.worn_persona(self.world, me):
            return self._turn([("You are already masked.", "system")])
        owned = masks.masks_of(self.world, me)
        if not owned:
            return self._turn([("You have no mask.", "system")])
        return self._turn(self._commit(masks.wear_events(self.world, me, self.place.id, owned[0].id)))

    def _do_remove_mask(self, _target):
        if busy := self._busy():
            return busy
        if not masks.worn_persona(self.world, self.player.id):
            return self._turn([("You are not wearing a mask.", "system")])
        return self._turn(self._commit(masks.remove_events(self.world, self.player.id, self.place.id)))
```

- [ ] **Step 5: Write the mask narration** — `narrate/mask_text.py`
```python
"""What the player is told about masks and being seen through them."""

from narrate.outcomes import cap, outcome, summary

HOW = {"art": "They know that way of fighting.", "voice": "They know your voice.", "changing": "They saw your face."}


@outcome("mask_bought", body_facts=False)
def _bought(world, event):
    return ["You buy a plain mask."], {}


@outcome("mask_on", body_facts=False)
def _on(world, event):
    return [f"You are now {world.entity(event.data['persona']).name}."], {}


@outcome("mask_off", body_facts=False)
def _off(world, event):
    return ["You take off your mask."], {}


@outcome("recognised", body_facts=False)
def _recognised(world, event):
    name = cap(world.entity(event.actors[1]).name)
    return [f"{name} looks hard at you. {HOW[event.data['how']]}", "They know who is behind the mask."], {}


@summary("mask_bought")
def _bought_line(world, entry, names, place, other):
    return "Bought a mask."


@summary("mask_on")
def _on_line(world, entry, names, place, other):
    return f"Put on a mask as {world.entity(entry.data['persona']).name}."


@summary("mask_off")
def _off_line(world, entry, names, place, other):
    return "Took off the mask."


@summary("recognised")
def _recognised_line(world, entry, names, place, other):
    return f"{cap(other)} recognised you behind the mask."
```

- [ ] **Step 6: Write the mask grammar** — `narrate/grammar/masks.toml`
```toml
[symbols]
mask_tie = ["You tie the mask on.", "You settle the mask over your face.", "You pull the mask into place.", "You knot the mask behind your head.", "The mask goes on."]
mask_feel = ["The world narrows to two eyeholes.", "Your breath is warm behind the cloth.", "No one here knows this face.", "You feel like someone else.", "The cloth smells of dust."]
mask_untie = ["You untie the mask.", "You pull the mask away.", "You take the mask off.", "You fold the mask away.", "The mask comes off."]
mask_air = ["The air is cool on your face.", "You are yourself again.", "You blink in the light.", "Your face feels bare.", "You breathe freely."]
mask_stare = ["{npc} stops.", "{npc} stares.", "{npc}'s eyes narrow.", "{npc} goes quiet.", "{npc} tilts their head."]
mask_knowing = ["Something in them has clicked.", "They have seen this before.", "Recognition crosses their face.", "They are sure of something now.", "Their look changes."]
mask_buy = ["The merchant wraps a plain mask for you.", "A plain mask changes hands.", "You pick the plainest mask on the table.", "You pay for a mask of grey cloth.", "The mask is cheap and plain."]

[mask_on]
colour = "default"
lines = ["#mask_tie# #mask_feel#", "#mask_feel# #mask_tie#"]

[mask_off]
colour = "default"
lines = ["#mask_untie# #mask_air#", "#mask_air# #mask_untie#"]

[mask_bought]
colour = "default"
lines = ["#mask_buy#", "#mask_buy# #mask_feel#"]

[recognised]
colour = "npc"
lines = ["#mask_stare# #mask_knowing#", "#mask_knowing# #mask_stare#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/3a_task8.py`
```python
"""Task 8 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("engine/hooks.py", '''    def _general_extras(self) -> list:
        """Extra entries for the main menu's general group (rumours, masks)."""
        return []
''', '''    def _general_extras(self) -> list:
        """Extra entries for the main menu's general group (rumours, masks)."""
        return []

    def _stamp(self, events: list) -> list:
        """Adjust events before they are committed (a mask stamps who the player seems to be)."""
        return events

    def _after_commit(self, ids: list, events: list) -> list:
        """Lines from reactions to what was just committed (someone seeing through a mask)."""
        return []

    def _status_suffix(self) -> str:
        return ""
''')

GAME = "engine/game.py"
edit(GAME, '''from engine.gossip import GossipMixin
''', '''from engine.gossip import GossipMixin
from engine.masks import MasksMixin
''')
edit(GAME, '''class Game(GossipMixin, InventingMixin,''', '''class Game(GossipMixin, MasksMixin, InventingMixin,''')
edit(GAME, '''    ("  news | ask about <name> | tell | rumours", "system"),''',
     '''    ("  news | ask about <name> | tell | rumours | wear mask | remove mask", "system"),''')
edit(GAME, '''    def _commit(self, events: list[Event]) -> list[Line]:
        ids = commit(self.world, events)
        self._last_ids = ids
        lines: list[Line] = []
        for event_id, event in zip(ids, events):
            brief = event_brief(self.world, event_id, event)
            self.last_briefs.append(brief)
            lines += self.narrator.narrate(brief)
        return lines''', '''    def _commit(self, events: list[Event]) -> list[Line]:
        events = self._stamp(list(events))
        ids = commit(self.world, events)
        self._last_ids = ids
        lines: list[Line] = []
        for event_id, event in zip(ids, events):
            brief = event_brief(self.world, event_id, event)
            self.last_briefs.append(brief)
            lines += self.narrator.narrate(brief)
        lines += self._after_commit(ids, events)
        self._last_ids = ids  # reactions commit too; callers want their own events' ids
        return lines''')
edit(GAME, '''        return f"{player.name} | {realm_title(self.body())} |''',
     '''        return f"{player.name}{self._status_suffix()} | {realm_title(self.body())} |''')

edit("engine/gossip.py", '''    def _speaker(self) -> int:
        """Who the listener takes the teller to be (Task 8 makes this the persona while masked)."""
        return self.player.id''', '''    def _speaker(self) -> int:
        """Who the listener takes the teller to be: the persona while masked and unrecognised."""
        return apparent_to(self.world, self.focus, self.player.id)''')
edit("engine/gossip.py", '''from systems.beliefs import confidence_word, knowledge_of, known_people''',
     '''from systems.beliefs import apparent_to, confidence_word, knowledge_of, known_people''')

DEAL = "engine/dealings.py"
edit(DEAL, '''        if learning.ensure_goods(self.world, npc.id):
            extras.append(Choice("Browse their manuals...", Action("browse")))''', '''        if learning.ensure_goods(self.world, npc.id) or npc.data.get("occupation") == "merchant":
            extras.append(Choice("Browse their goods...", Action("browse")))''')
edit(DEAL, '''                or not learning.ensure_goods(self.world, self.focus):''',
     '''                or not (learning.ensure_goods(self.world, self.focus)
                        or self.world.entity(self.focus).data.get("occupation") == "merchant"):''')

edit("engine/commands.py", '''    "tell": Action("tell_menu"),
}''', '''    "tell": Action("tell_menu"),
    "wear mask": Action("wear_mask"), "mask": Action("wear_mask"), "put on mask": Action("wear_mask"),
    "remove mask": Action("remove_mask"), "unmask": Action("remove_mask"), "take off mask": Action("remove_mask"),
}''')

TALK = "systems/talk.py"
edit(TALK, '''from world.db import Memory, World
''', '''from systems.beliefs import knows_identity
from world.db import Memory, World
''')
edit(TALK, '''def greet_events(world: World, player: int, npc_id: int, place: int) -> list[Event]:
    past = conversations_with(world, npc_id, player)''', '''def greet_events(world: World, player: int, npc_id: int, place: int) -> list[Event]:
    past = conversations_with(world, npc_id, player)
    persona = world.entity(player).data.get("masked")
    if persona and not knows_identity(world, npc_id, persona):
        past = [m for m in past if m.event.data.get("as") == persona]  # to them, a masked stranger''')

edit("narrate/outcomes.py", '''import narrate.gossip_text  # noqa: E402,F401
''', '''import narrate.gossip_text  # noqa: E402,F401
import narrate.mask_text  # noqa: E402,F401
''')
print("task 8 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3a_task8.py && .venv/Scripts/python.exe -m pytest tests/test_masks.py -q -p no:cacheprovider`
Expected: `task 8 edits applied`, then `6 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: masks, personas, and being recognised by art, voice or face"`

---

### Task 9: Showing attitude and reputation to the player

**Files:**
- Create: `narrate/social_text.py`, `narrate/grammar/social.toml`
- Modify (via `.patches/3a_task9.py`):
  - `narrate/brief.py`, `narrate/procedural.py`, `narrate/outcomes.py`
  - `engine/game.py`, `engine/sheet.py`, `engine/gossip.py`
- Test: `tests/test_surfacing.py`

**Interfaces:**
- Consumes: Task 4 (`attitude`, `reputation`) and Task 2 (`apparent_to`, `home_of`).
- Produces:
  - Greetings: outcome builders for `met` and `conversed` that add the line "X seems <word> toward you (<reason>)." only when a reason exists. They set `details["attitude"]`.
  - `_relationship` inserts the fact "X is <word> toward you: <reason>." first.
  - The grammar picks `met.hostile`, `conversed.hostile`, `met.warm` or `conversed.warm` by attitude.
  - `Game._patience` is shifted by attitude: +1 when warm, −1 when hostile or hateful, never below 1.
  - The F4 sheet gains a `Reputation:` block.
  - Arrival adds a dim line: "People here know you as the <epithet>." or "Some people here have heard of you."
  - `scene_brief` gains a reputation fact.

- [ ] **Step 1: Write the failing test** — `tests/test_surfacing.py`
```python
import pytest

import systems.encounters as encounters
from engine.game import Action, Game
from engine.sheet import sheet_lines
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event, Witness, commit
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("curious", "lazy"), occupation="innkeeper"):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": occupation, "traits": list(traits), "realm": "mortal", "surname": surname, "given": given,
        "gender": "man", "age": 40, "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def hate(game, npc):
    commit(game.world, [Event("insulted", (game.player.id, npc), game.place.id, {},
                              witnesses=(Witness(npc, "hatred", 1.0),))])


def bandit_kills(game, place):
    for name in ("Ma Bo", "Ma Da", "Ma San"):
        bandit = person(game, name, occupation="bandit")
        record_fact(game.world, game.player.id, "killed", bandit, place=place,
                    variant=make_variant("killed", game.player.id, bandit, place=game.world.entity(place).name,
                                         form="fist"))


def test_a_hostile_greeting_says_why(game):
    npc = person(game, "Old Wu")
    hate(game, npc)
    turn = game.perform(Action("talk", npc))
    assert "Old Wu seems hostile toward you (you wronged them)." in [text for text, _ in turn.lines]
    brief = game.last_briefs[0]
    assert brief.facts[0] == "Old Wu is hostile toward you: you wronged them."
    assert game.narrator._key(brief) == "met.hostile"


def test_a_stranger_is_greeted_as_before(game):
    turn = game.perform(Action("talk", person(game, "Hu Mei")))
    assert not any("seems" in text for text, _ in turn.lines)


def test_hostile_people_lose_patience_sooner(game):
    calm, cross = person(game, "Hu Mei"), person(game, "Old Wu")
    hate(game, cross)
    for npc, keeps_talking in ((calm, True), (cross, False)):
        game.perform(Action("talk", npc))
        for _ in range(4):
            game.perform(Action("ask", "work"))
        assert (game.focus == npc) is keeps_talking
        if game.focus is not None:
            game.perform(Action("farewell"))


def test_the_sheet_shows_reputation(game):
    bandit_kills(game, game.place.id)
    text = [line for line, _ in sheet_lines(game.world, game.player.id)]
    assert "Reputation:" in text
    assert any(line.startswith(f"  Here in {game.place.name}: renowned, righteous, known as the ") for line in text)


def test_arriving_somewhere_that_knows_you(game, monkeypatch):
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    road = next(c.action for c in game.start().all_choices if c.action.verb == "travel" and "north" in c.label)
    town = ensure_town(game.world, *road.target)
    bandit_kills(game, town)
    turn = game.perform(road)
    assert any(text.startswith("People here know you as the ") for text, _ in turn.lines)
    scene = next(b for b in game.last_briefs if b.kind == "scene")
    assert any("know you as the" in fact for fact in scene.facts)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_surfacing.py -q -p no:cacheprovider`
Expected: 4 of the 5 tests fail (all but `test_a_stranger_is_greeted_as_before`). For example, `AssertionError` on the "seems hostile" line and the missing `Reputation:` heading.

- [ ] **Step 3: Write the greeting builders** — `narrate/social_text.py`
```python
"""Greetings that show how someone feels about the player, and why (phase 3a spec 3.2)."""

from narrate.outcomes import cap, outcome
from systems.attitude import attitude
from systems.beliefs import apparent_to


@outcome("met", body_facts=False)
@outcome("conversed", body_facts=False)
def _greeting(world, event):
    player, npc = event.actors[0], event.actors[1]
    feeling = attitude(world, npc, apparent_to(world, npc, player))
    if not feeling.reason or feeling.word == "neutral":
        return [], {}
    return [f"{cap(world.entity(npc).name)} seems {feeling.word} toward you ({feeling.reason})."], \
        {"attitude": feeling.word}
```

- [ ] **Step 4: Write the greeting grammar** — `narrate/grammar/social.toml`
```toml
[symbols]
social_cold = ["{npc} does not return your greeting.", "{npc} looks at you as if at something spilled.", "{npc}'s hand drifts toward a weapon.", "{npc} steps back from you.", "{npc} answers through their teeth."]
social_cold_after = ["The air between you is thick.", "Others nearby fall silent.", "It will not be a friendly talk.", "Every word is weighed.", "They make no effort to hide it."]
social_warm = ["{npc} brightens at the sight of you.", "{npc} greets you like an old friend.", "{npc} makes room for you.", "{npc} smiles and bows.", "{npc} waves you over."]
social_warm_after = ["It is good to be welcome somewhere.", "They seem glad of the company.", "They pour you something to drink.", "The talk comes easily.", "They clearly think well of you."]

["met.hostile"]
colour = "npc"
lines = ["#social_cold# #social_cold_after#", "#social_cold_after# #social_cold#"]

["conversed.hostile"]
colour = "npc"
lines = ["#social_cold# #social_cold_after#", "#social_cold_after# #social_cold#"]

["met.warm"]
colour = "npc"
lines = ["#social_warm# #social_warm_after#", "#social_warm_after# #social_warm#"]

["conversed.warm"]
colour = "npc"
lines = ["#social_warm# #social_warm_after#", "#social_warm_after# #social_warm#"]
```

- [ ] **Step 5: Edit the existing files** — `.patches/3a_task9.py`
```python
"""Task 9 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


BRIEF = "narrate/brief.py"
edit(BRIEF, '''from systems.bodies import load_body
''', '''from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.bodies import load_body
from systems.reputation import reputation
''')
edit(BRIEF, '''    _patience_facts(world, npc, player, history, facts, details)
    return facts, details, prior''', '''    _patience_facts(world, npc, player, history, facts, details)
    feeling = attitude(world, npc.id, apparent_to(world, npc.id, player.id))
    if feeling.reason and feeling.word != "neutral":
        details["attitude"] = feeling.word
        facts.insert(0, f"{npc.name} is {feeling.word} toward you: {feeling.reason}.")
    return facts, details, prior''')
edit(BRIEF, '''    if known:
        facts.append("You already know " + ", ".join(known) + ".")''', '''    if known:
        facts.append("You already know " + ", ".join(known) + ".")
    fame = reputation(world, place_id, apparent_to(world, place_id, player_id))
    if fame.epithet:
        facts.append(f"People here know you as the {fame.epithet}.")
    elif fame.renown > 0:
        facts.append(f"People here have heard of you; you are {fame.word} here.")''')

edit("narrate/procedural.py", '''        if brief.kind == "conversed" and brief.details.get("annoyed_last_time")''', '''        mood = {"hostile": "hostile", "hateful": "hostile", "warm": "warm"}.get(brief.details.get("attitude", ""))
        if brief.kind in ("met", "conversed") and mood and f"{brief.kind}.{mood}" in self.grammar.tables:
            return f"{brief.kind}.{mood}"
        if brief.kind == "conversed" and brief.details.get("annoyed_last_time")''')
edit("narrate/outcomes.py", '''import narrate.mask_text  # noqa: E402,F401
''', '''import narrate.mask_text  # noqa: E402,F401
import narrate.social_text  # noqa: E402,F401
''')

GAME = "engine/game.py"
edit(GAME, '''from systems.bodies import load_body
''', '''from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.bodies import load_body
''')
edit(GAME, '''QUIET_KINDS = frozenset({"exchange"})''', '''QUIET_KINDS = frozenset({"exchange"})
PATIENCE_SHIFT = {"warm": 1, "hostile": -1, "hateful": -1}  # phase 3a spec 3.2''')
edit(GAME, '''    def _patience(self, npc) -> int:
        return talk.patience_of(npc)''', '''    def _patience(self, npc) -> int:
        feeling = attitude(self.world, npc.id, apparent_to(self.world, npc.id, self.player.id)).word
        return max(1, talk.patience_of(npc) + PATIENCE_SHIFT.get(feeling, 0))''')

SHEET = "engine/sheet.py"
edit(SHEET, '''from render.body_chart import SYMBOL
''', '''from render.body_chart import SYMBOL
from systems.beliefs import home_of
from systems.reputation import reputation
''')
edit(SHEET, '''    if not injuries:
        lines.append(("  none", "dim"))
    return lines''', '''    if not injuries:
        lines.append(("  none", "dim"))
    lines += [("", "default"), ("Reputation:", "heading")]
    town = home_of(world, player_id)
    if town is not None:
        lines.append((_standing(world, town, player_id, "Here"), "default"))
        for persona in world.entities("persona"):
            if persona.data.get("of") == player_id:  # your own masks: you know who wears them
                lines.append((_standing(world, town, persona.id, f"As {persona.name}"), "default"))
    return lines


def _standing(world: World, town: int, subject: int, label: str) -> str:
    name = world.entity(town).name
    rep = reputation(world, town, subject)
    if rep.word == "unknown":
        return f"  {label}: unknown in {name}"
    known_as = f", known as the {rep.epithet}" if rep.epithet else ""
    return f"  {label} in {name}: {rep.word}, {rep.path}{known_as}"''')

GOSSIP = "engine/gossip.py"
edit(GOSSIP, '''from systems.kin import ensure_kin
''', '''from systems.kin import ensure_kin
from systems.reputation import reputation
''')
edit(GOSSIP, '''        rumours.catch_up(self.world, self.place.id)
        if self.encounter is None:
            lines += self._exposures()
        return lines''', '''        rumours.catch_up(self.world, self.place.id)
        lines += self._fame()
        if self.encounter is None:
            lines += self._exposures()
        return lines

    def _fame(self) -> list:
        """What arriving here feels like, given what the town has heard."""
        rep = reputation(self.world, self.place.id, apparent_to(self.world, self.place.id, self.player.id))
        if rep.epithet:
            return [(f"People here know you as the {rep.epithet}.", "dim")]
        if rep.renown >= 2.0:
            return [("Some people here have heard of you.", "dim")]
        return []''')
print("task 9 edits applied")
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3a_task9.py && .venv/Scripts/python.exe -m pytest tests/test_surfacing.py -q -p no:cacheprovider`
Expected: `task 9 edits applied`, then `5 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass. Briefs still have at most 6 facts.

- [ ] **Step 7: Commit**

Run: `git add -A && git commit -m "feat: greetings, patience, F4 and arrivals show attitude and reputation"`

---

### Task 10: Knowledge rules, a gossip fuzz run, and the isolation proof

**Files:**
- Modify (via `.patches/3a_task10.py`): `debug/invariants.py`, `tests/test_fuzz.py`, `docs/debugging.md`
- Test: `tests/test_knowledge_rules.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `debug.invariants.check_knowledge(world) -> list[str]`, called from `check_world`.
  - `debug.invariants.check_people(game, turn) -> list[str]`, called from `check_turn`.
  - The fuzz test `test_a_life_of_rumours_and_masks`.

- [ ] **Step 1: Write the failing test** — `tests/test_knowledge_rules.py`
```python
import pytest

import systems.encounters as encounters
import systems.masks as masks
import systems.rumours as rumours
from debug.invariants import check_knowledge, check_people
from engine.actions import Turn
from engine.game import Action, Game
from engine.sheet import sheet_lines
from systems.attitude import attitude
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.reputation import reputation
from world.gen.materialize import ensure_town, people_at


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def test_the_name_rule_catches_a_stranger_named_on_screen(game):
    far = ensure_town(game.world, 4, 4, 0)
    zhao = game.world.add_entity("person", "Zhao Yun", {"realm": "mortal"})
    game.world.relate(zhao, far, "located_in")
    turn = Turn([("Zhao Yun waves from afar.", "npc")], [], {}, "")
    assert any("Zhao Yun" in problem for problem in check_people(game, turn))
    fid = record_fact(game.world, zhao, "spared", game.player.id, place=None,
                      variant=make_variant("spared", zhao, game.player.id))
    game.world.upsert_belief(game.player.id, fid, make_variant("spared", zhao, game.player.id), None, 0.5, 2, "told")
    assert check_people(game, turn) == []


def test_the_knowledge_rule_catches_a_face_behind_a_mask(game):
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    fid = record_fact(game.world, persona, "robbed", 999, place=None, variant=make_variant("robbed", persona, 999))
    assert check_knowledge(game.world) == []
    leaked = make_variant("robbed", game.player.id, 999)
    game.world.upsert_belief(12345, fid, leaked, None, 0.5, 2, "gossip")
    assert any("credited" in problem for problem in check_knowledge(game.world))


def test_a_lie_must_name_its_liar(game):
    with game.world.transaction():
        game.world.add_fact(1, "robbed", 2, is_true=False, data={"variant": make_variant("robbed", 1, 2)})
    assert any("lie" in problem for problem in check_knowledge(game.world))


def test_a_masked_killing_stays_with_the_mask(game, monkeypatch):
    for name in ("ART_CHANCE", "VOICE_CHANCE", "CHANGE_CHANCE"):
        monkeypatch.setattr(masks, name, 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "AVENGER_ROAD_CHANCE", 0.0)
    world, me = game.world, game.player.id
    with world.transaction():
        mask = world.add_entity("mask", "plain mask", {"persona": None})
        world.relate(me, mask, "owns")
    game.perform(Action("wear_mask"))
    persona = world.entity(me).data["masked"]
    victim = next(p for p in people_at(world, game.place.id, exclude=me))
    world.update_data(victim.id, traits=["proud", "honest"])
    game.perform(Action("challenge", victim.id))
    game.combat.stage, game.combat.harm = "verdict", {"player": 0.0, "opponent": 90.0}
    game.perform(Action("verdict", "kill"))
    game.perform(Action("remove_mask"))
    road = next(c.action for c in game.look().all_choices if c.action.verb == "travel" and "north" in c.label)
    game.perform(road)
    game.perform(Action("rest", 7))
    town = game.place.id
    rumours.catch_up(world, town)
    stranger = next(p for p in people_at(world, town, exclude=me) if not world.memories(p.id, about=me))
    assert reputation(world, town, persona).renown > 0
    assert reputation(world, town, me).renown == 0
    assert "killed" not in (attitude(world, stranger.id, me).reason or "")
    assert not any("renowned" in text or "known as" in text for text, _ in sheet_lines(world, me)
                   if text.startswith("  Here"))
    record_fact(world, persona, "is", me, place=town, variant=make_variant("is", persona, me))
    assert reputation(world, town, me).renown > 0
    assert "killed" in (attitude(world, stranger.id, me).reason or "")


def test_the_same_choices_make_the_same_world(tmp_path):
    digests = []
    for n in range(2):
        g = Game.new(tmp_path / f"d{n}.world", "Hero", world_seed=21, creation=CreationChoice("origin", "hunter"))
        turn = g.start()
        for step in range(40):
            turn = g.perform(turn.choices[(step * 7) % len(turn.choices)].action)
        digests.append(g.world.digest())
        g.close()
    assert digests[0] == digests[1]
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_rules.py -q -p no:cacheprovider`
Expected: the collection error `ImportError: cannot import name 'check_knowledge' from 'debug.invariants'`.

- [ ] **Step 3: Edit the rules, the fuzz test and the docs** — `.patches/3a_task10.py`
```python
"""Task 10 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


INV = "debug/invariants.py"
edit(INV, '''from narrate.brief import MAX_FACTS, MAX_PROMPT
''', '''from narrate.brief import MAX_FACTS, MAX_PROMPT
from systems.beliefs import known_people
from world.gen.materialize import people_at
''')
edit(INV, '''    problems += check_items(world)
''', '''    problems += check_items(world)
    problems += check_knowledge(world)
''')
edit(INV, '''def check_turn(game, turn, recent_narration: Sequence[str]) -> list[str]:
    problems = check_combat(game)''', '''def check_knowledge(world) -> list[str]:
    """Beliefs point at facts, lies name their liar, grief passes only from the dead, masks hide faces."""
    out = []
    player = world.get_meta("player_id")
    facts: dict = {}
    for belief in world.all_beliefs():
        if belief.fact_id not in facts:
            facts[belief.fact_id] = world.fact(belief.fact_id)
        fact = facts[belief.fact_id]
        if fact is None:
            out.append(f"#{belief.knower} believes missing fact #{belief.fact_id}")
            continue
        if not 0 <= belief.confidence <= 1 or belief.hops < 0:
            out.append(f"#{belief.knower} holds fact #{fact.id} at confidence {belief.confidence}, hops {belief.hops}")
        if belief.channel == "witness" and belief.hops != 0:
            out.append(f"#{belief.knower} witnessed fact #{fact.id} at {belief.hops} retellings")
        actor = belief.variant.get("actor")
        if actor is not None and actor != fact.subject:
            out.append(f"a retelling of fact #{fact.id} credited #{actor} instead of #{fact.subject}")
    for lie in world.facts(is_true=False):
        if "liar" not in lie.data or lie.source_event is None:
            out.append(f"lie #{lie.id} has no liar or no telling behind it")
    for memory in world.memories_inherited():
        source = world.entity(memory.inherited_from)
        if source is None or not source.data.get("dead"):
            out.append(f"#{memory.owner} inherited a memory from #{memory.inherited_from}, who is not dead")
    for persona in world.entities("persona"):
        if persona.data.get("of") != player:
            out.append(f"{persona.name} (#{persona.id}) is nobody's mask")
    return out


def check_people(game, turn) -> list[str]:
    """No one the player never met or heard of is named on screen; the dead never talk or fight."""
    world = game.world
    player_id = world.get_meta("player_id")
    player = world.entity(player_id) if player_id is not None else None
    if player is None:
        return []
    out = []
    for who, role in ((getattr(game, "focus", None), "conversation partner"),
                      (getattr(game, "challenger", None), "challenger")):
        if who is not None and world.entity(who).data.get("dead"):
            out.append(f"the dead #{who} is a {role}")
    encounter = getattr(game, "encounter", None)
    if encounter is not None and world.entity(encounter["person"]).data.get("dead"):
        out.append("a road encounter with the dead")
    text = "\\n".join([t for t, _ in turn.lines] + [c.label for c in turn.all_choices]).lower()
    known = {player.name.lower()}
    known |= {world.entity(p).name.lower() for p in known_people(world, player_id)}
    here = world.targets(player_id, "located_in")
    if here:
        known |= {p.name.lower() for p in people_at(world, here[0])}
    known |= {p.name.lower() for p in world.entities("persona") if p.data.get("of") == player_id}
    for kind in ("person", "persona"):
        for entity in world.entities(kind):
            name = entity.name.lower()
            if name in known or len(name) < 4:
                continue
            if re.search(rf"(?<![\\w-]){re.escape(name)}(?![\\w-])", text):
                out.append(f"{entity.name} (#{entity.id}) is named on screen but the player never heard of them")
    return out


def check_turn(game, turn, recent_narration: Sequence[str]) -> list[str]:
    problems = check_combat(game) + check_people(game, turn)''')

FUZZ = "tests/test_fuzz.py"
edit(FUZZ, '''         "challenge", "spar", "strike", "feint", "guard", "probe", "flee", "yield", "spare", "rob", "cripple"]''',
     '''         "challenge", "spar", "strike", "feint", "guard", "probe", "flee", "yield", "spare", "rob", "cripple",
         "kill", "news", "rumours", "tell", "wear mask", "remove mask", "ask about li", "ask news"]''')
edit(FUZZ, '''FIGHTING = ["strike", "feint", "guard", "probe", "strike", "guard", "flee", "yield", "spare", "rob", "cripple", "1", "2", "3", "4"]''',
     '''FIGHTING = ["strike", "feint", "guard", "probe", "strike", "guard", "flee", "yield", "spare", "rob", "cripple", "kill",
            "1", "2", "3", "4"]''')
Path(FUZZ).write_text(Path(FUZZ).read_text(encoding="utf-8") + '''

@pytest.mark.parametrize("seed", [5, 13])
def test_a_life_of_rumours_and_masks(tmp_path, seed, monkeypatch):
    """Killing, lying, masks and travel: every knowledge rule must hold throughout."""
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 2.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Gossip{seed}", world_seed=seed)
    world, me = app.game.world, app.game.player.id
    with world.transaction():
        mask = world.add_entity("mask", "plain mask", {"persona": None})
        world.relate(me, mask, "owns")
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["kill", "kill", "1", "2"]))
        elif game.focus is not None:
            app.submit(rng.choice(["news", "tell", "1", "2", "3", "4", "5", "6", "ask about li", "challenge", "bye"]))
        elif rng.random() < 0.3 and app.choices:
            app.submit(str(rng.randint(1, len(app.choices))))
        else:
            app.submit(rng.choice(["1", "2", "look", "rumours", "wear mask", "remove mask", "go north", "go east",
                                   "go south", "go west", "rest", "journal"]))
        assert app.state == "game", f"left the game at step {step}"
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()
''', encoding="utf-8", newline="\n")

edit("docs/debugging.md", '''Fragment lists are well-formed and hold at most 12.
''', '''Fragment lists are well-formed and hold at most 12.
- **The dead:** are buried (no location, one grave). They are never a conversation partner, a challenger or a road encounter.
- **Knowledge (phase 3a):** every belief points at a real fact, with confidence 0-1 and a first-hand witness at 0 retellings. A retelling never credits a deed to a different person (so a mask can't leak the face behind it). Every lie names its liar and the telling that started it. Inherited memories come only from the dead. Every persona is the player's.
- **Names on screen:** no person or persona is named in a turn unless the player has met them, heard of them, or they are standing here.
''')
print("task 10 edits applied")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe .patches/3a_task10.py && .venv/Scripts/python.exe -m pytest tests/test_knowledge_rules.py -q -p no:cacheprovider`
Expected: `task 10 edits applied`, then `5 passed`.

Run: `.venv/Scripts/python.exe -m pytest tests/test_fuzz.py -q -p no:cacheprovider`
Expected: every fuzz test passes, including `test_a_life_of_rumours_and_masks[5]` and `[13]`. If a rule fires, the failure lists the first 5 violations. Treat each one as a bug, find its cause with systematic debugging, and fix that. Do not loosen the rule.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 5: Commit**

Run: `git add -A && git commit -m "test: knowledge and name rules, gossip fuzz, masked-killing isolation proof"`

---

## Self-review

**Spec coverage:**

| Spec section | Where it is built |
|---|---|
| §2.1 save format v2 and migration | Task 1 |
| §2.2 modules | Tasks 1–9. Telling and exposure live in `systems/telling.py`, split out of `rumours.py` so no file is rewritten twice. |
| §3.1 fading | Task 1 |
| §3.2 attitude, bands, reasons and fear | Task 4. Uses (greetings, patience, refusals, grudges) are in Tasks 6 and 9. |
| §4.1 facts from events | Task 2 (fights, tolls), Task 5 (kills, left for dead), Task 7 (lies, exposure), Task 8 (`is`) |
| §4.2 beliefs, confidence and words | Task 2 |
| §5.1 channels 1–5 | Channels 1–2 in Task 2, channel 3 (kin) in Task 5, channel 4 (`catch_up`) in Task 3, channel 5 (telling) in Task 7 |
| §5.2 mutation and sensible-ness | Task 3, with a property test over 2,000 seeds |
| §5.3 picking news | Task 3, with hearing wired up in Task 7 |
| §6.1 kin | Task 5 |
| §6.2 kill, died and left for dead | Task 5 |
| §6.3 avengers | Task 5 (`avengers_for`, pause), Task 6 (in town and on the road) |
| §7.1 and §7.2 hearing and the Rumours page | Task 7 |
| §7.3 telling, lying and exposure | Task 7 |
| §8 masks and recognition | Task 8 |
| §9 reputation and its effects | Task 4, with effects in Tasks 6 and 9 and F4 in Task 9 |
| §10 narration | Tasks 5, 7, 8 and 9 |
| §11 debug rules | Rule 3 (buried) in Task 5; rules 1, 2, 4, 5 and 6 in Task 10 |
| §12 tests | Every task. Migration in Task 1, performance in Task 3, isolation, determinism and fuzz in Task 10. |

**Differences from the spec, each recorded as a ruling:**
- The truth column is named `is_true` rather than `true`, because `true` is an SQL keyword.
- The `died` actors are `(killer, victim)`, not `(victim, killer)`, so briefs keep the player at `actors[0]`.
- Lie exposure gives the victim the feeling `wronged` (−1.2, a grudge feeling, not indelible), because `hatred` is forced to be indelible.
- Killing a beast is judged +0.2, killing a bandit −0.5 and robbing a bandit −0.3. This is one reading of the spec's "+0.5/+0.2" modifiers.
- Buying a manual writes no `owns_manual` fact (purchases are private). Loot from a fight does.
- `backs_off` compares the bandit's realm with the player's real realm, not the realm the town believes.
- NPC-facing checks use `apparent_to` (the persona unless recognised). The player's own view always sees their own deeds.
- An `ask about <name>` event carries the person asked about as a third actor, so asking makes them known to the player. Recognition only considers `actors[1]` and the event's witnesses.

**Dry run:** before handing this plan over, all 10 tasks' files and patch scripts were applied in order to a scratch copy of `ae3aa53`+spec, and the full suite ran: 343 passed (261 existing + 82 new), including both new fuzz runs and the 50 ms `catch_up` timing test.

**Type consistency:**
- `record_fact` has the same keyword-only signature everywhere.
- `believe` takes `(world, knower, fact_id, variant, source, confidence, hops, channel)`.
- `knowledge_of` returns `(Belief, Fact)` pairs.
- `tell_events` takes `(world, player, listener, place, variant, fact_id=None, speaker_as=None)`.
- `onlookers` takes `(world, player, place, persona, putting_on)`.
- Encounter state is `{"person", "kind", "toll"}` everywhere.

**Review Focus coverage:**
- Item 1: `test_a_dead_roamer_is_never_met_again` (Task 5) and the `check_people` dead rules (Task 10).
- Item 2: `test_a_masked_player_is_greeted_as_a_stranger` (Task 8).
- Item 3: `test_a_version_1_save_is_upgraded_and_plays_on` (Task 1).
- Item 4: `test_the_conversation_menu_never_shows_more_than_nine` (Task 7).
- Item 5: `test_the_name_rule_catches_a_stranger_named_on_screen` (Task 10), plus the fuzz run.
