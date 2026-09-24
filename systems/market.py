"""Markets (phase 4c spec 4): prices computed on demand, stock that recovers, buying and selling.

price = base x region x town kind x events x (1 / stock) x drift, rounded, at least 1.
Stock is stored as [value, day] and recovers lazily toward 1.0 when read.
"""

from collections.abc import Callable

from systems import factions as F
from systems import halls
from systems.goods import GOODS, LACKED, MULE_CAPACITY, MULE_PRICE, PRODUCED, capacity, carried, fit, pack_weight, region_goods
from systems.purse import silver_of
from world.events import Event, effect
from world.gen.materialize import region_of
from world.seed import rng_for

STOCK_STEP, STOCK_MIN, STOCK_MAX, RECOVERY = 0.01, 0.1, 3.0, 0.1
SELL_CUT, GUILD_CUT = 0.9, 0.95
EVENT_MIN, EVENT_MAX = 0.3, 4.0
EVENT_FACTORS: list[Callable] = []  # (world, town, good) -> factor; price_events.py registers here


def day(world) -> int:
    return world.time // 4


def drift(world, town: int, good: str) -> float:
    return rng_for(world.world_seed, f"market:{town}:{good}:{day(world)}").uniform(0.95, 1.05)


def stock(world, town: int, good: str) -> float:
    found = world.entity(town).data.get("market", {}).get(good)
    if found is None:
        return 1.0
    value, since = found
    return round(1.0 + (value - 1.0) * (1.0 - RECOVERY) ** max(0, day(world) - since), 6)


def event_factor(world, town: int, good: str) -> float:
    factor = 1.0
    for hook in EVENT_FACTORS:
        factor *= hook(world, town, good)
    return max(EVENT_MIN, min(EVENT_MAX, factor))


def _region_factor(world, town: int, good: str) -> float:
    made, lacking = region_goods(world, region_of(world, town))
    return PRODUCED if good in made else LACKED if good in lacking else 1.0


def _kind_factor(world, town: int, good: str) -> float:
    kind, category = world.entity(town).data.get("kind"), GOODS[good][2]
    if kind == "city" and category == "luxury":
        return 1.2
    if kind == "village" and category == "staple":
        return 0.9
    return 1.0


def price(world, town: int, good: str, n: int = 0) -> int:
    """The price of one unit; with `n` (bought > 0, sold < 0) each unit is charged at the average stock
    over the whole trade, so buying and selling back always loses the cut (phase 4c final review)."""
    base = GOODS[good][0]
    held = max(STOCK_MIN, min(STOCK_MAX, stock(world, town, good) - STOCK_STEP * n / 2))
    value = base * _region_factor(world, town, good) * _kind_factor(world, town, good) \
        * event_factor(world, town, good) / held * drift(world, town, good)
    return max(1, round(value))


def _guild_here(world, town: int) -> bool:
    return any(world.entity(f).data["type"] == "merchant_guild" for f in halls.halls_here(world, town))


def sell_price(world, town: int, good: str, n: int = 1) -> int:
    """What each of `n` units sold here fetches."""
    return max(1, int(price(world, town, good, -n) * (GUILD_CUT if _guild_here(world, town) else SELL_CUT)))


def prices(world, town: int) -> dict[str, int]:
    return {good: price(world, town, good) for good in GOODS}


def buy_block(world, player: int, town: int, good: str, n: int) -> str | None:
    if good not in GOODS or n <= 0:
        return "There is no such trade."
    if silver_of(world, player) < price(world, town, good, n) * n:
        return "You cannot afford that."
    if pack_weight(carried(world, player)) + GOODS[good][1] * n > capacity(world, player):
        return "Your pack cannot hold that much."
    if stock(world, town, good) - STOCK_STEP * n < STOCK_MIN - 1e-9:
        return f"The market has little {good} left."
    return None


def sell_block(world, player: int, town: int, good: str, n: int) -> str | None:
    if good not in GOODS or n <= 0:
        return "There is no such trade."
    if carried(world, player).get(good, 0) < n:
        return f"You have no {good} to sell." if not carried(world, player).get(good) else f"You have only {carried(world, player)[good]} {good}."
    return None


def buy_events(world, player: int, town: int, good: str, n: int) -> list[Event]:
    unit = price(world, town, good, n)
    return [Event("traded", (player,), town, {"good": good, "n": n, "side": "buy", "unit": unit, "total": unit * n,
                                             "day": day(world)})]


def sell_events(world, player: int, town: int, good: str, n: int) -> list[Event]:
    unit = sell_price(world, town, good, n)
    return [Event("traded", (player,), town, {"good": good, "n": n, "side": "sell", "unit": unit, "total": unit * n,
                                             "day": day(world)})]


def mule_block(world, player: int) -> str | None:
    if world.entity(player).data.get("mule"):
        return "You already have a mule."
    if silver_of(world, player) < MULE_PRICE:
        return f"A mule costs {MULE_PRICE} silver."
    return None


