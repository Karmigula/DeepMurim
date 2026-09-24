# Phase 4c: Trade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every town has a market whose prices depend on region, town, events and trading. The player carries goods between towns and profits from prices they have seen or heard of.

**Architecture:**
- **Goods** are counts in the player's data.
- **Prices** are computed on demand from:
  - a seeded regional profile;
  - town kind;
  - live price events;
  - lazily recovering market stock;
  - a seeded daily drift.
- **Price events** plug into the price formula through a registry, `market.EVENT_FACTORS`.
- **The price book** is the player's visits plus the `shortage` and `glut` facts they believe, read at the moment it is shown.
- **The engine** adds a market page with a two-level submenu (the goods, then buy or sell for one good), a `prices` page, and the pack in the status line.

| Area | System | Engine | Narration |
|---|---|---|---|
| goods and pack | `goods.py` | `MarketMixin` | `market_text.py` |
| markets and prices | `market.py` | `MarketMixin` | `market_text.py` |
| price events | `price_events.py` | — | `market_text.py` |

**Tech Stack:** Python 3.12, SQLite (save format v2, unchanged), pygame-ce, pytest.

**Spec:** `docs/superpowers/specs/2026-09-23-phase4c-trade-design.md`.

## Global Constraints

- No schema change. New keys:
  - player data `goods`, `mule`, `price_book`, `sold_today`;
  - town data `market`;
  - entity kind `price_event`;
  - facts `shortage` and `glut`.
- A day is 4 watches (`world.time // 4`).
- **Seeds:**
  - region goods `goods:{region seed path}`;
  - drift `market:{town}:{good}:{day}`;
  - famine `famine:{region}:{n}`;
  - harvest `harvest:{region}:{n}`;
  - a stolen mule `mule:{duel id}`.
- **Event kinds** must not reuse existing names. 4c's new kinds are `traded`, `bought_mule`, `price_shift` and `lost_goods`.
- **Narration.** Every new narrated event kind gets a grammar table, an outcome builder and a journal summary. World-committed events (`price_shift`) are not narrated.
- **Verbs** must not reuse an existing verb (`_do_<verb>` resolves by the MRO, so a clash silently shadows the older one). 4c trades with `buy_goods`/`sell_goods`, because 2b owns `buy`.
- A menu shows at most 9 choices, including Back.
- Test command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.

## Review Focus

1. **Selling more than the market wants.** A price never drops below 1, and stock never below 0.1. Task 1 pins this with `test_a_market_can_be_flooded_but_never_below_one`.
2. **A full pack.** Buying beyond capacity is refused with the reason. Task 1 pins this with `test_buying_is_refused_with_a_reason`.
3. **A robbery with an empty pack.** Nothing breaks, and nothing is taken. Task 4 pins this with `test_a_robbery_of_nothing_takes_nothing`.
4. **A save from before 4c.** An empty pack, an empty price book, and markets that appear on first visit. Task 3 pins this with `test_an_old_save_trades_from_scratch`.
5. **A famine and a war in one town.** The multipliers combine and are clamped to 0.3–4.0. Task 2 pins this with `test_price_events_stack_but_are_clamped`.

## Plan-time rulings (deviations from the spec, argued)

1. **Rumoured prices are read from beliefs when the price book is shown** (the facts carry the good and the price), rather than copied into `price_book` when heard. Nothing is missed by any path of learning (heard, arrival news, kin, witness). *Cost if wrong:* none.
2. **Buying a mule is offered in the town menu** ("Buy a mule (60 silver)") rather than inside the market submenu. The market submenu is the 8 goods plus Back, which fills the 9-choice menu exactly.
3. **A merchant's trade rumour reuses the 3a `heard` event.** The player comes to believe the fact the ordinary way. *Cost if wrong:* none.
4. **The 3b rule "no unheard faction named on screen" matches whole words.** It matched substrings, so "Wang Clan" was flagged inside "Hwang Clan"; the trader's fuzz run met such a pair. *Cost if wrong:* none.

---

### Task 1: Goods, markets, prices, buying and selling

**Files:**
- Create: `systems/goods.py`, `systems/market.py`, `narrate/market_text.py`, `narrate/grammar/market.toml`
- Modify (via `.patches/4c_task1.py`): `narrate/outcomes.py`
- Test: `tests/test_market.py`

**Interfaces:**
- Consumes: `systems.bodies.load_body`, `systems.purse.silver_of`, `systems.halls.halls_here`, `systems.factions`, `world.gen.materialize.region_of`.
- Produces:
  - `systems.goods`:
    - Constants: `GOODS = {good: (base, weight, category)}`, `ORDER` (goods by base price, highest first), `PRODUCED = 0.6`, `LACKED = 1.6`, `MULE_CAPACITY = 40`, `MULE_PRICE = 60`.
    - `region_goods(world, region) -> tuple[list[str], list[str]]` (produced, lacked).
    - `carried(world, person) -> dict[str, int]`, `pack_weight(goods: dict) -> int`, `capacity(world, person) -> int`.
  - `systems.market`:
    - Constants: `STOCK_STEP = 0.01`, `STOCK_MIN = 0.1`, `STOCK_MAX = 3.0`, `RECOVERY = 0.1`, `SELL_CUT = 0.9`, `GUILD_CUT = 0.95`.
    - Registry: `EVENT_FACTORS: list[Callable[[world, town, good], float]]`.
    - Pricing: `day(world) -> int`, `drift(world, town, good) -> float`, `stock(world, town, good) -> float`, `event_factor(world, town, good) -> float`, `price(world, town, good) -> int`, `sell_price(world, town, good) -> int`, `prices(world, town) -> dict[str, int]`.
    - Trading: `buy_block(world, player, town, good, n) -> str | None`, `sell_block(...) -> str | None`, `buy_events(world, player, town, good, n)`, `sell_events(...)`, `mule_block(world, player) -> str | None`, `mule_events(world, player, town)`.
    - Price book: `record_visit(world, player, town) -> None`.
  - Events: `traded` (player; data `good`, `n`, `side` = `buy` or `sell`, `unit`, `total`, `day`), `bought_mule` (player; data `price`).

