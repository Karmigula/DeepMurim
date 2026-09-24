# DeepMurim Phase 4c: Trade

Date: 2026-09-23
Status: Draft, awaiting user review
Parent spec: `2026-09-22-deepmurim-design.md` (§5.7 living world and economy; §8 item 4)
Builds on: phase 4b (merged at `2a56ee9`): the world clock, lineage.

## 1. Goal

Every town has a market, and prices differ by region, town and circumstance. War raises the price of iron, famine the price of rice, spring festivals the price of wine. You carry goods between towns and profit from what you know. Your knowledge of prices comes only from where you have been and what you have heard, so rumours of a shortage are worth silver.

Every system:
- reports to the narrator in `Brief` facts plain enough for Haiku;
- adds rules to `debug/invariants.py`;
- is covered by the fuzz test.

### Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Phase split | 4c trade (this spec), 4d tournaments and secret realms. |
| Scope | Trade goods, and prices that react to events. |
| Approach | **Counted goods and known prices.** Goods are counts in your pack. Towns have markets with lazily computed prices. You know prices only from visits and rumours. |

## 2. Architecture

- **No save-format version change.** New keys:
  - player data: `goods` (`{good: count}`), `mule` (bool), `price_book` (`{town: {"time": t, "source": "visit"|"rumour", "prices": {good: price}}}`);
  - town data: `market` (`{good: [stock, day]}`, created on first use);
  - entity kind `price_event` (data `scope`: `"town"` or `"region"`, `place`, `multipliers` `{good: factor}`, `until`, `cause`);
  - facts `shortage` and `glut` (subject = the town, object = None, variant `good`).
- Prices are computed on demand, never stored per day.

### 2.1 New modules

| Module | Role |
|---|---|
| `systems/goods.py` | The goods table; region produce and lack; pack weight and capacity. |
| `systems/market.py` | Stock with recovery; the price formula; `buy_events`, `sell_events`, `mule_events`; the price book. |
| `systems/price_events.py` | War, famine, harvest, festival and faction-demand events: creation, expiry, multipliers, `shortage`/`glut` facts. |
| `engine/market.py` | `MarketMixin`: the market page and its buy/sell submenu, the `prices` page, the pack in the status line, a merchant's trade rumour. |
| `narrate/market_text.py`, `narrate/grammar/market.toml` | Outcome lines, journal summaries and grammar for every new event kind. |

## 3. Goods

| Good | Base price | Weight | Category |
|---|---|---|---|
| rice | 2 | 2 | staple |
| salt | 4 | 2 | staple |
| tea | 8 | 1 | luxury |
| wine | 10 | 2 | luxury |
| iron | 12 | 3 | war |
| herbs | 15 | 1 | medicine |
| silk | 30 | 1 | luxury |
| jade | 80 | 1 | luxury |

- **Regions.** Each region is seeded (`goods:{region seed path}`) to *produce* 2 goods (factor 0.6) and *lack* 2 others (factor 1.6).
- **Town kind.**
  - A city pays ×1.2 for luxuries.
  - A village sells staples ×0.9.
  - A town is ×1.0.
