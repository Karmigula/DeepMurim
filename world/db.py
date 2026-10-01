"""The world file: one SQLite database per save, the single source of truth.

Nothing outside the engine writes here. Every table stays even when a system
doesn't use it yet, so later phases add tables rather than reshaping these.
"""

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

SCHEMA_VERSION = 2

SCHEMA = """
create table if not exists meta(key text primary key, value text not null);
create table if not exists entities(
    id integer primary key, kind text not null, name text not null,
    seed_path text unique, created_at integer not null, data text not null default '{}');
create table if not exists relations(
    a integer not null, b integer not null, kind text not null,
    value real not null default 0, since integer not null, data text not null default '{}',
    primary key(a, b, kind));
create index if not exists relations_b on relations(b, kind);
create table if not exists chronicle(
    id integer primary key, time integer not null, kind text not null,
    actors text not null, place integer, data text not null default '{}',
    weight real not null default 1);
create table if not exists memories(
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
    "create index if not exists entities_kind on entities(kind)",
    "create index if not exists facts_subject on facts(subject)",
    "create index if not exists facts_time on facts(time)",
    "create index if not exists facts_place on facts(place)",
    "create index if not exists beliefs_fact on beliefs(fact_id)",
    "create index if not exists beliefs_knower on beliefs(knower)",
    "create index if not exists memories_feeling on memories(feeling)",
    "create index if not exists beliefs_actor on beliefs(json_extract(variant, '$.actor'))",
    "create index if not exists beliefs_knower_actor on beliefs(knower, json_extract(variant, '$.actor'))",  # 4e
    "create index if not exists facts_predicate on facts(predicate)",  # 4e: the newest lists a town has heard
)
SCHEMA += ";\n".join(INDEXES) + ";\n"

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

TABLES = ("meta", "entities", "relations", "chronicle", "memories", "facts", "beliefs")
_ENTRY_COLUMNS = "c.id, c.time, c.kind, c.actors, c.place, c.data, c.weight"
_MEMORY_COLUMNS = "m.owner, m.feeling, m.intensity, m.indelible, m.inherited_from"
_FACT_COLUMNS = "f.id, f.subject, f.predicate, f.object, f.time, f.source_event, f.place, f.weight, f.is_true, f.data"
_BELIEF_COLUMNS = "b.knower, b.fact_id, b.variant_key, b.variant, b.source, b.confidence, b.learned_at, b.hops, b.channel"


class SaveError(Exception):
    """A save file that can't be opened, with a message fit to show a player."""


@dataclass(frozen=True)
class Entity:
    id: int
    kind: str
    name: str
    seed_path: str | None
    created_at: int
    data: dict


@dataclass(frozen=True)
class ChronicleEntry:
    id: int
    time: int
    kind: str
    actors: tuple[int, ...]
    place: int | None
    data: dict
    weight: float


@dataclass(frozen=True)
class Memory:
    owner: int
    event: ChronicleEntry
    feeling: str
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


def _entry(row) -> ChronicleEntry:
    return ChronicleEntry(row[0], row[1], row[2], tuple(json.loads(row[3])), row[4], json.loads(row[5]), row[6])


def _entity(row) -> Entity | None:
    if row is None:
        return None
    return Entity(row[0], row[1], row[2], row[3], row[4], json.loads(row[5]))


ENTITY_CACHE = 4096  # decoded entities kept between reads; the oldest go first
DRIFT_WINDOW = 64  # entities listed by kind that one drift check reads back, in turn: all are reached, cheaply