- [ ] **Step 1: Write the failing test** — `tests/test_market.py`
```python
import pytest

import systems.encounters as encounters
import systems.goods as goods
import systems.market as market
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.gen.materialize import region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


@pytest.fixture
def still(monkeypatch):
    monkeypatch.setattr(market, "drift", lambda world, town, good: 1.0)


def rich(game, silver=5000):
    game.world.update_data(game.player.id, silver=silver)


def test_each_region_produces_two_goods_and_lacks_two(game):
    region = region_of(game.world, game.place.id)
    made, lacking = goods.region_goods(game.world, region)
    assert len(made) == len(lacking) == 2 and not set(made) & set(lacking)
    assert goods.region_goods(game.world, region) == (made, lacking)


def test_the_price_is_the_product_of_its_factors(game, still):
    town = game.place.id
    kind = game.world.entity(town).data["kind"]
    made, lacking = goods.region_goods(game.world, region_of(game.world, town))
    for good, (base, _, category) in goods.GOODS.items():
        region = goods.PRODUCED if good in made else goods.LACKED if good in lacking else 1.0
        kind_factor = 1.2 if kind == "city" and category == "luxury" else 0.9 if kind == "village" and category == "staple" else 1.0
        assert market.price(game.world, town, good) == max(1, round(base * region * kind_factor))


def test_buying_raises_the_price_and_the_market_recovers(game, still):
    rich(game)
    town, me = game.place.id, game.player.id
    before = market.price(game.world, town, "jade")
    game._commit(market.buy_events(game.world, me, town, "jade", 10))
    assert goods.carried(game.world, me) == {"jade": 10}
    assert market.stock(game.world, town, "jade") == pytest.approx(0.9)
    assert market.price(game.world, town, "jade") > before
    game.world.set_time(game.world.time + 4 * 30)
    assert market.stock(game.world, town, "jade") == pytest.approx(1 - 0.1 * 0.9 ** 30, abs=1e-6)


def test_selling_pays_less_than_buying(game, still):
    rich(game)
    town, me = game.place.id, game.player.id
    game._commit(market.buy_events(game.world, me, town, "silk", 5))
    silver = silver_of(game.world, me)
    unit = market.sell_price(game.world, town, "silk")
    game._commit(market.sell_events(game.world, me, town, "silk", 5))
    assert silver_of(game.world, me) == silver + 5 * unit
    assert unit < market.price(game.world, town, "silk") or unit == 1


def test_buying_is_refused_with_a_reason(game, still):
    town, me = game.place.id, game.player.id
    game.world.update_data(me, silver=0)
    assert market.buy_block(game.world, me, town, "rice", 1) == "You cannot afford that."
    rich(game)
    too_many = goods.capacity(game.world, me) // goods.GOODS["iron"][1] + 1
    assert market.buy_block(game.world, me, town, "iron", too_many) == "Your pack cannot hold that much."
    assert market.sell_block(game.world, me, town, "tea", 1) == "You have no tea to sell."


def test_a_market_can_be_flooded_but_never_below_one(game, still):
    rich(game, 10 ** 7)
    town, me = game.place.id, game.player.id
    game.world.update_data(me, goods={"rice": 400})
    for _ in range(4):
        game._commit(market.sell_events(game.world, me, town, "rice", 100))
    assert market.stock(game.world, town, "rice") == market.STOCK_MAX
    assert market.price(game.world, town, "rice") >= 1 and market.sell_price(game.world, town, "rice") >= 1
    game.world.update_data(me, goods={})
    while market.buy_block(game.world, me, town, "salt", 10) is None:
        game._commit(market.buy_events(game.world, me, town, "salt", 10))
        game.world.update_data(me, goods={})
    assert market.stock(game.world, town, "salt") >= market.STOCK_MIN


def test_a_mule_carries_more(game):
    me = game.player.id
    base = goods.capacity(game.world, me)
    game.world.update_data(me, silver=100)
    game._commit(market.mule_events(game.world, me, game.place.id))
    assert goods.capacity(game.world, me) == base + goods.MULE_CAPACITY and silver_of(game.world, me) == 40
    assert market.mule_block(game.world, me) == "You already have a mule."


def test_the_merchant_guild_pays_more(game, still):
    town = game.place.id
    guild = next(f for f in F.ensure_roster(game.world) if game.world.entity(f).data["type"] == "merchant_guild")
    plain = market.sell_price(game.world, town, "jade")
    game.world.update_data(town, halls=[*halls.halls_here(game.world, town), guild])
    assert market.sell_price(game.world, town, "jade") >= plain
    assert market.sell_price(game.world, town, "jade") == int(market.price(game.world, town, "jade") * market.GUILD_CUT)


def test_the_same_seed_gives_the_same_prices(game, tmp_path):
    twin = Game.new(tmp_path / "twin.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    twin.start()
    assert market.prices(game.world, game.place.id) == market.prices(twin.world, twin.place.id)
    twin.close()


def test_a_visit_writes_the_price_book(game):
    market.record_visit(game.world, game.player.id, game.place.id)
    entry = game.player.data["price_book"][str(game.place.id)]
    assert entry["source"] == "visit" and entry["prices"] == market.prices(game.world, game.place.id)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_market.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.goods'`.

- [ ] **Step 3: Write the goods** — `systems/goods.py`
```python
"""Trade goods (phase 4c spec 3): what exists, where it is made, and what a pack can hold."""

from systems.bodies import load_body
from world.seed import rng_for

GOODS = {  # good: (base price, weight, category)
    "rice": (2, 2, "staple"), "salt": (4, 2, "staple"), "tea": (8, 1, "luxury"), "wine": (10, 2, "luxury"),
    "iron": (12, 3, "war"), "herbs": (15, 1, "medicine"), "silk": (30, 1, "luxury"), "jade": (80, 1, "luxury"),
}
ORDER = tuple(sorted(GOODS, key=lambda g: (-GOODS[g][0], g)))
PRODUCED, LACKED = 0.6, 1.6
PACK_BASE, PACK_PER_STRENGTH = 20, 2
MULE_CAPACITY, MULE_PRICE = 40, 60


def region_goods(world, region) -> tuple[list[str], list[str]]:
    """The two goods a region makes cheaply and the two it lacks, seeded by the region."""
    picked = rng_for(world.world_seed, f"goods:{region.seed_path}").sample(sorted(GOODS), 4)
    return picked[:2], picked[2:]


def carried(world, person: int) -> dict[str, int]:
    return {g: int(n) for g, n in world.entity(person).data.get("goods", {}).items() if n}


def pack_weight(goods: dict) -> int:
    return sum(GOODS[g][1] * n for g, n in goods.items())


def capacity(world, person: int) -> int:
    strength = load_body(world, person).physique.get("strength", 10)
    mule = MULE_CAPACITY if world.entity(person).data.get("mule") else 0
    return int(PACK_BASE + PACK_PER_STRENGTH * strength) + mule
```

- [ ] **Step 4: Write the market** — `systems/market.py`
```python
"""Markets (phase 4c spec 4): prices computed on demand, stock that recovers, buying and selling.

price = base x region x town kind x events x (1 / stock) x drift, rounded, at least 1.
Stock is stored as [value, day] and recovers lazily toward 1.0 when read.
"""

from collections.abc import Callable

from systems import factions as F
from systems import halls
from systems.goods import GOODS, LACKED, MULE_PRICE, PRODUCED, capacity, carried, pack_weight, region_goods
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


def price(world, town: int, good: str) -> int:
    base = GOODS[good][0]
    value = base * _region_factor(world, town, good) * _kind_factor(world, town, good) \
        * event_factor(world, town, good) / stock(world, town, good) * drift(world, town, good)
    return max(1, round(value))


def _guild_here(world, town: int) -> bool:
    return any(world.entity(f).data["type"] == "merchant_guild" for f in halls.halls_here(world, town))


def sell_price(world, town: int, good: str) -> int:
    return max(1, int(price(world, town, good) * (GUILD_CUT if _guild_here(world, town) else SELL_CUT)))


def prices(world, town: int) -> dict[str, int]:
    return {good: price(world, town, good) for good in GOODS}


def buy_block(world, player: int, town: int, good: str, n: int) -> str | None:
    if good not in GOODS or n <= 0:
        return "There is no such trade."
    if silver_of(world, player) < price(world, town, good) * n:
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
    unit = price(world, town, good)
    return [Event("traded", (player,), town, {"good": good, "n": n, "side": "buy", "unit": unit, "total": unit * n,
                                             "day": day(world)})]


def sell_events(world, player: int, town: int, good: str, n: int) -> list[Event]:
    unit = sell_price(world, town, good)
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
```

