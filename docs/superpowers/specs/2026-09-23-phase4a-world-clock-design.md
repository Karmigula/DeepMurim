# DeepMurim Phase 4a: The World Clock

Date: 2026-09-23
Status: Draft, awaiting user review
Parent spec: `2026-09-22-deepmurim-design.md` (§4.3 time and level of detail, §5.7 agendas; §8 item 4)
Builds on: phase 3 (merged at `322ed1b`): rumours and knowledge, factions, founding.

## 1. Goal

The world lives without you. People age, cultivate, marry, have children, move, take apprentices, settle scores with each other and die. Factions grow and shrink, feud, win and lose halls, replace dead leaders and sometimes perish. You learn of it the way you learn anything: by being there, or by rumour. Returning to a town after years shows a changed place, and the change is recorded, so nothing is forgotten.

Every system:
- reports to the narrator in `Brief` facts plain enough for Haiku;
- adds rules to `debug/invariants.py`;
- is covered by the fuzz test.

### Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Phase split | 4a world clock (this spec), 4b lineage (player death, heirs), 4c economy and scheduled world events. |
| World life | All four: people age and die, people rise, factions clash, people move and scheme. |
| Approach | **Hybrid.** Factions tick globally each season. People catch up lazily when you next meet or hear of them. |

## 2. Architecture

### 2.1 Two clocks

| Clock | Scope | Trigger | Seed |
|---|---|---|---|
| **Faction clock** | Every materialized faction except `player_sect`, in id order | Player time crosses a season boundary. At most `MAX_WORLD_SEASONS = 8` seasons per turn; the rest wait for the next turns. | `world:{season}` for the season, `world:{season}:{faction}` per faction |
| **Life clock** | One materialized person | The person is observed (§7.1) and their `lived_to` is behind the current season | `life:{person}:{season}`; coarse years `life:{person}:year:{y}` |

- A season is 360 watches (`SEASON` in `systems/time.py`, the 3c value). Season number `n = time // 360`.
- The world stores `world_tick` (the last season the faction clock ran) in world meta. Each person stores `lived_to` (a season number) in their data.
- Unmaterialized people and places are never simulated. A person materialized now starts with `lived_to` = the current season.

### 2.2 Interactions between people

When A's season targets B (a revenge, a marriage, taking B as an apprentice), B is first caught up **passively** to the same season: aging, cultivation and the death roll only, no agendas and no families. Then the interaction resolves against B's state. Passive catch-up never triggers further catch-ups, so the recursion is one level deep and the result is deterministic for a given order of observation.

### 2.3 Everything becomes story

Every notable change is committed as a chronicle event plus a fact with a subject, a predicate, an object, a place and a weight. The 3a rumour system spreads it by distance and mutates it. The player never reads ground truth: scene lines, briefs and the Rumours page show only what the player believes.

| Change | Event / fact | Weight |
|---|---|---|
| Death of age or illness | `died` (victim as both actors) / `died` | 1.0 (2.0 if Second-rate or higher, or faction staff) |
| Killed in a feud or a clash | `died` with killer / `killed` | 2.0 |
| Breakthrough to Second-rate or higher | `broke_through` / `broke_through` | 1.0 + 0.5 per realm above Second-rate |
| Promotion to elder or leader | `promoted` / `promoted` | 1.5 (leader 2.0) |
| Marriage | `married` / `married` | 1.0 |
| Birth | `born` / `born` | 0.5 |
| Moved town | `moved` / `moved` | 0.5 |
| Took an apprentice | `apprenticed` / `apprenticed` | 0.5 |
| Faction clash | `clash` / `clashed_with` | 1.5 |
| Hall lost | `hall_lost` / `lost_hall` | 2.0 |
| Minor faction founded / destroyed | `faction_founded` / `faction_destroyed` | 2.0 / 2.5 |

### 2.4 New modules

| Module | Role |
|---|---|
| `systems/world_clock.py` | The faction clock: `due_seasons`, `faction_season_events`, power, stance drift, succession, staffing, minors. |
| `systems/wars.py` | Clashes between hostile factions: where, who wins, losses, halls. |
| `systems/lives.py` | The life clock: `live_events(world, person, until)`, passive catch-up, coarse mode, aging, lifespan, cultivation, death. |
| `systems/agendas.py` | Marriage, births, moving, revenge between NPCs, apprentices. |
| `engine/world_mixin.py` | `WorldMixin`: runs the faction clock after time advances, catches up people on arrival and observation, the "much has changed" scene line. |
| `narrate/world_text.py`, `narrate/grammar/world.toml` | Outcome lines and grammar for every new event kind. |

No save-format version change. New keys: world meta `world_tick`; person data `lived_to`, `born_at` (time), `age` (existing, now a float); kin role `spouse`.

## 3. The faction clock