def mule_events(world, player: int, town: int) -> list[Event]:
    return [Event("bought_mule", (player,), town, {"price": MULE_PRICE})]


def record_visit(world, player: int, town: int) -> None:
    """Seeing a market writes its prices into the player's price book (spec §6)."""
    book = dict(world.entity(player).data.get("price_book", {}))
    book[str(town)] = {"time": world.time, "source": "visit", "prices": prices(world, town)}
    world.update_data(player, price_book=book)


@effect("traded")
def _traded(world, event) -> None:
    player, town, d = event.actors[0], event.place, event.data
    pack = carried(world, player)
    sign = 1 if d["side"] == "buy" else -1
    pack[d["good"]] = pack.get(d["good"], 0) + sign * d["n"]
    world.update_data(player, goods={g: n for g, n in pack.items() if n > 0},
                      silver=silver_of(world, player) - sign * d["total"])
    market = dict(world.entity(town).data.get("market", {}))
    now = max(STOCK_MIN, min(STOCK_MAX, stock(world, town, d["good"]) - sign * STOCK_STEP * d["n"]))
    market[d["good"]] = [round(now, 6), d["day"]]
    world.update_data(town, market=market)


@effect("bought_mule")
def _mule(world, event) -> None:
    player = event.actors[0]
    world.update_data(player, silver=silver_of(world, player) - event.data["price"], mule=True)


def known_prices(world, player: int) -> dict[int, dict[str, tuple[int, int, str]]]:
    """What the player knows of prices, {town: {good: (price, time, source)}}: their visits, and the
    shortages and gluts they believe (spec §6). Each price keeps its own age (phase 4c final review)."""
    book = {int(t): {g: (p, e["time"], e["source"]) for g, p in e["prices"].items()}
            for t, e in world.entity(player).data.get("price_book", {}).items()}
    for belief, fact in world.known_facts(player):
        if fact.predicate not in ("shortage", "glut") or fact.place is None or "good" not in fact.data:
            continue
        entry = book.setdefault(fact.place, {})
        good = fact.data["good"]
        if good not in entry or fact.time > entry[good][1]:
            entry[good] = (fact.data["price"], fact.time, "rumour")
    return book


def town_line(world, town: int) -> str | None:
    """The good that is cheapest and the one that is dearest here today, for a brief (spec §8)."""
    ratios = {good: price(world, town, good) / GOODS[good][0] for good in GOODS}
    cheap, dear = min(ratios, key=lambda g: (ratios[g], g)), max(ratios, key=lambda g: (ratios[g], g))
    if cheap == dear:
        return None
    return f"Here {cheap} is cheap and {dear} is dear."


MULE_THEFT = 0.3


def robbery_events(world, player: int, robber: int, place: int, duel_id) -> list[Event]:
    """A robber takes half of each good, and perhaps the mule (spec §7); without the mule, whatever
    the pack can no longer hold goes with it, the cheapest for its weight first (phase 4c final review)."""
    pack = carried(world, player)
    taken = {g: n // 2 for g, n in pack.items() if n // 2}
    mule = bool(world.entity(player).data.get("mule")) \
        and rng_for(world.world_seed, f"mule:{duel_id}").random() < MULE_THEFT
    if mule:
        _, shed = fit({g: n - taken.get(g, 0) for g, n in pack.items()}, capacity(world, player) - MULE_CAPACITY)
        for good, n in shed.items():
            taken[good] = taken.get(good, 0) + n
    if not taken and not mule:
        return []
    return [Event("lost_goods", (player, robber), place, {"goods": taken, "mule": mule, "reason": "robbed"})]


def toll_goods(world, player: int, town: int, toll: int) -> dict | None:
    """Goods worth at least the toll at local prices, the most valuable for their weight first; None if too poor."""
    pack, paid, worth = carried(world, player), {}, 0
    for good in sorted(pack, key=lambda g: (-GOODS[g][0] / GOODS[g][1], g)):
        unit = sell_price(world, town, good)
        for _ in range(pack[good]):
            if worth >= toll:
                break
            paid[good] = paid.get(good, 0) + 1
            worth += unit
    return paid if worth >= toll else None


def toll_events(world, player: int, bandit: int, town: int, toll: int) -> list[Event]:
    goods = toll_goods(world, player, town, toll)
    if goods is None:
        return []
    return [Event("lost_goods", (player, bandit), town, {"goods": goods, "mule": False, "reason": "toll"})]


@effect("lost_goods")
def _lost(world, event) -> None:
    player, taker = event.actors
    d = event.data
    mine, theirs = carried(world, player), dict(world.entity(taker).data.get("goods", {}))
    for good, n in d["goods"].items():
        mine[good] = mine.get(good, 0) - n
        theirs[good] = theirs.get(good, 0) + n
    changes = {"goods": {g: n for g, n in mine.items() if n > 0}}
    if d["mule"]:
        changes["mule"] = False
    world.update_data(player, **changes)
    world.update_data(taker, goods=theirs)