- [ ] **Step 5: Write the narration** — `narrate/market_text.py`
```python
"""What the player is told about trade (phase 4c)."""

from narrate.outcomes import outcome, summary


@outcome("traded", body_facts=False)
def _traded(world, event):
    d = event.data
    verb = "buy" if d["side"] == "buy" else "sell"
    return [f"You {verb} {d['n']} {d['good']} for {d['total']} silver ({d['unit']} each)."], {}


@summary("traded")
def _traded_line(world, entry, names, place, other):
    d = entry.data
    return f"{'Bought' if d['side'] == 'buy' else 'Sold'} {d['n']} {d['good']} in {place} for {d['total']} silver."


@outcome("bought_mule", body_facts=False)
def _mule(world, event):
    return ["You buy a sturdy mule. It regards you without enthusiasm."], {}


@summary("bought_mule")
def _mule_line(world, entry, names, place, other):
    return f"Bought a mule in {place}."
```

- [ ] **Step 6: Write the grammar** — `narrate/grammar/market.toml`
```toml
[symbols]
market_noise = ["A vendor shouts over the crowd.", "Scales creak under the weight.", "Coins ring on a counter.", "Someone haggles loudly nearby.", "The smell of spice drifts past.", "A porter shoulders a load."]
market_mood = ["The deal is struck.", "Hands are shaken.", "The merchant nods, satisfied.", "You tie the bundle tight.", "It is a fair enough bargain.", "You count the silver twice."]

[traded]
colour = "default"
lines = ["#market_noise# #market_mood#", "#market_mood# #market_noise#"]

[bought_mule]
colour = "default"
lines = ["#market_noise# #market_mood#", "#market_mood# #market_noise#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/4c_task1.py`
```python
"""Task 1 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("narrate/outcomes.py", "import narrate.lineage_text  # noqa: E402,F401\n",
     "import narrate.lineage_text  # noqa: E402,F401\nimport narrate.market_text  # noqa: E402,F401\n")
print("task 1 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4c_task1.py && .venv/Scripts/python.exe -m pytest tests/test_market.py -q -p no:cacheprovider`
Expected: `task 1 edits applied`, then `10 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: markets - goods, regional prices, stock, buying, selling and mules"`

---
### Task 2: What moves prices: war, famine, harvest, festivals, arming, gluts

**Files:**
- Create: `systems/price_events.py`
- Modify (via `.patches/4c_task2.py`):
  - `world/db.py` (`entities_after`, so only live price events are read);
  - `systems/world_clock.py` (a season hook registry);
  - `narrate/gossip_text.py` (story shapes that need the good);
  - `narrate/market_text.py` (the phrases);
  - `narrate/outcomes.py`.
- Test: `tests/test_price_events.py`

**Interfaces:**
- Consumes: Task 1 (`market.EVENT_FACTORS`, `market.price`, `market.day`), 4a `wars` `clash` events, `world_clock.run_season`, `lives.SEASON`, `systems.time.season_of`, 3b `factions.STAFFED`.
- Produces:
  - `systems.price_events`:
    - Constants: `FAMINE_CHANCE = 0.03`, `HARVEST_CHANCE = 0.05`, `GLUT_UNITS = 30`, `FACT_WEIGHT = 1.5`, `ARMING_BELOW = 40`.
    - Shifts: `shift(world, scope, place, multipliers, until, cause, news=True) -> int` (the new `price_event` id; writes its facts), `live(world) -> list[Entity]`, `factor(world, town, good) -> float` (registered in `market.EVENT_FACTORS`).
    - Season hook: `season_events(world, n) -> list[Event]` (famine and harvest; registered in `world_clock.SEASON_HOOKS`).
  - `world_clock.SEASON_HOOKS: list[Callable[[world, n], list[Event]]]`, committed at the end of each season.
  - `narrate.gossip_text.SPECIAL_PHRASES: dict[predicate, Callable[[world, variant, viewer], str]]`.
  - Event: `price_shift` (actors `()`; data `scope`, `place`, `multipliers`, `until`, `cause`).
  - Facts: `shortage` and `glut` (subject = a town; variant `good`; fact data `good` and `price`).

- [ ] **Step 1: Write the failing test** — `tests/test_price_events.py`
```python
import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.market as market
import systems.price_events as price_events
import systems.world_clock as clock
from engine.game import Game
from narrate.gossip_text import rumour_text
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import ensure_town, region_of
from world.gen.region import region_spec


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(market, "drift", lambda world, town, good: 1.0)
    monkeypatch.setattr(price_events, "FAMINE_CHANCE", 0.0)
    monkeypatch.setattr(price_events, "HARVEST_CHANCE", 0.0)


def base(game, town, good):
    """The price with no events: every hook but the price events."""
    return market.price(game.world, town, good) / market.event_factor(game.world, town, good)


def test_a_clash_makes_iron_dear_there_and_nearby(game):
    town = game.place.id
    other = ensure_town(game.world, *[region_of(game.world, town).data[k] for k in ("x", "y")], 1) \
        if region_spec(game.world.world_seed, *[region_of(game.world, town).data[k] for k in ("x", "y")]).town_count > 1 else None
    a, b = F.ensure_roster(game.world)[:2]
    commit(game.world, [Event("clash", (a, b), town, {"season": 0, "hall_lost": False, "abstract": False})])
    assert market.event_factor(game.world, town, "iron") == pytest.approx(1.8 * 1.3)
    assert market.event_factor(game.world, town, "herbs") == pytest.approx(1.5)
    if other is not None:
        assert market.event_factor(game.world, other, "iron") == pytest.approx(1.3)
    [fact] = [f for f in game.world.facts(predicate="shortage", subject=town) if f.data["good"] == "iron"]
    assert fact.data["price"] == market.price(game.world, town, "iron")
    assert rumour_text(game.world, fact.variant, game.player.id) == f"Iron is dear in {game.world.entity(town).name}."
    game.world.set_time(game.world.time + lives.SEASON + 1)
    assert market.event_factor(game.world, town, "iron") == 1.0


def test_a_famine_empties_the_rice_barrels(game, monkeypatch):
    monkeypatch.setattr(price_events, "FAMINE_CHANCE", 1.0)
    town = game.place.id
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)
    assert market.event_factor(game.world, town, "rice") >= 3.0
    assert market.event_factor(game.world, town, "salt") >= 1.5


def test_a_bumper_harvest_makes_local_goods_cheap(game, monkeypatch):
    monkeypatch.setattr(price_events, "HARVEST_CHANCE", 1.0)
    from systems.goods import region_goods
    town = game.place.id
    made, _ = region_goods(game.world, region_of(game.world, town))
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)
    assert all(market.event_factor(game.world, town, g) == pytest.approx(0.6) for g in made)
    assert any(f.data["good"] in made for f in game.world.facts(predicate="glut"))


def a_city(game):
    for x in range(-4, 5):
        for y in range(-4, 5):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                town = ensure_town(game.world, x, y, i)
                if game.world.entity(town).data["kind"] == "city":
                    return town
    raise AssertionError("no city")


def test_cities_feast_in_spring(game):
    city = a_city(game)
    assert price_events.factor(game.world, city, "wine") == pytest.approx(1.4)  # the game begins in spring
    game.world.set_time(game.world.time + lives.SEASON)
    assert price_events.factor(game.world, city, "wine") == 1.0


def test_a_weak_faction_arms_itself(game):
    sect = next(f for f in F.ensure_roster(game.world) if game.world.entity(f).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    game.world.update_data(sect, power=90)
    strong = price_events.factor(game.world, seat, "iron")
    game.world.update_data(sect, power=20)
    assert price_events.factor(game.world, seat, "iron") == pytest.approx(strong * 1.2)


def test_price_events_stack_but_are_clamped(game):
    town = game.place.id
    until = game.world.time + lives.SEASON
    for _ in range(3):
        price_events.shift(game.world, "town", town, {"rice": 3.0}, until, "test")
    assert market.event_factor(game.world, town, "rice") == market.EVENT_MAX
    for _ in range(3):
        price_events.shift(game.world, "town", town, {"tea": 0.2}, until, "test")
    assert market.event_factor(game.world, town, "tea") == market.EVENT_MIN


def test_flooding_a_market_starts_a_rumour(game):
    town, me = game.place.id, game.player.id
    game.world.update_data(me, goods={"rice": 40})
    game._commit(market.sell_events(game.world, me, town, "rice", 30))
    [fact] = game.world.facts(predicate="glut", subject=town)
    assert fact.data["good"] == "rice"
    assert rumour_text(game.world, fact.variant, me) == f"Rice is going cheap in {game.world.entity(town).name}."
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_price_events.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.price_events'`.