Runs once per due season for every materialized faction that is not `player_sect` and not dissolved, in id order. Each faction's rolls use `rng_for(world_seed, f"world:{n}:{faction}")`.

### 3.1 Power

- `power` stays 0–100.
- Target = `20 + 10 × (mean realm index of its living staff) + 5 × (number of halls)`, clamped to 0–100.
- Each season: `power += 0.2 × (target − power) + uniform(−3, 3)`, rounded, clamped to 0–100.

### 3.2 Clashes

- For each unordered pair (a, b) with `stance(a, b) ≤ −0.5`, handled once per season from the lower id: a clash happens with chance 0.2, or 0.4 when `stance ≤ −0.8`.
- **Where:** a materialized town where both have a hall (lowest id). If there is none, the fight is abstract and placed at the weaker side's seat.
- **Winner:** a wins with chance `power_a / (power_a + power_b)`.
- **The loser** loses 5 power. With chance 0.3, one of the loser's staff in that town (or at the seat, if abstract; never the leader of a great faction) is killed by a winner's staff member present there or at the winner's seat. It is a real `died` event with a killer, so kin grieve and the 3a avenger rules apply.
- If the loser has a branch hall (not its seat) in that town, it loses it with chance 0.5. The town's `halls` drops the faction, and its staff there move to its seat.
- Every clash moves both stances by −0.05 (min −1.0). A pair that did not clash this season drifts +0.02 toward its `base_stance` (never past it).

### 3.3 Succession and staffing

- A faction whose leader is dead or gone gets a new one: the living elder with the highest realm (ties by lowest id). With no elder, the highest-realm keeper, then disciple. The new leader gets rank 4 and role `leader`.
- Empty elder slots are filled the same way from keepers, then disciples.
- Empty staff slots at each hall (per the 3b `SEAT_STAFF`, `BRANCH_STAFF` and `CAPITAL_STAFF` tables) are filled by seeded recruits made at that town, with path `world:{faction}:recruit:{n}:{i}`.
- Each promotion is a `promoted` event.

### 3.4 Minor factions