- **Pack.**
  - Capacity = `20 + 2 × strength` (the body's physique `strength`), plus 40 with a mule.
  - Weight = the sum of count × weight.
  - A mule costs 60 silver.

## 4. Prices

- **Price of a good in a town on a day:**
  `base × region factor × kind factor × event factor × stock factor × drift`.
  - The event factor is the product of every live `price_event` covering that town or its region, clamped to 0.3–4.0.
  - `stock factor = 1 / stock`.
  - `drift` is seeded uniform(0.95, 1.05) by `market:{town}:{good}:{day}`.
  - The result is rounded to a whole number, minimum 1.
- **Buying and selling.**
  - You buy at the price.
  - You sell at 90% of it (95% where the Merchant Guild keeps a hall), rounded down, minimum 1.
- **Stock.**
  - It starts at 1.0.
  - Buying n units: `stock -= 0.01 × n`. Selling n: `stock += 0.01 × n`. It is clamped to 0.1–3.0.
  - Each day since it was last touched, stock recovers 10% of the gap to 1.0. It is applied lazily when the market is read.
- **Limits.**
  - You cannot buy with more silver than you have, or beyond your pack's capacity.
  - You cannot buy when stock would fall below 0.1.
  - You cannot sell goods you don't carry.

## 5. What moves prices

Price events are entities with an `until` time. Expired events have no effect. They are created by listeners and by the world clock, and each writes a `shortage` or `glut` fact (weight 1.5) at its place.

| Event | Scope | Multipliers | Duration | Trigger |
|---|---|---|---|---|
| War | the clash's town | iron ×1.8, herbs ×1.5 (plus rice ×1.5 if a hall was lost) | 1 season | 4a `clash` with a place |
| War nearby | the clash's region | iron ×1.3 | 1 season | the same clash |
| Famine | a region | rice ×3, salt ×1.5 | 2 seasons | chance 0.03 per materialized region per season (world clock), seeded by `famine:{region}:{n}` |
| Famine nearby | each neighbouring materialized region | rice ×1.5 | 2 seasons | the same famine |
| Bumper harvest | a region | its produced goods ×0.6 | 1 season | chance 0.05 per materialized region per season |
| Festival | every city | wine ×1.4, silk ×1.4 | the spring season | computed from the calendar, not stored |
| Faction arming | a staffed faction's seat town | iron ×1.2 | while the faction's power is below 40 | computed from the faction, not stored |

- A `glut` fact is also written when the player sells 30 or more units of one good in one town on one day.
- Facts carry the good in their variant, so rumour text reads "Rice is dear in Crimson Town." or "Silk is going cheap in Jade Harbor."

## 6. Knowledge

- **Visiting.** Opening a town's market records every price there in the price book (`source: "visit"`).
- **Rumour.** When the player comes to believe a `shortage` or `glut` fact (the 3a `heard` event, or the 4a arrival news), the price book gains that town's price for that good at the time of the fact (`source: "rumour"`).
- **Asking a merchant.** "Ask about trade" gives one market rumour: the heaviest `shortage` or `glut` fact the merchant knows and the player doesn't.

## 7. Robbery and tolls

- **Robbery.** A duel verdict of `rob` against the player, or the robbery of a bandit encounter, also takes half of each good (rounded down). A mule is taken with chance 0.3.
- **Tolls.** A bandit's toll can be paid in goods worth at least the toll, at local prices. The goods of highest value per weight go first.

## 8. Screens

- **Market** ("Visit the market" in any town, or typed `market`). One line per good: price here, what you carry, and your last known price elsewhere with its town and age.
  - Its submenu offers buy or sell 1, 5 or 10 of each good (most valuable first, 9 shown), plus *Buy a mule*.
- **Price book** (typed `prices`). For each good, the best known selling price and where, and the best known buying price and where, each with its age in days and source.
- **Status line** shows `pack W/C` after the player's name while the pack is not empty.
- **Briefs.** A town's scene brief gains its cheapest and dearest good today. A merchant's brief gains their trade rumour.
- **Journal.** Summaries for trades worth 50 silver or more, and for losing a mule.

## 9. Debug rules

1. Goods counts are whole numbers, 0 or more. Pack weight never exceeds capacity.
2. Market stock stays within 0.1–3.0.
3. A price event's multipliers are within 0.3–4.0.
4. No price-book entry is later than now.

## 10. Testing

- **Unit tests:**
  - the price formula and each factor;
  - stock recovery;
  - every buy/sell limit;
  - the mule;
  - each price event's effect and expiry;
  - robbery and tolls in goods;
  - the price book from visits and from rumours;
  - a merchant's trade rumour.
- **Determinism:** the same seed gives the same prices on the same day.
- **Fuzz:** a trader who buys, sells and travels for 300 turns.
- **Speed:** the market page takes under 30 ms.
- **Old saves:** empty packs and price books; markets are created on first use.

## 11. Out of scope for 4c

- Crafting with goods, and goods as items with history (phase 5).
- NPC caravans as road encounters.
- Taxes and smuggling.
- Tournaments and secret realms (4d).