- [ ] **Step 3: Write the price events** — `systems/price_events.py`
```python
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
```

- [ ] **Step 4: Edit the existing files** — `.patches/4c_task2.py`
```python
"""Task 2 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("world/db.py", '''    def entities(self, kind: str) -> list[Entity]:''', '''    def entities_after(self, kind: str, key: str, value) -> list[Entity]:
        """Entities of this kind whose data[key] is greater than `value` (phase 4c: live price events)."""
        rows = self._conn.execute(
            "select id, kind, name, seed_path, created_at, data from entities "
            f"where kind = ? and json_extract(data, '$.{key}') > ? order by id", (kind, value))
        return [_entity(row) for row in rows]

    def entities(self, kind: str) -> list[Entity]:''')
WC = "systems/world_clock.py"
edit(WC, '''MAX_WORLD_SEASONS = 8''', '''MAX_WORLD_SEASONS = 8
SEASON_HOOKS: list = []  # (world, n) -> list[Event]; later phases add their seasonal events (4c: famines)''')
edit(WC, '''        commit(world, founding_events(world, n))
        world.set_meta("world_tick", n)''', '''        commit(world, founding_events(world, n))
        for hook in SEASON_HOOKS:
            commit(world, hook(world, n))
        world.set_meta("world_tick", n)''')

GOSSIP = "narrate/gossip_text.py"
edit(GOSSIP, '''EXTRA_PHRASES = {"member_of": "{actor} {be} of the {target}."}''', '''EXTRA_PHRASES = {"member_of": "{actor} {be} of the {target}."}
# Story shapes that need more than actor and target (phase 4c: which good is dear or cheap).
SPECIAL_PHRASES: dict = {}''')
edit(GOSSIP, '''    predicate = variant.get("predicate")
    target = who(world, variant["target"], viewer) if variant.get("target") is not None else None
    if predicate == "is":''', '''    predicate = variant.get("predicate")
    if predicate in SPECIAL_PHRASES:
        return SPECIAL_PHRASES[predicate](world, variant, viewer)
    target = who(world, variant["target"], viewer) if variant.get("target") is not None else None
    if predicate == "is":''')

edit("narrate/market_text.py", '''from narrate.outcomes import outcome, summary
''', '''from narrate.gossip_text import SPECIAL_PHRASES
from narrate.outcomes import outcome, summary


def _market_story(world, variant, viewer) -> str:
    good = str(variant.get("good", "trade")).capitalize()
    where = variant.get("place") or "some town"
    if variant.get("predicate") == "shortage":
        return f"{good} is dear in {where}."
    return f"{good} is going cheap in {where}."


SPECIAL_PHRASES.update({"shortage": _market_story, "glut": _market_story})
''')
edit("narrate/outcomes.py", "import narrate.market_text  # noqa: E402,F401\n",
     "import narrate.market_text  # noqa: E402,F401\nimport systems.price_events  # noqa: E402,F401  (registers price events)\n")
print("task 2 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4c_task2.py && .venv/Scripts/python.exe -m pytest tests/test_price_events.py tests/test_market.py -q -p no:cacheprovider`
Expected: `task 2 edits applied`, then `17 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: price events - war, famine, harvest, festivals, arming and gluts move prices and start rumours"`

---
### Task 3: The market in the engine: page, price book, pack, merchant news, briefs