- A minor faction whose power is below 15 is destroyed. It gets `dissolved = true`, every member is `released`, its hall and seat leave their town's lists, and a `faction_destroyed` fact is written.
- Each materialized region has a chance of 0.02 per season to found a new minor faction (a school or a bandit fort, chosen by the region's seed) in a materialized town of that region that has no minor faction. It is made with the 3b minor generator and staffed at once.
- Great factions are never destroyed in 4a.

### 3.5 Not in the faction clock

- The player's own sect (3c seasons handle it; hostile factions reach it through gate events).
- Prices and scheduled events (4c).

## 4. The life clock

`live_events(world, person, until_season)` returns the events for every season from `lived_to + 1` to `until_season`. The engine commits them season by season, and a person's season sees the world as the previous season left it.

### 4.1 Aging and death

- Age goes up 0.25 each season.
- Lifespan by realm: Mortal 70, Third-rate 80, Second-rate 95, First-rate 120, Peak 150, Transcendent 200, Profound 300, Life-and-Death 500.
- Death chance per season: `0.001` always. From `lifespan − 10`, add `0.02`. Past `lifespan`, add `0.02 × (age − lifespan)`.
- A natural death is a `died` event with the victim as both actors and `cause: "age"` or `"illness"`. Kin grieve and inherit grudges (3a). A dead faction member leaves their membership (status `dead`).
- The player is not aged by the life clock in 4a (4b owns the player's lifespan).

### 4.2 Rise

- A person is **martial** if they are faction staff, above Mortal, or have a fighting occupation (the 3b `FAVOURED` occupations plus `wandering swordsman`).
- Martial people gain `0.25 × talent` energy years each season with `realms.add_energy`. `talent` is seeded by seed path (`talent:{seed_path or id}`, 0.5–1.5).
- At a bottleneck they break through with `breakthrough_chance(body, True)`. A breakthrough to Second-rate or higher is a `broke_through` event.
- Commoners do not cultivate.

### 4.3 Families

- New kin role `spouse` (its own inverse). A person has at most one living spouse.
- **Marriage:** an unmarried living adult aged 18–50 marries with chance 0.03 per season. The partner is the unmarried adult in the same town with the lowest id who is not their kin. If there is none, a seeded newcomer (`life:{person}:spouse:{n}`) moves in. Both get `spouse` kin.
- **Birth:** a married couple where either partner is aged 18–45 has a child with chance 0.08 per season, rolled by the lower-id partner only. The child is age 0 and located with the parents, with `parent`/`child` kin to both and `sibling` kin to the couple's other children.
- **Cap:** no births in a town whose living population is at least `1.5 × npc_count` (staff excluded).
- A widowed spouse may remarry.

### 4.4 Agendas

- **Move:** with chance 0.03 per season, to a materialized town within 1 region (lowest id first, chosen by the season's rng). Never for staff, children under 16, or anyone with a living spouse or children in their town. It is a `moved` event.
- **Revenge between NPCs:** a person holding a `wronged` or `hatred` memory (3a) about another living NPC acts with chance 0.1 per season.
  - The target is caught up passively first.
  - The winner is decided by realm gap: `chance = 0.5 + 0.15 × (realm_a − realm_b)`, clamped to 0.1–0.9.
  - The loser takes a torso injury, and dies with chance 0.2. That death is a `died` event with a real killer and a `killed` fact, so the victim's kin gain grudges and vendettas chain.
  - An acted-on memory is not acted on again for 4 seasons.
- **Apprentice:** a living person at Second-rate or higher with no living disciple takes a local person aged 12–20 who has no master, with chance 0.05 per season. They get `master`/`disciple` kin.
- NPCs do not target the player through agendas in 4a (the 3a avenger rules already do).

### 4.5 Level of detail

- The first 40 missed seasons run in full, as above.
- Any seasons beyond the most recent 40 run first, in **coarse mode**: one step per year, seeded by `life:{person}:year:{y}`. A step covers age +1, energy `1.0 × talent` for martial people with one breakthrough roll, and one death roll at 4 × the season chance. No agendas and no families.
- Coarse deaths are `died` events like any other.

## 5. Children

- A child under 12 shows as "a child of X" in people lists. They cannot be challenged, recruited, invited, asked to follow or robbed.
- At 16 a child picks an occupation from their seed: a parent's occupation with chance 0.5, otherwise a seeded one.

## 6. Save compatibility

- On first load of an older save, `world_tick` is set to the current season.
- Every existing person gets `lived_to` = the current season, so nobody ages retroactively.
- Existing integer ages stay as they are and become floats as seasons pass.

## 7. What the player sees

### 7.1 Catch-up triggers

- **Arrival** in a town: everyone located there catches up.
- **Talking** to someone catches them up.
- **Hearing news** about someone (3a `heard`) catches up its subject.
- **Opening** a person's brief, the people list, or the standing page catches up the people shown.
- **Time passing:** after each action that advances time, the faction clock runs due seasons (at most 8 per turn).

### 7.2 Screens

- **Arriving somewhere:** after catch-up, one scene line lists at most 3 changes at that town that the player believes, learned since their last visit. For example: "Much has changed: old Wang died; Hu Mei married Chen Bo; the Iron Fist School lost its hall here." Nothing new, no line.
- **People list and portraits** show the current age in years.
- **Briefs:** a person's brief gains their age and one family line, for example "Wife of Chen Bo, mother of two." The town brief gains the newest believed change there.
- **Rumours page:** world news appears there with the 3a distance and mutation rules. There is no new page.
- **Journal:** the death of someone the player had met is added as "Heard: X died" when the player learns it.
- **Long seclusion:** after a time skip of a season or more, the log says "The world moved on: N seasons pass."

## 8. Debug rules

1. `world_tick` ≤ the current season, and every person's `lived_to` ≤ the current season.
2. A living person's age never decreases (checked against the previous turn's snapshot of observed people).
3. The dead have no living `spouse` link and no membership with status `member`.
4. `spouse` kin is symmetric, and a living person has at most one living spouse.
5. Every faction that is not dissolved and not `player_sect` has exactly one living leader. The number of staff at each of its halls matches its hall table after the faction clock runs.
6. Every `born` event records the town's living population (staff excluded) just before the birth, and it is below `1.5 × npc_count`.
7. A child under 12 is never faction staff, a sect member, a sworn follower or anyone's master.

## 9. Testing

- **Unit tests** per module: power drift, clash odds and losses, hall loss, succession, staffing, minor founding and destruction, aging and lifespan, cultivation, marriage, births and the cap, moving, revenge chains, apprentices, coarse mode.
- **Determinism:** catching up one person over 8 seasons in one call matches 8 single-season calls. The faction clock gives the same world for the same seeds.
- **Soak:** 200 in-game years headless on one world, with the faction clock running and random towns visited every 5 years. No exceptions, every debug rule holds, all great factions still exist, and the database stays under a fixed bound. A 500-year run exists behind the `slow` marker.
- **Fuzz:** a long-lived wanderer who takes seasonal seclusions and travels.
- **Speed:**
  - One faction season takes under 30 ms.
  - Arriving in a town of 30 people 8 seasons later takes under 150 ms.
  - One person 100 years stale takes under 20 ms.

## 10. Out of scope for 4a

- The player's own aging, death, heirs and inheritance (4b).
- Prices, trade, tournaments, secret realms and succession crises (4c).
- Wars against the player's sect beyond 3c gate events.
- NPCs travelling on the road as encounters.
