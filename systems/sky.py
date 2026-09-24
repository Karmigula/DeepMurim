"""The sky's clock (phase 4d spec 3): occurrences start, their stages are observed, and towns talk.

`start_events` begins an occurrence. `observe` commits a `world_event_stage` event for each
stage reached but not yet seen, and the type's module reacts. The world clock rolls the
season-cycle types and observes everything each season; the engine observes the player's
place on every scene, so what happens in the sky happens whether or not anyone is there.
"""

import importlib

import systems.market as market
import systems.world_clock as world_clock
import systems.world_events as W
from systems.facts import make_variant, place_name, record_fact
from systems.time import DAYS_PER_SEASON, WATCHES_PER_DAY
from world.events import Event, commit, effect, listen
from world.seed import rng_for

NEWS_STAGES = ("announced", "active")
LOCAL = ("town", "site")


def module(kind: str):
    path = W.TYPES[kind]["module"]
    return importlib.import_module(path) if path else None


def _hook(kind: str, name: str):
    found = module(kind) if kind in W.TYPES else None
    return getattr(found, name, None) if found is not None else None


def start_events(world, kind: str, place: int | None, starts: int, data: dict | None = None) -> list[Event]:
    """An occurrence of `kind` over `place` from `starts`; none if one is live there or it would be long over."""
    spec = W.TYPES[kind]
    ends, active_from, active_to, over_at = W.schedule(spec, starts)
    if over_at <= world.time:
        return []
    if any(row[W.TYPE] == kind and row[W.PLACE] == place and not row[W.DONE] and row[W.OVER_AT] > starts
           for row in W.index(world)):
        return []
    x, y = W.place_xy(world, place) or (None, None)
    return [Event("sky_started", (), place if spec["scope"] in LOCAL else None, {
        "type": kind, "scope": spec["scope"], "place": place, "x": x, "y": y, "starts": starts, "ends": ends,
        "active": [active_from, active_to], "over_at": over_at, "data": data or {}})]


@effect("sky_started")
def _started(world, event) -> None:
    d = event.data
    occurrence = world.add_entity("world_event", d["type"].replace("_", " "), {**d, "seen": [], "over": False})
    keep = [row for row in W.index(world) if row[W.OVER_AT] > world.time - W.KEEP_INDEXED]
    keep.append([occurrence, d["type"], d["scope"], d["place"], d["x"], d["y"], d["starts"], d["active"][0],
                 d["active"][1], d["over_at"], False])
    world.set_meta("sky_index", keep)


def stage_events(world, place: int | None = None) -> list[Event]:
    """An event for every stage reached but not yet seen, over `place` (everywhere when None)."""
    now = world.time
    xy = W.place_xy(world, place)
    events = []
    for row in W.index(world):
        if row[W.DONE] or now < row[W.STARTS] or (place is not None and not W.covers(row, place, xy)):
            continue
        occurrence = world.entity(row[W.ID])
        d = occurrence.data
        order = W.stages_of(d)
        for stage in order[: order.index(W.stage_at(d, now)) + 1]:
            if stage not in d["seen"]:
                events.append(Event("world_event_stage", (), d["place"] if d["scope"] in LOCAL else None,
                                    {"occurrence": occurrence.id, "type": d["type"], "stage": stage}))
    return events


def observe(world, place: int | None = None) -> list[int]:
    events = stage_events(world, place)
    return commit(world, events) if events else []


@effect("world_event_stage")
def _stage(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    world.update_data(occurrence.id, seen=list(occurrence.data["seen"]) + [d["stage"]], over=d["stage"] == "over")
    if d["stage"] == "over":
        world.set_meta("sky_index", [row if row[W.ID] != occurrence.id else row[:W.DONE] + [True]
                                     for row in W.index(world)])


@listen("world_event_stage")
def _react(world, event, event_id: int) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    _news(world, occurrence, d["stage"], event_id)
    react = _hook(d["type"], "on_stage")
    if react is not None:
        events = react(world, occurrence, d["stage"])
        if events:
            commit(world, events)


def news_town(world, d: dict) -> int | None:
    """The town whose people first talk about an occurrence."""
    if d["scope"] in LOCAL:
        return d["place"]
    if d["scope"] == "region":
        towns = sorted(t for t in world.sources(d["place"], "located_in") if world.entity(t).kind == "town")
        return towns[0] if towns else None
    capital = world.get_meta("capital")
    if capital is not None:
        return capital
    towns = world.entities("town")
    return towns[0].id if towns else None


def reading(world, kind: str, town: int) -> str | None:
    """What this town makes of it: each town has its own superstition (spec §3.5)."""
    readings = W.TYPES.get(kind, W.DEFAULTS)["readings"]
    return rng_for(world.world_seed, f"reading:{kind}:{town}").choice(readings) if readings else None


def _news(world, occurrence, stage: str, event_id: int) -> None:
    d = occurrence.data
    news = W.TYPES.get(d["type"], W.DEFAULTS)["news"]
    if not news or stage not in news.get("stages", NEWS_STAGES) or d["ends"].get(stage, d["over_at"]) <= world.time:
        return  # a stage that ended before anyone told of it is not news (a catch-up; final review)
    town = news_town(world, d)
    if town is None:
        return
    predicate = news.get("predicate", "phenomenon")
    variant = make_variant(predicate, town, None, place=place_name(world, town))
    variant.update(kind=d["type"], stage=stage, reading=reading(world, d["type"], town))
    record_fact(world, town, predicate, None, place=town, source_event=event_id, weight=news.get("weight", 1.0),
                variant=variant, extra={"occurrence": occurrence.id, "until": d["ends"].get(stage, d["over_at"])})


def _places(world, scope: str) -> list[tuple[int | None, str]]:
    if scope == "world":
        return [(None, "world")]
    kind = "town" if scope == "town" else "region"
    return [(e.id, e.seed_path or str(e.id)) for e in world.entities(kind)]


def _site(world, region: int, rng) -> int | None:
    towns = sorted(t for t in world.sources(region, "located_in") if world.entity(t).kind == "town")
    return rng.choice(towns) if towns else None


def season_events(world, n: int) -> list[Event]:
    """Roll every season-cycle type for season n; each starts on a day of that season (spec §3.3)."""
    events = []
    for kind in sorted(W.TYPES):
        spec = W.TYPES[kind]
        if spec["cycle"] != "season" or spec["chance"] <= 0:
            continue
        for place, path in _places(world, spec["scope"]):
            rng = rng_for(world.world_seed, f"sky:{kind}:{path}:{n}")
            if rng.random() >= spec["chance"]:
                continue
            where = _site(world, place, rng) if spec["scope"] == "site" else place
            if spec["scope"] == "site" and where is None:
                continue
            starts = n * W.SEASON + rng.randrange(DAYS_PER_SEASON) * WATCHES_PER_DAY
            if W.schedule(spec, starts)[3] <= world.time:
                continue  # long over: a catch-up never starts old events now
            eligible = _hook(kind, "eligible")
            if eligible is not None and not eligible(world, where, n):
                continue
            make = _hook(kind, "start_data")
            data = make(world, where, n, rng) if make is not None else {}
            if data is not None:
                events += start_events(world, kind, where, starts, data)
    return events


def observe_all(world, n: int) -> list[Event]:
    """Every occurrence reaches its stages each season, whoever is watching."""
    observe(world)
    return []


world_clock.SEASON_HOOKS.extend([season_events, observe_all])
market.EVENT_FACTORS.append(W.price_factor)
for _kind in sorted(W.TYPES):
    module(_kind)  # a type's module may register hooks of its own (the blood moon's patrols)