**Files:**
- Create: `engine/market.py`
- Modify (via `.patches/4c_task3.py`):
  - `systems/market.py` (`known_prices`, `town_line`);
  - `engine/game.py` (the `MarketMixin` base, help text);
  - `engine/commands.py` (`market`, `prices`);
  - `narrate/brief.py` (a town's cheapest and dearest goods).
- Test: `tests/test_market_engine.py`

**Interfaces:**
- Consumes: Tasks 1–2; 3a `rumours.heard_events`, `beliefs.knowledge_of`, `world.known_facts`.
- Produces:
  - `systems.market` (additions):
    - `known_prices(world, player) -> dict[int, dict]`: `{town: {"time", "source", "prices": {good: price}}}`, where visits and believed `shortage`/`glut` facts merge and the newer entry wins per good.
    - `town_line(world, town) -> str | None`: "Here jade is cheap and iron is dear."
  - `engine.market.MarketMixin`:
    - Verbs: `market`, `trade_good` (good), `buy_goods` ((good, n)), `sell_goods` ((good, n)), `buy_mule`, `prices`, `ask_trade`. (Not `buy`: 2b uses it for manuals.)
    - Submenus: `market` (the goods), `trade_good` (buy or sell 1, 5 or 10).
    - Hooks: `_status_suffix` ("pack W/C"), `_general_extras` (market, mule), `_conversation_extras` (a merchant's trade news).

- [ ] **Step 1: Write the failing test** — `tests/test_market_engine.py`
```python
import time

import pytest

import systems.encounters as encounters
import systems.market as market
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.goods import GOODS
from systems.price_events import shift
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def texts(turn):
    return [t for t, _ in turn.lines]


def test_the_market_page_lists_every_good_and_records_the_visit(game):
    turn = game.perform(Action("market"))
    lines = texts(turn)
    assert lines[0].startswith("Market of ")
    assert all(any(t.strip().startswith(good) for t in lines) for good in GOODS)
    assert [c.action.verb for c in turn.choices[:-1]] == ["trade_good"] * len(GOODS)
    assert str(game.place.id) in game.player.data["price_book"]


def test_trading_through_the_menus(game):
    game.world.update_data(game.player.id, silver=1000)
    game.perform(Action("market"))
    turn = game.perform(Action("trade_good", "silk"))
    assert Action("buy_goods", ("silk", 5)) in [c.action for c in turn.choices]
    game.perform(Action("buy_goods", ("silk", 5)))
    assert game.player.data["goods"] == {"silk": 5}
    turn = game.perform(Action("sell_goods", ("silk", 1)))
    assert game.player.data["goods"] == {"silk": 4}
    assert Action("sell_goods", ("silk", 1)) in [c.action for c in turn.choices]


def test_refusals_are_explained(game):
    game.world.update_data(game.player.id, silver=0)
    game.perform(Action("market"))
    game.perform(Action("trade_good", "jade"))
    assert texts(game.perform(Action("buy_goods", ("jade", 1))))[-1] == "You cannot afford that."


def test_the_price_book_mixes_visits_and_rumours(game):
    me = game.player.id
    game.perform(Action("market"))
    far = ensure_town(game.world, 5, 5, 0)
    shift(game.world, "town", far, {"iron": 3.0}, game.world.time + 360, "test")
    [fact] = [f for f in game.world.facts(predicate="shortage", subject=far)]
    believe(game.world, me, fact.id, fact.variant, None, 0.8, 2, "test")
    book = market.known_prices(game.world, me)
    assert book[far]["prices"]["iron"] == fact.data["price"] and book[far]["source"] == "rumour"
    lines = texts(game.perform(Action("prices")))
    name = game.world.entity(far).name
    assert any(t.strip().startswith("iron") and name in t and "heard" in t for t in lines)


def test_a_merchant_passes_on_trade_news(game):
    town, me = game.place.id, game.player.id
    shift(game.world, "town", town, {"salt": 2.0}, game.world.time + 360, "test")
    merchant = founding.make_person(game.world, "test:merchant", town, occupation="merchant")
    turn = game.perform(Action("talk", merchant))
    assert Action("ask_trade") in [c.action for c in turn.all_choices]
    game.perform(Action("ask_trade"))
    assert any(b.variant.get("predicate") == "shortage" for b in game.world.beliefs(me))


def test_the_status_line_shows_the_pack(game):
    game.world.update_data(game.player.id, goods={"silk": 3})
    assert "pack 3/" in game.perform(Action("look")).status


def test_a_mule_from_the_town_menu(game):
    game.world.update_data(game.player.id, silver=100)
    turn = game.perform(Action("look"))
    assert Action("buy_mule") in [c.action for c in turn.all_choices]
    game.perform(Action("buy_mule"))
    assert game.player.data["mule"]


def test_the_town_brief_names_its_cheap_and_dear_goods(game):
    game.world.set_time(game.world.time + 1)
    game.perform(Action("look"))
    facts = " ".join(game.last_briefs[-1].facts)
    assert "is cheap" in facts and "is dear" in facts


def test_an_old_save_trades_from_scratch(tmp_path):
    path = tmp_path / "old.world"
    old = Game.new(path, "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    old.start()
    old.world._conn.execute("update entities set data = json_remove(data, '$.goods', '$.price_book', '$.market')")
    old.close()
    game = Game.load(path)
    game.start()
    assert market.known_prices(game.world, game.player.id) == {}
    assert texts(game.perform(Action("market")))[0].startswith("Market of ")
    game.close()


def test_the_market_is_quick(game):
    start = time.perf_counter()
    game.perform(Action("market"))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.03, f"the market took {elapsed * 1000:.0f} ms"
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_market_engine.py -q -p no:cacheprovider`
Expected: failures such as `You can't do that (market).` in place of the market page.

- [ ] **Step 3: Write the mixin** — `engine/market.py`
```python
"""The market in the engine (phase 4c spec 8): a page, a two-level trade menu, the price book, merchant news."""

import systems.market as market
from engine.actions import Action, Choice
from systems.beliefs import knowledge_of
from systems.goods import GOODS, MULE_PRICE, ORDER, capacity, carried, pack_weight
from systems.rumours import heard_events

MARKET_MENUS = ("market", "trade_good")
AMOUNTS = (1, 5, 10)


class MarketMixin:
    _trade_good: str | None = None

    def _market_lines(self) -> list:
        world, me, town = self.world, self.player.id, self.place.id
        book = market.known_prices(world, me)
        pack = carried(world, me)
        lines = [(f"Market of {self.place.name} (pack {pack_weight(pack)}/{capacity(world, me)})", "heading")]
        for good in ORDER:
            here, sell = market.price(world, town, good), market.sell_price(world, town, good)
            elsewhere = [(entry["prices"][good], t, entry) for t, entry in book.items()
                         if t != town and good in entry["prices"]]
            note = ""
            if elsewhere:
                best, where, entry = max(elsewhere, key=lambda e: (e[0], -e[1]))
                days = max(0, (world.time - entry["time"]) // 4)
                note = f" | {best} in {world.entity(where).name}, {days}d ago"
            lines.append((f"  {good:<6} buy {here:>4}  sell {sell:>4}  carry {pack.get(good, 0):>3}{note}", "dim"))
        return lines

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is None and self.submenu in MARKET_MENUS:
            if self.submenu == "market":
                goods = [Choice(f"Trade {g} ({market.price(self.world, self.place.id, g)})", Action("trade_good", g))
                         for g in ORDER]
                options["market"] = (goods, Action("back"))
            else:
                good = self._trade_good
                trades = [Choice(f"Buy {n} {good}", Action("buy_goods", (good, n))) for n in AMOUNTS] \
                    + [Choice(f"Sell {n} {good}", Action("sell_goods", (good, n))) for n in AMOUNTS]
                options["trade_good"] = (trades, Action("market"))
        return options

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        extras.append(Choice("Visit the market", Action("market")))
        if market.mule_block(self.world, self.player.id) is None:
            extras.append(Choice(f"Buy a mule ({MULE_PRICE} silver)", Action("buy_mule")))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if npc.data.get("occupation") == "merchant":
            extras.append(Choice("Ask about trade", Action("ask_trade")))
        return extras

    def _status_suffix(self) -> str:
        suffix = super()._status_suffix()
        pack = carried(self.world, self.player.id)
        if not pack:
            return suffix
        return f"{suffix} pack {pack_weight(pack)}/{capacity(self.world, self.player.id)}"

    def _do_market(self, _target):
        market.record_visit(self.world, self.player.id, self.place.id)
        self.submenu = "market"
        return self._turn(self._market_lines())

    def _do_trade_good(self, good):
        if good not in GOODS:
            return self._turn([("There is no such good.", "system")])
        self._trade_good, self.submenu = good, "trade_good"
        buy, sell = market.price(self.world, self.place.id, good), market.sell_price(self.world, self.place.id, good)
        have = carried(self.world, self.player.id).get(good, 0)
        return self._turn([(f"{good.capitalize()}: buy at {buy}, sell at {sell}. You carry {have}.", "system")])

    def _trade(self, target, block, build):
        if not isinstance(target, (tuple, list)) or len(target) != 2:
            return self._turn([("There is no such trade.", "system")])
        good, n = target
        why = block(self.world, self.player.id, self.place.id, good, n)
        self._trade_good, self.submenu = good, "trade_good"
        if why is not None:
            return self._turn([(why, "system")])
        lines = self._commit(build(self.world, self.player.id, self.place.id, good, n))
        market.record_visit(self.world, self.player.id, self.place.id)
        self.submenu = "trade_good"
        return self._turn(lines)

    def _do_buy_goods(self, target):
        return self._trade(target, market.buy_block, market.buy_events)

    def _do_sell_goods(self, target):
        return self._trade(target, market.sell_block, market.sell_events)

    def _do_buy_mule(self, _target):
        if (why := market.mule_block(self.world, self.player.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(market.mule_events(self.world, self.player.id, self.place.id)))

    def _do_prices(self, _target):
        world, me = self.world, self.player.id
        book = market.known_prices(world, me)
        lines = [("Your price book", "heading")]
        if not book:
            return self._turn(lines + [("  You have seen no markets and heard no talk of trade.", "dim")])
        for good in ORDER:
            seen = [(entry["prices"][good], t, entry) for t, entry in book.items() if good in entry["prices"]]
            if not seen:
                continue
            low, high = min(seen, key=lambda e: (e[0], e[1])), max(seen, key=lambda e: (e[0], -e[1]))

            def where(e):
                how = "seen" if e[2]["source"] == "visit" else "heard"
                return f"{e[0]} in {world.entity(e[1]).name} ({how} {max(0, (world.time - e[2]['time']) // 4)}d ago)"
            lines.append((f"  {good:<6} cheapest {where(low)}; dearest {where(high)}", "dim"))
        return self._turn(lines)

    def _do_ask_trade(self, _target):
        npc = self.focus
        if npc is None or self.world.entity(npc).data.get("occupation") != "merchant":
            return self._turn([("Ask a merchant.", "system")])
        mine = {b.fact_id for b in self.world.beliefs(self.player.id)}
        news = [(b, f) for b, f in knowledge_of(self.world, npc)
                if f.predicate in ("shortage", "glut") and f.id not in mine]
        if not news:
            return self._turn([("They know of no trade worth telling.", "system")])
        belief, fact = max(news, key=lambda p: (p[1].weight, p[1].time, p[1].id))
        return self._turn(self._commit(heard_events(self.world, self.player.id, npc, self.place.id, belief, fact)))
```

- [ ] **Step 4: Edit the existing files** — `.patches/4c_task3.py`
```python
"""Task 3 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


Path("systems/market.py").write_text(Path("systems/market.py").read_text(encoding="utf-8") + '''

def known_prices(world, player: int) -> dict[int, dict]:
    """What the player knows of prices: their visits, and the shortages and gluts they believe (spec §6)."""
    book = {int(t): {"time": e["time"], "source": e["source"], "prices": dict(e["prices"])}
            for t, e in world.entity(player).data.get("price_book", {}).items()}
    for belief, fact in world.known_facts(player):
        if fact.predicate not in ("shortage", "glut") or fact.place is None or "good" not in fact.data:
            continue
        entry = book.setdefault(fact.place, {"time": fact.time, "source": "rumour", "prices": {}})
        if fact.data["good"] not in entry["prices"] or fact.time > entry["time"]:
            entry["prices"][fact.data["good"]] = fact.data["price"]
            if fact.time > entry["time"]:
                entry["time"], entry["source"] = fact.time, "rumour"
    return book


def town_line(world, town: int) -> str | None:
    """The good that is cheapest and the one that is dearest here today, for a brief (spec §8)."""
    ratios = {good: price(world, town, good) / GOODS[good][0] for good in GOODS}
    cheap, dear = min(ratios, key=lambda g: (ratios[g], g)), max(ratios, key=lambda g: (ratios[g], g))
    if cheap == dear:
        return None
    return f"Here {cheap} is cheap and {dear} is dear."
''', encoding="utf-8", newline="\n")

GAME = "engine/game.py"
edit(GAME, "from engine.lineage import LineageMixin\n", "from engine.lineage import LineageMixin\nfrom engine.market import MarketMixin\n")
edit(GAME, "class Game(LineageMixin, WorldMixin,", "class Game(LineageMixin, MarketMixin, WorldMixin,")
edit(GAME, '''ledger (F7) | lineage (F8)"''', '''ledger (F7) | lineage (F8) | market | prices"''')
edit("engine/commands.py", '''"lineage": Action("lineage"),''', '''"lineage": Action("lineage"), "market": Action("market"), "prices": Action("prices"),''')
edit("narrate/brief.py", '''    ancestors = player.data.get("ancestors") or []''', '''    from systems.market import town_line  # what is cheap and dear here (phase 4c)
    trade = town_line(world, place_id)
    if trade:
        facts.append(trade)
    ancestors = player.data.get("ancestors") or []''')
print("task 3 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4c_task3.py && .venv/Scripts/python.exe -m pytest tests/test_market_engine.py -q -p no:cacheprovider`
Expected: `task 3 edits applied`, then `10 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: the market in the engine - trading menus, the price book, the pack and merchant news"`

---
### Task 4: Robbery and tolls in goods

**Files:**
- Modify (via `.patches/4c_task4.py`):
  - `systems/market.py` (`robbery_events`, `toll_goods`, `toll_events`, the `lost_goods` event);
  - `engine/market.py` (`_after_duel`);
  - `engine/roads.py` (paying a toll in goods);
  - `narrate/market_text.py`, `narrate/grammar/market.toml`.
- Test: `tests/test_trade_losses.py`

**Interfaces:**
- Consumes: Tasks 1–3; 2b duel end data (`verdict`, `by`, `duel`); the 2b road encounter (`encounter["toll"]`, `_resolve`).
- Produces:
  - `systems.market` (additions):
    - Constant: `MULE_THEFT = 0.3`.
    - Robbery: `robbery_events(world, player, robber, place, duel_id) -> list[Event]` (nothing when there is nothing to take).
    - Tolls: `toll_goods(world, player, town, toll) -> dict | None` (goods worth at least the toll, most valuable per weight first), `toll_events(world, player, bandit, town, toll) -> list[Event]`.
  - Event `lost_goods` (player, taker; data `goods`, `mule`, `reason` = `robbed` or `toll`). It moves the goods to the taker.
  - Road verb: `road` with `pay_goods`.

- [ ] **Step 1: Write the failing test** — `tests/test_trade_losses.py`
```python
import random

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.market as market
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.goods import GOODS


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def robber(game):
    return founding.make_person(game.world, "test:robber", game.place.id, occupation="hunter", age=30,
                                traits=["greedy", "kind"])


def lose(game, npc):
    game._start_duel(npc, "duel")
    d = game.combat
    event = duel._end_event(game.world, d, "lost", "broken", random.Random(1), d.harm, 3)
    lines = game._commit([event])
    return lines + game._finish_duel(event.data)


def test_a_robber_takes_half_the_goods_and_maybe_the_mule(game, monkeypatch):
    monkeypatch.setattr(market, "MULE_THEFT", 1.0)
    me = game.player.id
    game.world.update_data(me, silver=50, goods={"silk": 5, "jade": 2}, mule=True)
    npc = robber(game)
    lines = lose(game, npc)
    assert game.player.data["goods"] == {"silk": 3, "jade": 1} and not game.player.data.get("mule")
    assert game.world.entity(npc).data["goods"] == {"silk": 2, "jade": 1}
    journal = [t for t, _ in game.perform(Action("journal")).lines]
    assert any("mule" in t for t in journal) and lines


def test_a_robbery_of_nothing_takes_nothing(game):
    game.world.update_data(game.player.id, silver=50, goods={"rice": 1})
    lose(game, robber(game))
    assert game.player.data["goods"] == {"rice": 1}
    assert not [e for e in game.world.chronicle_about(game.player.id, limit=20) if e.kind == "lost_goods"]


def bandit_on_the_road(game, toll):
    bandit = founding.make_person(game.world, "test:bandit", game.place.id, occupation="bandit", age=30)
    events = encounters.encounter_events(game.player.id, bandit, game.place.id, "bandit", toll)
    game._commit(events)
    game.encounter = encounters.encounter_state(events[-1])
    return bandit


def test_a_toll_can_be_paid_in_goods(game):
    me = game.player.id
    game.world.update_data(me, silver=0, goods={"jade": 3, "rice": 5})
    bandit = bandit_on_the_road(game, 60)
    turn = game.perform(Action("look"))
    assert Action("road", "pay_goods") in [c.action for c in turn.choices]
    game.perform(Action("road", "pay_goods"))
    taken = game.world.entity(bandit).data["goods"]
    worth = sum(market.sell_price(game.world, game.place.id, g) * n for g, n in taken.items())
    assert worth >= 60 and "jade" in taken and game.encounter is None


def test_no_goods_toll_when_the_pack_is_too_poor(game):
    game.world.update_data(game.player.id, silver=0, goods={"rice": 1})
    bandit_on_the_road(game, 500)
    assert Action("road", "pay_goods") not in [c.action for c in game.perform(Action("look")).choices]


def test_toll_goods_prefer_value_per_weight(game):
    game.world.update_data(game.player.id, goods={"jade": 1, "iron": 10})
    goods = market.toll_goods(game.world, game.player.id, game.place.id, 20)
    assert goods and next(iter(goods)) == max(goods, key=lambda g: GOODS[g][0] / GOODS[g][1])
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trade_losses.py -q -p no:cacheprovider`
Expected: failures, for example the goods are untouched after a robbery.

- [ ] **Step 3: Edit the existing files** — `.patches/4c_task4.py`
```python
"""Task 4 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


Path("systems/market.py").write_text(Path("systems/market.py").read_text(encoding="utf-8") + '''

MULE_THEFT = 0.3


def robbery_events(world, player: int, robber: int, place: int, duel_id) -> list[Event]:
    """A robber takes half of each good, and perhaps the mule (spec §7)."""
    taken = {g: n // 2 for g, n in carried(world, player).items() if n // 2}
    mule = bool(world.entity(player).data.get("mule")) \\
        and rng_for(world.world_seed, f"mule:{duel_id}").random() < MULE_THEFT
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
''', encoding="utf-8", newline="\n")

edit("engine/market.py", '''    def _do_market(self, _target):''', '''    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        if data.get("by") == "opponent" and data.get("verdict") == "rob" and self.combat is None:
            robber = self.world.entity(self.world.chronicle_entry(data.get("duel")).actors[1]) \\
                if self.world.chronicle_entry(data.get("duel")) else None
            if robber is not None:
                lines += self._commit(market.robbery_events(self.world, self.player.id, robber.id,
                                                            self.place.id, data.get("duel")))
        return lines

    def _do_market(self, _target):''')

ROADS = "engine/roads.py"
edit(ROADS, '''        if e["kind"] == "bandit":
            choices.append(Choice(f"Pay the toll ({e['toll']} silver)", Action("road", "pay")))''', '''        if e["kind"] == "bandit":
            choices.append(Choice(f"Pay the toll ({e['toll']} silver)", Action("road", "pay")))
            if silver_of(self.world, self.player.id) < e["toll"] \\
                    and market.toll_goods(self.world, self.player.id, self.place.id, e["toll"]) is not None:
                choices.append(Choice("Pay the toll in goods", Action("road", "pay_goods")))  # phase 4c''')
edit(ROADS, '''        if how == "talk":''', '''        if how == "pay_goods":
            events = market.toll_events(self.world, me, person, place, e["toll"]) if e["kind"] == "bandit" else []
            if not events:
                return self._turn([("You have nothing they would take.", "system")])
            return self._turn(self._commit(events) + self._resolve("paid"))
        if how == "talk":''')
text = Path(ROADS).read_text(encoding="utf-8")
if "import systems.market as market" not in text:
    text = text.replace("import systems.encounters as encounters\n", "import systems.encounters as encounters\nimport systems.market as market\n", 1)
Path(ROADS).write_text(text, encoding="utf-8", newline="\n")

edit("narrate/market_text.py", '''@outcome("bought_mule", body_facts=False)''', '''def _goods_words(goods: dict) -> str:
    return ", ".join(f"{n} {g}" for g, n in sorted(goods.items())) or "nothing"


@outcome("lost_goods", body_facts=False)
def _lost(world, event):
    d = event.data
    taker = world.entity(event.actors[1]).name
    mule = " and your mule" if d["mule"] else ""
    if d["reason"] == "toll":
        return [f"{taker} takes {_goods_words(d['goods'])} as the toll."], {}
    return [f"{taker} takes {_goods_words(d['goods'])}{mule} from your pack."], {}


@summary("lost_goods")
def _lost_line(world, entry, names, place, other):
    d = entry.data
    mule = " and a mule" if d.get("mule") else ""
    why = "as a toll to" if d.get("reason") == "toll" else "to"
    return f"Lost {_goods_words(d['goods'])}{mule} {why} {other}."


@outcome("bought_mule", body_facts=False)''')
Path("narrate/grammar/market.toml").write_text(Path("narrate/grammar/market.toml").read_text(encoding="utf-8") + '''
[lost_goods]
colour = "default"
lines = ["#market_loss# #market_noise#", "#market_noise# #market_loss#"]
''', encoding="utf-8", newline="\n")
edit("narrate/grammar/market.toml", '''market_mood = [''', '''market_loss = ["Your pack is lighter.", "You watch it go.", "There is nothing to be done.", "Hands rifle through your bundles.", "A strap is cut.", "Some things are not worth dying for."]
market_mood = [''')
print("task 4 edits applied")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4c_task4.py && .venv/Scripts/python.exe -m pytest tests/test_trade_losses.py -q -p no:cacheprovider`
Expected: `task 4 edits applied`, then `5 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 5: Commit**

Run: `git add -A && git commit -m "feat: robbers take goods and mules, and a toll can be paid in goods"`

---
### Task 5: Trade rules, a trader's fuzz run, docs

**Files:**
- Create: `tests/test_trade_rules.py`
- Modify (via `.patches/4c_task5.py`): `debug/invariants.py` (`check_trade`; faction names on screen match whole words), `tests/test_fuzz.py` (the trader), `docs/debugging.md`
- Test: `tests/test_trade_rules.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `debug.invariants.check_trade(world) -> list[str]`, called from `check_world`; the fuzz test `test_a_travelling_trader`.

- [ ] **Step 1: Write the failing test** — `tests/test_trade_rules.py`
```python
import pytest

import systems.encounters as encounters
import systems.market as market
from debug.invariants import check_trade
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice
from systems.price_events import shift


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def test_honest_trading_breaks_no_rule(game):
    game.world.update_data(game.player.id, silver=500)
    game.perform(Action("market"))
    game.perform(Action("trade_good", "silk"))
    game.perform(Action("buy_goods", ("silk", 5)))
    shift(game.world, "town", game.place.id, {"iron": 2.0}, game.world.time + 360, "test")
    assert check_trade(game.world) == []


def test_bad_goods_and_an_overfull_pack_are_caught(game):
    game.world.update_data(game.player.id, goods={"rice": -1})
    assert any("goods" in p for p in check_trade(game.world))
    game.world.update_data(game.player.id, goods={"iron": 999})
    assert any("pack" in p for p in check_trade(game.world))


def test_wild_stock_and_multipliers_are_caught(game):
    game.world.update_data(game.place.id, market={"rice": [9.0, 0]})
    assert any("stock" in p for p in check_trade(game.world))
    game.world.update_data(game.place.id, market={})
    shift(game.world, "town", game.place.id, {"rice": 9.0}, game.world.time + 360, "test")
    assert any("multiplier" in p for p in check_trade(game.world))


def test_a_name_inside_another_is_not_a_mention():
    from debug.invariants import mentions
    assert mentions("wang clan", "ha rinhwa the clan head (wang clan) (36)")
    assert not mentions("wang clan", "ha rinhwa the clan head (hwang clan) (36)")


def test_a_price_book_from_the_future_is_caught(game):
    market.record_visit(game.world, game.player.id, game.place.id)
    book = game.player.data["price_book"]
    book[str(game.place.id)]["time"] = game.world.time + 100
    game.world.update_data(game.player.id, price_book=book)
    assert any("price book" in p for p in check_trade(game.world))
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trade_rules.py -q -p no:cacheprovider`
Expected: the collection error `ImportError: cannot import name 'check_trade' from 'debug.invariants'`.

- [ ] **Step 3: Edit the rules, the fuzz test and the docs** — `.patches/4c_task5.py`
```python
"""Task 5 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


INV = "debug/invariants.py"
edit(INV, '''    problems += check_lineage(world)
''', '''    problems += check_lineage(world)
    problems += check_trade(world)
''')
edit(INV, '''def check_lineage(world) -> list[str]:''', '''def check_trade(world) -> list[str]:
    """Phase 4c spec 9: sane packs, markets, price events and price books."""
    from systems.goods import GOODS, capacity, pack_weight
    out = []
    player = world.get_meta("player_id")
    for person in world.entities("person"):
        goods = person.data.get("goods") or {}
        if any(g not in GOODS or not isinstance(n, int) or n < 0 for g, n in goods.items()):
            out.append(f"{person.name} (#{person.id}) carries impossible goods {goods}")
        elif person.id == player and not person.data.get("dead") and pack_weight(goods) > capacity(world, person.id):
            out.append(f"the player's pack weighs {pack_weight(goods)}, over its {capacity(world, person.id)}")
        book = person.data.get("price_book") or {}
        if any(entry.get("time", 0) > world.time for entry in book.values()):
            out.append(f"{person.name} (#{person.id}) has a price book entry from the future")
    for town in world.entities("town"):
        for good, (value, _) in (town.data.get("market") or {}).items():
            if not 0.1 - 1e-9 <= value <= 3.0 + 1e-9:
                out.append(f"{town.name} market stock of {good} is {value}")
    for event in world.entities_after("price_event", "until", world.time):
        if any(not 0.3 <= m <= 4.0 for m in event.data["multipliers"].values()):
            out.append(f"price event #{event.id} has a multiplier outside 0.3-4.0")
    return out


def check_lineage(world) -> list[str]:''')

edit(INV, '''        if faction.name.lower() not in heard_names and faction.name.lower() in text:''',
     '''        if faction.name.lower() not in heard_names and mentions(faction.name.lower(), text):''')
edit(INV, '''def check_trade(world) -> list[str]:''', '''def mentions(name: str, text: str) -> bool:
    """Whether `name` appears in `text` as whole words ("wang clan" is not in "hwang clan")."""
    return name in text and re.search(rf"(?<![\\w-]){re.escape(name)}(?![\\w-])", text) is not None


def check_trade(world) -> list[str]:''')
FUZZ = "tests/test_fuzz.py"
Path(FUZZ).write_text(Path(FUZZ).read_text(encoding="utf-8") + '''

@pytest.mark.parametrize("seed", [9, 31])
def test_a_travelling_trader(tmp_path, seed, monkeypatch):
    """Buying, selling and hauling between towns, robbed now and then: every trade rule holds."""
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 1.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Trader{seed}", world_seed=seed)
    app.game.world.update_data(app.game.player.id, silver=2000)
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3", "4"]))
        elif game.submenu in ("market", "trade_good") and app.choices:
            app.submit(str(rng.randint(1, len(app.choices))))
        else:
            app.submit(rng.choice(["market", "market", "prices", "go north", "go east", "go south", "go west",
                                   "look", "meditate week", "1", "2", "3"]))
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()
''', encoding="utf-8", newline="\n")

edit("docs/debugging.md", '''- **Lineage (phase 4b):**''', '''- **Trade (phase 4c):** goods are whole counts of known goods and the player's pack never exceeds its capacity; market stock stays within 0.1-3.0; a live price event's multipliers stay within 0.3-4.0; no price book entry comes from the future. The fuzz run `test_a_travelling_trader` hauls goods for 300 turns.
- **Lineage (phase 4b):**''')
print("task 5 edits applied")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4c_task5.py && .venv/Scripts/python.exe -m pytest tests/test_trade_rules.py -q -p no:cacheprovider`
Expected: `task 5 edits applied`, then `5 passed`.

Run: `.venv/Scripts/python.exe -m pytest tests/test_fuzz.py -q -p no:cacheprovider`
Expected: every fuzz test passes, including `test_a_travelling_trader[9]` and `[31]`. Treat any rule violation as a bug and find its cause with systematic debugging. Do not loosen the rule.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 5: Commit**

Run: `git add -A && git commit -m "test: trade rules, a travelling trader, docs"`

---

## Self-review

**Spec coverage:**

| Spec section | Where it is built |
|---|---|
| §3 goods, regions, pack | Task 1 |
| §4 prices, stock, limits | Task 1 |
| §5 what moves prices | Task 2 |
| §6 knowledge | Task 1 (visits), Task 3 (rumours through beliefs; merchants) |
| §7 robbery and tolls | Task 4 |
| §8 screens | Task 3 (market, prices, status, briefs), Tasks 1 and 4 (journal) |
| §9 debug rules | Task 5 |
| §10 testing | every task; fuzz in Task 5 |

**Differences from the spec:** the plan-time rulings 1–3 above.

**Type consistency:**
- `market.price`, `sell_price`, `buy_events` and `sell_events` all take `(world, player?, town, good, n?)`, in the order given in Task 1.
- `price_events.shift(world, scope, place, multipliers, until, cause, news=True)`.
- Engine buy and sell targets are `(good, n)` tuples.

**Dry run** (the whole plan on a scratch copy of `935d652`: 654 passed, plus the 500-year soak deselected). It found and fixed:
- **Soak speed.** Centuries of expired price events made each world season slow (377 ms). Live events now come from the database (`World.entities_after`), and a region's towns are found through its relations.
- **One rumour per war.** The town shift comes last, so its rumour carries the full price.
- **A verb clash.** `buy` belonged to 2b's manual trade, so the market uses `buy_goods` and `sell_goods`.
- **Whole-word faction names** in the name-on-screen rule (ruling 4).
