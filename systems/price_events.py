"""What moves prices (phase 4c spec 5): war, famine, harvest, festivals, arming, and the player's own gluts.

Stored events are `price_event` entities with an `until`; festivals and arming are
worked out from the calendar and the factions each time. Every stored event and
every glut becomes a `shortage` or `glut` fact, the rumour that tells a trader where
the silver is.
"""

import systems.lives as lives
import systems.market as market
import systems.world_clock as world_clock
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.goods import region_goods
from systems.time import season_of
from world.events import Event, effect, listen
from world.gen.materialize import region_of
from world.seed import rng_for

FAMINE_CHANCE, HARVEST_CHANCE = 0.03, 0.05
GLUT_UNITS = 30
FACT_WEIGHT = 1.5
ARMING_BELOW = 40


def live(world) -> list:
    """Price events still in force: the database finds them, so centuries of old ones cost nothing."""
    return world._cached(("live_price_events", world.time),
                         lambda: world.entities_after("price_event", "until", world.time))


def factor(world, town: int, good: str) -> float:
    """The combined effect of every live event on this good in this town (market clamps the product)."""
    region = region_of(world, town).id
    value = 1.0
    for event in live(world):
        d = event.data
        if (d["scope"] == "town" and d["place"] == town) or (d["scope"] == "region" and d["place"] == region):
            value *= d["multipliers"].get(good, 1.0)
    data = world.entity(town).data
    if data.get("kind") == "city" and good in ("wine", "silk") and season_of(world.time) == "spring":
        value *= 1.4  # the spring festival
    if good == "iron":
        for fid in data.get("seats", []):
            faction = world.entity(fid).data
            if faction.get("type") in F.STAFFED and not faction.get("dissolved") \
                    and faction.get("power", 50) < ARMING_BELOW:
                value *= 1.2  # a faction arming itself
    return value


market.EVENT_FACTORS.append(factor)


def _fact_town(world, scope: str, place: int) -> int | None:
    if scope == "town":
        return place
    towns = sorted(t for t in world.sources(place, "located_in") if world.entity(t).kind == "town")
    return towns[0] if towns else None


def _news(world, town: int, good: str, dear: bool, source_event: int | None = None) -> None:
    predicate = "shortage" if dear else "glut"
    variant = make_variant(predicate, town, None, place=place_name(world, town))
    variant["good"] = good
    record_fact(world, town, predicate, None, place=town, source_event=source_event, weight=FACT_WEIGHT,
                variant=variant, extra={"good": good, "price": market.price(world, town, good)})


def shift(world, scope: str, place: int, multipliers: dict, until: int, cause: str, news: bool = True) -> int:
    """A price event from now until `until`, and (unless `news` is off) the rumours it starts."""
    event = world.add_entity("price_event", f"{cause} at #{place}",
                             {"scope": scope, "place": place, "multipliers": multipliers, "until": until, "cause": cause})
    town = _fact_town(world, scope, place) if news else None
    if town is not None:
        for good, value in multipliers.items():
            if value != 1.0:
                _news(world, town, good, value > 1.0)
    return event


@listen("clash")
def _war_prices(world, event, event_id: int) -> None:
    town = event.place
    if town is None or world.entity(town).kind != "town":
        return
    until = world.time + lives.SEASON
    here = {"iron": 1.8, "herbs": 1.5, **({"rice": 1.5} if event.data.get("hall_lost") else {})}
    shift(world, "region", region_of(world, town).id, {"iron": 1.3}, until, "war nearby", news=False)  # one rumour per war
    shift(world, "town", town, here, until, "war")  # last, so its rumour carries the full price


def season_events(world, n: int) -> list[Event]:
    """Famines and bumper harvests across the materialized regions (spec §5)."""
    events = []
    regions = world.entities("region")
    for region in regions:
        if rng_for(world.world_seed, f"famine:{region.id}:{n}").random() < FAMINE_CHANCE:
            until = world.time + 2 * lives.SEASON
            events.append(Event("price_shift", (), None, {"scope": "region", "place": region.id,
                                                          "multipliers": {"rice": 3.0, "salt": 1.5}, "until": until,
                                                          "cause": "famine"}))
            for other in regions:
                d, o = region.data, other.data
                if other.id != region.id and max(abs(d["x"] - o["x"]), abs(d["y"] - o["y"])) == 1:
                    events.append(Event("price_shift", (), None, {"scope": "region", "place": other.id,
                                                                  "multipliers": {"rice": 1.5}, "until": until,
                                                                  "cause": "famine nearby"}))
        if rng_for(world.world_seed, f"harvest:{region.id}:{n}").random() < HARVEST_CHANCE:
            made, _ = region_goods(world, region)
            events.append(Event("price_shift", (), None, {"scope": "region", "place": region.id,
                                                          "multipliers": {g: 0.6 for g in made},
                                                          "until": world.time + lives.SEASON, "cause": "harvest"}))
    return events


world_clock.SEASON_HOOKS.append(season_events)


@effect("price_shift")
def _price_shift(world, event) -> None:
    d = event.data
    shift(world, d["scope"], d["place"], d["multipliers"], d["until"], d["cause"])


@listen("traded")
def _player_glut(world, event, event_id: int) -> None:
    d = event.data
    if d["side"] != "sell":
        return
    player, town = event.actors[0], event.place
    sold = dict(world.entity(player).data.get("sold_today", {}))
    key = f"{town}:{d['good']}"
    day, count = sold.get(key, [d["day"], 0])
    count = (count if day == d["day"] else 0) + d["n"]
    sold[key] = [d["day"], count]
    world.update_data(player, sold_today=sold)
    if count >= GLUT_UNITS > count - d["n"]:  # once, as the day's selling crosses the mark
        _news(world, town, d["good"], False, source_event=event_id)
