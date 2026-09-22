"""The world file: one SQLite database per save, the single source of truth.

Nothing outside the engine writes here. Every table stays even when a system
doesn't use it yet, so later phases add tables rather than reshaping these.
"""

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1

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

TABLES = ("meta", "entities", "relations", "chronicle", "memories", "facts", "beliefs")
_ENTRY_COLUMNS = "c.id, c.time, c.kind, c.actors, c.place, c.data, c.weight"


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


def _entry(row) -> ChronicleEntry:
    return ChronicleEntry(row[0], row[1], row[2], tuple(json.loads(row[3])), row[4], json.loads(row[5]), row[6])


def _entity(row) -> Entity | None:
    if row is None:
        return None
    return Entity(row[0], row[1], row[2], row[3], row[4], json.loads(row[5]))


class World:
    def __init__(self, conn: sqlite3.Connection, path: Path) -> None:
        self._conn = conn
        self.path = path
        self._depth = 0

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
        path = Path(path)
        if not path.is_file():
            raise SaveError(f"No save at {path}")
        try:
            conn = cls._connect(path)
            row = conn.execute("select value from meta where key = 'schema_version'").fetchone()
        except sqlite3.DatabaseError as exc:
            raise SaveError(f"{path.name} is not a DeepMurim save ({exc})") from exc
        version = json.loads(row[0]) if row else None
        if version != SCHEMA_VERSION:
            conn.close()
            raise SaveError(f"{path.name} has save version {version}; this game reads version {SCHEMA_VERSION}")
        return cls(conn, path)

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
            raise
        self._depth -= 1
        if self._depth == 0:
            self._conn.execute("commit")

    # --- meta -------------------------------------------------------------
    def get_meta(self, key: str, default=None):
        row = self._conn.execute("select value from meta where key = ?", (key,)).fetchone()
        return default if row is None else json.loads(row[0])

    def set_meta(self, key: str, value) -> None:
        self._conn.execute(
            "insert into meta(key, value) values(?, ?) on conflict(key) do update set value = excluded.value",
            (key, json.dumps(value)),
        )

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
        return _entity(self._conn.execute(
            "select id, kind, name, seed_path, created_at, data from entities where id = ?", (entity_id,)
        ).fetchone())

    def entity_by_seed(self, seed_path: str) -> Entity | None:
        return _entity(self._conn.execute(
            "select id, kind, name, seed_path, created_at, data from entities where seed_path = ?", (seed_path,)
        ).fetchone())

    def entities(self, kind: str) -> list[Entity]:
        rows = self._conn.execute(
            "select id, kind, name, seed_path, created_at, data from entities where kind = ? order by id", (kind,)
        )
        return [_entity(row) for row in rows]

    def update_data(self, entity_id: int, **changes) -> None:
        current = self.entity(entity_id)
        if current is None:
            raise KeyError(entity_id)
        merged = {**current.data, **changes}
        self._conn.execute("update entities set data = ? where id = ?", (json.dumps(merged), entity_id))

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

    # --- chronicle & memories ----------------------------------------------
    def append_chronicle(self, kind: str, actors: Sequence[int], place: int | None, data: dict, weight: float) -> int:
        cursor = self._conn.execute(
            "insert into chronicle(time, kind, actors, place, data, weight) values(?, ?, ?, ?, ?, ?)",
            (self.time, kind, json.dumps(list(actors)), place, json.dumps(data), weight),
        )
        return cursor.lastrowid

    def chronicle_about(self, entity_id: int, limit: int = 20) -> list[ChronicleEntry]:
        rows = self._conn.execute(
            f"select {_ENTRY_COLUMNS} from chronicle c "
            "where exists(select 1 from json_each(c.actors) where json_each.value = ?) "
            "order by c.id desc limit ?",
            (entity_id, limit),
        )
        return [_entry(row) for row in rows]

    def add_memory(self, owner: int, event_id: int, feeling: str, intensity: float, indelible: bool = False) -> None:
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
        return [Memory(row[0], _entry(row[4:]), row[1], row[2], bool(row[3])) for row in rows]

    # --- integrity ----------------------------------------------------------
    def digest(self) -> str:
        """A hash of every row, for proving a save reloads identically."""
        h = hashlib.sha256()
        for table in TABLES:
            rows = sorted(repr(row) for row in self._conn.execute(f"select * from {table}"))
            h.update(table.encode())
            for row in rows:
                h.update(row.encode())
        return h.hexdigest()