class World:
    def __init__(self, conn: sqlite3.Connection, path: Path) -> None:
        # WAL's recommended level: commits stop waiting on the disk; a power cut may lose the last turn, never the file
        conn.execute("pragma synchronous = normal")
        self._conn = conn
        self.path = path
        self._depth = 0
        self._cache: dict = {}
        self._cache_mark = -1
        # Every entity read decoded its JSON again: an arrival read the same 61 people 4,000 times. Entities are
        # snapshots; update_data stores a new one, a rollback or a bulk delete clears them all (cache_drift checks).
        self._entities: dict[int, Entity] = {}
        self._meta: dict = {}  # scalar meta values (the clock, the seed): a season reads `time` hundreds of times
        self._handed: set[int] = set()  # read since the last drift check: only these can have been edited in place
        self._listed: set[int] = set()  # handed out by entities(kind): checked DRIFT_WINDOW at a time, in id order
        self._drift_cursor = 0
        self._acquainted: dict[int, tuple[int, dict[int, int]]] = {}
        self._about: dict[int, tuple[int, list[int]]] = {}  # chronicle ids per entity, scanned once (6a review)

    def _cached(self, key, compute):
        """Reuse a read until anything in the world changes (sqlite counts every row written)."""
        mark = self._conn.total_changes
        if mark != self._cache_mark:
            self._cache.clear()
            self._cache_mark = mark
        if key not in self._cache:
            self._cache[key] = compute()
        return list(self._cache[key])

    @classmethod
    def create(cls, path, world_seed: int) -> "World":
        path = Path(path)
        if path.exists():
            raise SaveError(f"{path.name} already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = cls._connect(path)
        conn.executescript(SCHEMA)
        world = cls(conn, path)
        with world.transaction():
            world.set_meta("schema_version", SCHEMA_VERSION)
            world.set_meta("world_seed", world_seed)
            world.set_meta("time", 0)
        return world

    @classmethod
    def open(cls, path) -> "World":
        """Open a save, or raise SaveError with a message fit for the title screen.

        The version is read before anything is written (WAL mode is a write),
        so a foreign or future file is rejected untouched.
        """
        path = Path(path)
        if not path.is_file():
            raise SaveError(f"No save at {path}")
        conn = sqlite3.connect(path, isolation_level=None)
        try:
            row = conn.execute("select value from meta where key = 'schema_version'").fetchone()
            version = json.loads(row[0]) if row else None
        except (sqlite3.DatabaseError, ValueError) as exc:
            conn.close()
            raise SaveError(f"{path.name} is not a DeepMurim save ({exc})") from exc
        upgradable = isinstance(version, int) and not isinstance(version, bool) and version in MIGRATIONS
        if version != SCHEMA_VERSION and not upgradable:
            conn.close()
            raise SaveError(f"{path.name} has save version {version}; this game reads version {SCHEMA_VERSION}")
        try:
            conn.execute("pragma journal_mode = wal")
            problem = conn.execute("pragma quick_check").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            problem = str(exc)
        if problem != "ok":
            conn.close()
            raise SaveError(f"{path.name} is damaged ({problem})")
        world = cls(conn, path)
        if version != SCHEMA_VERSION:
            world._migrate(version)
        with world.transaction():  # indexes added after a save was made (optional; no version change)
            for statement in INDEXES:
                conn.execute(statement)
        return world

    @classmethod
    def open_readonly(cls, path) -> "World":
        """A save opened for reading only (phase 6: the MCP server). Any write raises sqlite3.OperationalError,
        so a read that would quietly create something (a seeded body, a recipe) fails loudly instead."""
        path = Path(path)
        if not path.is_file():
            raise SaveError(f"No save at {path}")
        # The MCP server answers in a worker thread; a read-only connection is safe to hand between threads.
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, isolation_level=None,
                               check_same_thread=False)
        row = conn.execute("select value from meta where key = 'schema_version'").fetchone()
        if row is None or json.loads(row[0]) != SCHEMA_VERSION:
            conn.close()
            raise SaveError(f"{path.name} is not a save this game reads")
        return cls(conn, path)

    def _migrate(self, version: int) -> None:
        """Bring an older save up to SCHEMA_VERSION, all or nothing."""
        with self.transaction():
            while version < SCHEMA_VERSION:
                for statement in MIGRATIONS[version]:
                    self._conn.execute(statement)
                version += 1
            self.set_meta("schema_version", SCHEMA_VERSION)

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(path, isolation_level=None)
        conn.execute("pragma journal_mode = wal")
        return conn

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """All-or-nothing. Nested calls join the outermost transaction."""
        if self._depth == 0:
            self._conn.execute("begin immediate")
        self._depth += 1
        try:
            yield
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self._conn.execute("rollback")
                self._entities.clear()  # what the transaction wrote is gone
                self._meta.clear()
            raise
        self._depth -= 1
        if self._depth == 0:
            self._conn.execute("commit")

    # --- meta -------------------------------------------------------------
    def get_meta(self, key: str, default=None):
        if key in self._meta:
            return self._meta[key]
        row = self._conn.execute("select value from meta where key = ?", (key,)).fetchone()
        if row is None:
            return default
        value = json.loads(row[0])
        if isinstance(value, (int, float, str, bool)):  # never a list or dict: a caller may edit what it gets back
            self._meta[key] = value
        return value

    def set_meta(self, key: str, value) -> None:
        self._conn.execute(
            "insert into meta(key, value) values(?, ?) on conflict(key) do update set value = excluded.value",
            (key, json.dumps(value)),
        )
        if isinstance(value, (int, float, str, bool)):
            self._meta[key] = value
        else:
            self._meta.pop(key, None)

    @property
    def world_seed(self) -> int:
        return int(self.get_meta("world_seed"))

    @property
    def time(self) -> int:
        return int(self.get_meta("time", 0))

    def set_time(self, t: int) -> None:
        self.set_meta("time", t)

    # --- entities ---------------------------------------------------------
    def add_entity(self, kind: str, name: str, data: dict | None = None, seed_path: str | None = None) -> int:
        cursor = self._conn.execute(
            "insert into entities(kind, name, seed_path, created_at, data) values(?, ?, ?, ?, ?)",
            (kind, name, seed_path, self.time, json.dumps(data or {})),
        )
        return cursor.lastrowid

    def entity(self, entity_id: int) -> Entity | None:
        found = self._entities.get(entity_id)
        if found is not None:
            self._handed.add(entity_id)
            return found
        found = _entity(self._conn.execute(
            "select id, kind, name, seed_path, created_at, data from entities where id = ?", (entity_id,)
        ).fetchone())
        if found is not None:
            self._remember(found)
            self._handed.add(entity_id)
        return found

    def _remember(self, entity: Entity) -> None:
        self._entities[entity.id] = entity
        if len(self._entities) > ENTITY_CACHE:
            del self._entities[next(iter(self._entities))]

    def cache_drift(self) -> list[str]:
        """Entities whose remembered data differs from the save: someone edited `.data` in place (debug rule).
        Only those handed out since the last check, so the per-turn rules stay cheap in a long game."""
        out = []
        handed, self._handed = self._handed, set()
        later = sorted(i for i in self._listed if i > self._drift_cursor)[:DRIFT_WINDOW]
        window = later + sorted(i for i in self._listed if i <= self._drift_cursor)[:DRIFT_WINDOW - len(later)]
        if window:  # an entity edited in place stays edited in the cache: its turn in the window will come
            self._drift_cursor = window[-1]
            self._listed.difference_update(window)
        for entity_id in sorted(handed.union(window)):
            remembered = self._entities.get(entity_id)
            if remembered is None:
                continue
            row = self._conn.execute("select data from entities where id = ?", (entity_id,)).fetchone()
            if row is None or json.loads(row[0]) != remembered.data:
                out.append(f"entity #{entity_id} ({remembered.name}) was changed in memory but not saved")
        return out

    def entity_by_seed(self, seed_path: str) -> Entity | None:
        return _entity(self._conn.execute(
            "select id, kind, name, seed_path, created_at, data from entities where seed_path = ?", (seed_path,)
        ).fetchone())

    def entities_after(self, kind: str, key: str, value) -> list[Entity]:
        """Entities of this kind whose data[key] is greater than `value` (phase 4c: live price events)."""
        rows = self._conn.execute(
            "select id, kind, name, seed_path, created_at, data from entities "
            f"where kind = ? and json_extract(data, '$.{key}') > ? order by id", (kind, value))
        return [_entity(row) for row in rows]

    def drop_entities_until(self, kind: str, key: str, value) -> None:
        """Delete entities of this kind whose data[key] is at most `value` (phase 4c: spent price events)."""
        where = f"kind = ? and json_extract(data, '$.{key}') <= ?"
        for (gone,) in self._conn.execute(f"select id from entities where {where}", (kind, value)).fetchall():
            self._entities.pop(gone, None)  # forget only what is deleted: this runs every season
        self._conn.execute(f"delete from entities where {where}", (kind, value))

    def entities(self, kind: str) -> list[Entity]:
        """Every entity of a kind, decoded once: a 500-year world's rules list 2,500 people each turn."""
        found = []
        for row in self._conn.execute(
                "select id, kind, name, seed_path, created_at, data from entities where kind = ? order by id", (kind,)):
            entity = self._entities.get(row[0])
            if entity is None:
                entity = _entity(row)
                self._remember(entity)
            found.append(entity)
        self._listed.update(e.id for e in found)  # the drift rule reaches them a window at a time
        return found

    def update_data(self, entity_id: int, **changes) -> None:
        current = self.entity(entity_id)
        if current is None:
            raise KeyError(entity_id)
        merged = {**current.data, **changes}
        self._conn.execute("update entities set data = ? where id = ?", (json.dumps(merged), entity_id))
        self._remember(replace(current, data=merged))  # a new snapshot: whoever holds the old one keeps it

    def rename(self, entity_id: int, name: str) -> None:
        """A new name for an entity (phase 5d: a refined piece, a named masterwork)."""
        current = self.entity(entity_id)
        if current is None:
            raise KeyError(entity_id)
        self._conn.execute("update entities set name = ? where id = ?", (name, entity_id))
        self._remember(replace(current, name=name))

    # --- relations --------------------------------------------------------
    def relate(self, a: int, b: int, kind: str, value: float = 0.0, data: dict | None = None) -> None:
        self._conn.execute(
            "insert into relations(a, b, kind, value, since, data) values(?, ?, ?, ?, ?, ?) "
            "on conflict(a, b, kind) do update set value = excluded.value, data = excluded.data",
            (a, b, kind, value, self.time, json.dumps(data or {})),
        )

    def unrelate(self, a: int, kind: str, b: int | None = None) -> None:
        if b is None:
            self._conn.execute("delete from relations where a = ? and kind = ?", (a, kind))
        else:
            self._conn.execute("delete from relations where a = ? and b = ? and kind = ?", (a, b, kind))

    def targets(self, a: int, kind: str) -> list[int]:
        rows = self._conn.execute("select b from relations where a = ? and kind = ? order by since, b", (a, kind))
        return [row[0] for row in rows]

    def sources(self, b: int, kind: str) -> list[int]:
        rows = self._conn.execute("select a from relations where b = ? and kind = ? order by a", (b, kind))
        return [row[0] for row in rows]

    def relations_to(self, b: int, kind: str) -> list[tuple[int, float, dict]]:
        """(source, value, data) for each relation of this kind pointing at `b`, by source id."""
        rows = self._conn.execute("select a, value, data from relations where b = ? and kind = ? order by a", (b, kind))
        return [(row[0], row[1], json.loads(row[2])) for row in rows]

    def relations_from(self, a: int, kind: str) -> list[tuple[int, float, dict]]:
        """(target, value, data) for each relation of this kind from `a`, oldest first."""
        rows = self._conn.execute(
            "select b, value, data from relations where a = ? and kind = ? order by since, b", (a, kind)
        )
        return [(row[0], row[1], json.loads(row[2])) for row in rows]

    # --- chronicle & memories ----------------------------------------------
    def append_chronicle(self, kind: str, actors: Sequence[int], place: int | None, data: dict, weight: float) -> int:
        cursor = self._conn.execute(
            "insert into chronicle(time, kind, actors, place, data, weight) values(?, ?, ?, ?, ?, ?)",
            (self.time, kind, json.dumps(list(actors)), place, json.dumps(data), weight),
        )
        return cursor.lastrowid

    def chronicle_of_kind(self, kind: str) -> list[ChronicleEntry]:
        """Every entry of one kind, oldest first (phase 4d: the yearly lists, one a year)."""
        rows = self._conn.execute(f"select {_ENTRY_COLUMNS} from chronicle c where c.kind = ? order by c.id", (kind,))
        return [_entry(row) for row in rows]

    def chronicle_about(self, entity_id: int, limit: int = 20) -> list[ChronicleEntry]:
        """This entity's latest chronicle entries, newest first. The chronicle only grows, so the ids of an
        entity's entries are remembered and only newer rows scanned: in a world of centuries a newcomer's few
        entries no longer cost a scan of every row each time (phase 6a review)."""
        seen_to, ids = self._about.get(entity_id, (0, []))
        top = self._conn.execute("select coalesce(max(id), 0) from chronicle").fetchone()[0]
        if top > seen_to:
            rows = self._conn.execute(
                "select c.id from chronicle c where c.id > ? and c.id <= ? "
                "and exists(select 1 from json_each(c.actors) where json_each.value = ?) order by c.id",
                (seen_to, top, entity_id))
            ids = ids + [row[0] for row in rows]
            if self._depth == 0:  # never remember a scan that a rollback could undo
                if len(self._about) >= ENTITY_CACHE:
                    self._about.clear()
                self._about[entity_id] = (top, ids)
        wanted = ids[-limit:] if limit > 0 else []
        if not wanted:
            return []
        rows = self._conn.execute(
            f"select {_ENTRY_COLUMNS} from chronicle c where c.id in ({','.join('?' * len(wanted))}) "
            "order by c.id desc", wanted)
        return [_entry(row) for row in rows]

    def add_memory(self, owner: int, event_id: int, feeling: str, intensity: float, indelible: bool = False,
                   inherited_from: int | None = None, ignore_existing: bool = False) -> None:
        verb = "insert or ignore" if ignore_existing else "insert"
        self._conn.execute(
            f"{verb} into memories(owner, event_id, feeling, intensity, indelible, inherited_from) values(?, ?, ?, ?, ?, ?)",
            (owner, event_id, feeling, intensity, int(indelible), inherited_from),
        )

    def memories(self, owner: int, about: int | None = None) -> list[Memory]:
        return self._cached(("memories", owner, about), lambda: self._memories(owner, about))

    def _memories(self, owner: int, about: int | None) -> list[Memory]:
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
        seen_to, last = self._acquainted.get(entity_id, (0, {}))
        rows = self._conn.execute(
            "select other.value, max(c.id) from chronicle c, json_each(c.actors) me, json_each(c.actors) other "
            "where c.id > ? and me.value = ? and other.value != ? group by other.value",
            (seen_to, entity_id, entity_id))
        last = {**last, **{row[0]: row[1] for row in rows}}  # only entries since the last call are scanned
        top = self._conn.execute("select coalesce(max(id), 0) from chronicle").fetchone()[0]
        if self._depth == 0:  # never remember a scan that a rollback could undo
            self._acquainted[entity_id] = (top, last)
        return sorted(last, key=lambda other: -last[other])

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

    def facts_after(self, after_id: int, until: int, predicates) -> list[Fact]:
        """Facts newer than `after_id`, no later than `until`, of these predicates (phase 4d: the Pavilion's informants)."""
        predicates = sorted(predicates)
        rows = self._conn.execute(
            f"select {_FACT_COLUMNS} from facts f where f.id > ? and f.time <= ? "
            f"and f.predicate in ({','.join('?' * len(predicates))}) order by f.id", (after_id, until, *predicates))
        return [_fact(row) for row in rows]

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

    def forget(self, knower: int, predicates, before: int) -> None:
        """Drop this knower's beliefs in facts of these predicates older than `before` (4e: the Pavilion's old news)."""
        predicates = sorted(predicates)
        self._conn.execute(
            f"delete from beliefs where knower = ? and fact_id in (select id from facts where time < ? "
            f"and predicate in ({','.join('?' * len(predicates))}))", (knower, before, *predicates))

    def beliefs(self, knower: int) -> list[Belief]:
        rows = self._conn.execute(
            f"select {_BELIEF_COLUMNS} from beliefs b where b.knower = ? order by b.learned_at, b.fact_id, b.variant_key",
            (knower,))
        return [_belief(row) for row in rows]

    def believers(self, fact_id: int) -> list[Belief]:
        rows = self._conn.execute(
            f"select {_BELIEF_COLUMNS} from beliefs b where b.fact_id = ? order by b.knower, b.variant_key", (fact_id,))
        return [_belief(row) for row in rows]

    def all_beliefs(self, after: int = 0) -> list[Belief]:
        """Every belief, or only those added after rowid `after` (see last_rowid)."""
        rows = self._conn.execute(f"select {_BELIEF_COLUMNS} from beliefs b where b.rowid > ? order by b.rowid", (after,))
        return [_belief(row) for row in rows]

    def last_rowid(self, table: str) -> int:
        if table not in TABLES:
            raise ValueError(table)
        return self._conn.execute(f"select coalesce(max(rowid), 0) from {table}").fetchone()[0]

    def known_facts(self, knower: int) -> list[tuple[Belief, Fact]]:
        """Each belief this knower holds, with its fact, oldest learned first."""
        return self._cached(("known_facts", knower), lambda: self._known_facts(knower))

    def known_facts_about(self, knowers, actors=None, predicate: str | None = None,
                          obj: int | None = None) -> list[tuple[Belief, Fact]]:
        """Beliefs held by any of `knowers`, narrowed in SQL by the story's actor, the predicate or the object."""
        knowers = list(knowers)
        if not knowers:
            return []
        sql = (f"select {_BELIEF_COLUMNS}, {_FACT_COLUMNS} from beliefs b join facts f on f.id = b.fact_id "
               f"where b.knower in ({','.join('?' * len(knowers))})")
        params: list = list(knowers)
        if actors is not None:
            actors = list(actors)
            sql += f" and json_extract(b.variant, '$.actor') in ({','.join('?' * len(actors))})"  # beliefs_actor index
            params += actors
        if predicate is not None:
            sql += " and f.predicate = ?"
            params.append(predicate)
        if obj is not None:
            sql += " and f.object = ?"
            params.append(str(obj))
        rows = self._conn.execute(sql + " order by b.fact_id, b.knower", params)
        return [(_belief(row[:9]), _fact(row[9:])) for row in rows]

    def renown_among(self, knower: int, actors) -> dict[int, float]:
        """What this knower's beliefs weigh for each of these actors, summed in SQL (the beliefs_actor index)."""
        actors = list(actors)
        rows = self._conn.execute(
            "select json_extract(b.variant, '$.actor'), sum(f.weight * b.confidence) from beliefs b "
            f"join facts f on f.id = b.fact_id where b.knower = ? and json_extract(b.variant, '$.actor') in "
            f"({','.join('?' * len(actors))}) group by 1", [knower, *actors])
        return {actor: total for actor, total in rows}

    def newest_known(self, knower: int, predicate: str, key: str) -> tuple[Belief, Fact] | None:
        """The belief of this predicate with the greatest variant `key` (the first learned among equals)."""
        row = self._conn.execute(
            f"select {_BELIEF_COLUMNS}, {_FACT_COLUMNS} from facts f cross join beliefs b on b.fact_id = f.id "
            f"where f.predicate = ? and b.knower = ? order by json_extract(b.variant, '$.' || ?) desc, "
            "b.fact_id limit 1", (predicate, knower, key)).fetchone()  # from the few facts of the kind, not the many beliefs
        return (_belief(row[:9]), _fact(row[9:])) if row else None

    def _known_facts(self, knower: int) -> list[tuple[Belief, Fact]]:
        rows = self._conn.execute(
            f"select {_BELIEF_COLUMNS}, {_FACT_COLUMNS} from beliefs b join facts f on f.id = b.fact_id "
            "where b.knower = ? order by b.learned_at, b.fact_id, b.variant_key", (knower,))
        return [(_belief(row[:9]), _fact(row[9:])) for row in rows]

    # --- integrity ----------------------------------------------------------
    def recent_chronicle_times(self, limit: int = 50) -> list[int]:
        """Times of the latest chronicle entries, oldest first."""
        rows = self._conn.execute("select time from chronicle order by id desc limit ?", (limit,))
        return [row[0] for row in rows][::-1]

    def backup_to(self, path) -> None:
        """A consistent copy of the live save, safe to take mid-session."""
        target = sqlite3.connect(Path(path))
        try:
            self._conn.backup(target)
        finally:
            target.close()

    def digest(self) -> str:
        """A hash of every row, for proving a save reloads identically."""
        h = hashlib.sha256()
        for table in TABLES:
            rows = sorted(repr(row) for row in self._conn.execute(f"select * from {table}"))
            h.update(table.encode())
            for row in rows:
                h.update(row.encode())
        return h.hexdigest()
