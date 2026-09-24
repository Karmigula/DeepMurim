"""World events (phase 4d spec 3): typed occurrences whose stages follow the calendar, and the modifiers they lend.

A type is an entry in `systems/data/world_events.toml`, and may name a module with hooks
(systems/sky.py says when each runs):

    eligible(world, place, n) -> bool           may one start here in season n?
    start_data(world, place, n, rng) -> dict    its own data, fixed when it starts (None: do not start)
    on_stage(world, occurrence, stage) -> list  the events of a stage, the first time it is observed

A fork adds an event with one TOML entry and one module; the engine is untouched.

This module only reads. The occurrences that still matter are listed in the `sky_index` meta
row as [id, type, scope, place, x, y, starts, active_from, active_to, over_at, done], so asking
what is in the sky over a place never scans the world's history.
"""

import tomllib
from pathlib import Path

from systems.time import DAYS_PER_SEASON, WATCHES_PER_DAY

SEASON = DAYS_PER_SEASON * WATCHES_PER_DAY
STAGES = ("foretold", "announced", "active", "aftermath")
SCOPES = ("world", "region", "town", "site")
FACTOR_MIN, FACTOR_MAX = 0.25, 4.0
KEEP_INDEXED = 44 * SEASON  # the life clock replays up to 40 missed seasons in full (4a) and asks about them
DATA = Path(__file__).parent / "data" / "world_events.toml"
DEFAULTS = {"module": None, "scope": "town", "cycle": "season", "chance": 0.0, "stages": {}, "modifiers": {},
            "prices": {}, "readings": [], "news": None}
TYPES: dict[str, dict] = {}
ID, TYPE, SCOPE, PLACE, X, Y, STARTS, ACTIVE_FROM, ACTIVE_TO, OVER_AT, DONE = range(11)


def full_spec(spec: dict) -> dict:
    unknown = sorted(set(spec) - set(DEFAULTS)) + sorted(set(spec.get("stages", {})) - set(STAGES))
    if unknown:
        raise ValueError(f"unknown event-type fields or stages: {unknown}")  # a fork's typo is caught, not ignored
    full = {**DEFAULTS, **spec}
    if full["scope"] not in SCOPES:
        raise ValueError(f"unknown scope {full['scope']!r}")
    full["stages"] = {stage: int(full["stages"].get(stage, 0)) for stage in STAGES}
    return full


def register(name: str, spec: dict) -> None:
    """Add or replace an event type (the TOML loader uses this; so may a fork)."""
    TYPES[name] = full_spec(spec)


def load_types(path: Path = DATA) -> None:
    with open(path, "rb") as handle:
        for name, spec in tomllib.load(handle).items():
            register(name, spec)


def schedule(spec: dict, starts: int) -> tuple[dict, int, int, int]:
    """(the end of each stage it has, when its active stage begins and ends, when it is over) from a start."""
    ends, t = {}, starts
    active_from = active_to = starts
    for stage in STAGES:
        days = spec["stages"][stage]
        if not days:
            continue
        if stage == "active":
            active_from = t
        t += days * WATCHES_PER_DAY
        ends[stage] = t
        if stage == "active":
            active_to = t
    return ends, active_from, active_to, t


def stage_at(data: dict, t: int) -> str:
    """Its stage at time t: "pending" before it starts, "over" once its last stage has ended."""
    if t < data["starts"]:
        return "pending"
    for stage in STAGES:
        end = data["ends"].get(stage)
        if end is not None and t < end:
            return stage
    return "over"


def stages_of(data: dict) -> list[str]:
    """The stages this occurrence has, in order, ending with "over"."""
    return [stage for stage in STAGES if stage in data["ends"]] + ["over"]


def index(world) -> list[list]:
    return world._cached(("sky_index",), lambda: world.get_meta("sky_index", []))


def _xy(world, place: int):
    entity = world.entity(place)
    return None if entity is None or "x" not in entity.data else (entity.data["x"], entity.data["y"])


def place_xy(world, place: int | None):
    """The region coordinates of a town or a region (a town's data carries its region's x and y)."""
    if place is None:
        return None
    return world._cached(("sky_xy", place), lambda: [_xy(world, place)])[0]


def covers(row: list, place: int | None, xy) -> bool:
    scope = row[SCOPE]
    if scope == "world":
        return True
    if place is None:
        return False
    if scope == "region":
        return xy is not None and (row[X], row[Y]) == tuple(xy)
    return row[PLACE] == place


def showing(world, place: int | None, at: int | None = None) -> list[list]:
    """Index rows over `place` that have begun and are not yet over at `at`."""
    at = world.time if at is None else at
    xy = place_xy(world, place)
    return [row for row in index(world) if row[STARTS] <= at < row[OVER_AT] and covers(row, place, xy)]


def factor(world, place: int | None, key: str, at: int | None = None) -> float:
    """The `key` modifiers of every occurrence active over `place` at `at` (None: the world-wide ones), clamped."""
    at = world.time if at is None else at
    hits = [row for row in index(world)
            if row[ACTIVE_FROM] <= at < row[ACTIVE_TO] and key in TYPES.get(row[TYPE], DEFAULTS)["modifiers"]]
    if not hits:
        return 1.0
    xy = place_xy(world, place)
    value = 1.0
    for row in hits:
        if covers(row, place, xy):
            value *= TYPES[row[TYPE]]["modifiers"][key]
    return max(FACTOR_MIN, min(FACTOR_MAX, value))


def price_factor(world, town: int, good: str) -> float:
    """The price multipliers of occurrences active over this town (4c market clamps the product)."""
    at = world.time
    hits = [row for row in index(world)
            if row[ACTIVE_FROM] <= at < row[ACTIVE_TO] and good in TYPES.get(row[TYPE], DEFAULTS)["prices"]]
    if not hits:
        return 1.0
    xy = place_xy(world, town)
    value = 1.0
    for row in hits:
        if covers(row, town, xy):
            value *= TYPES[row[TYPE]]["prices"][good]
    return value


load_types()
