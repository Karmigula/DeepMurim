# DeepMurim Phase 4d: World Events, Heavenly Phenomena and Rankings

Date: 2026-09-24
Status: Draft, awaiting user review
Parent spec: `2026-09-22-deepmurim-design.md` (§5.7 scheduled world events)
Builds on: phase 4c (merged, master at `df07505`): trade, the world clock, lineage.

## 1. Goal

The sky and the Murim both keep a calendar. Comets foretell war, blood moons wake demonic arts, qi tides speed cultivation, and lightning marks every great breakthrough. A treasure's light draws champions from every sect. Once a year the Heavenly Ranking Pavilion publishes who stands where under heaven, from what it has heard.

This phase is the **template for forks**. It builds:
- the world-event framework that 4e (tournaments), 4f (secret realms) and 4g (succession crises) build on;
- eight heavenly phenomena as worked examples of the framework;
- the rankings that every later event feeds.

Every system:
- reports to the narrator in `Brief` facts plain enough for Haiku;
- adds rules to `debug/invariants.py`;
- is covered by the fuzz test.

### Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Phase split | 4d framework + phenomena + rankings (this spec), 4e tournaments, 4f secret realms, 4g succession crises. |
| Depth | A deep, genre-faithful treatment: this RPG is the template for future forks. |
| Framework | **TOML types + Python stages.** Event types are TOML entries; each has a Python module with stage hooks. Occurrences are `world_event` entities advanced by the clock. |
| Phenomena | Tribulation lightning, qi tide, blood moon, comet omen, treasure light, beast tide, dao resonance, star fall. |
| Rankings | **A publisher's knowledge.** The Heavenly Ranking Pavilion ranks from what it believes, not from truth. |

## 2. Architecture

- **No save-format version change.** New:
  - entity kinds `world_event` and `institution`;
  - event kinds `world_event_stage`, `tribulation`, `treasure_claimed`, `rankings_published`;
  - fact predicates `phenomenon`, `tribulation`, `treasure`, `ranked`;
  - an `entities(kind)` index already exists (4c review).
- Stages are **computed from time**, like 4c stock. The first observation of a stage commits one `world_event_stage` event, and the type's module reacts to it.
- Occurrences are history: never deleted, only marked `over`.

### 2.1 New modules

| Module | Role |
|---|---|
| `systems/world_events.py` | The framework: loading types, scheduling, stages, `factor()`, news, `sky_line`. |
| `systems/data/world_events.toml` | The eight event types. |
| `systems/events/<type>.py` | One module per type: stage hooks and special rules. |
| `systems/rankings.py` | The Pavilion, its informants, scoring, the yearly revision, known lists. |
| `systems/races.py` | Treasure races (treasure light, star fall): champions, the contest, the claim. |
| `engine/sky.py` | `SkyMixin`: `sky`, `rankings`, `seek`, the tribulation scene, sheet and journal lines. |
| `engine/rankings_page.py` | The F9 rankings page. |
| `narrate/sky_text.py`, `narrate/grammar/sky.toml` | Narration for stages, tribulations, claims and lists. |

## 3. The framework

### 3.1 Event types (TOML)

```toml
[qi_tide]
module = "systems.events.qi_tide"
scope = "region"                 # world | region | town | site
cycle = "season"                 # "season": rolled each world season; "trigger": started by a listener
chance = 0.04                    # per eligible place per season
stages = { foretold = 0, announced = 10, active = 90, aftermath = 20 }   # days; 0 skips the stage
modifiers = { cultivation = 1.5, breakthrough = 1.2 }                     # while active
news = { predicate = "phenomenon", weight = 1.2 }
```

- Stage order is fixed: `foretold → announced → active → aftermath → over`.
- A type module may define `on_stage(world, occurrence, stage) -> list[Event]`, `eligible(world, place, n) -> bool` and `start_data(world, place, n, rng) -> dict`. All three are optional.
- **A fork adds an event by adding one TOML entry and one module.** No engine edit is needed.

### 3.2 Occurrences

- A `world_event` entity with data:
  - `type`, `scope`, `place`;
  - `starts`, the end time of each stage (`stage_ends`);
  - `seen` (the stages already committed);
  - `over`;
  - `data` (the module's own).
- `stage(world, occurrence)` is computed from `world.time`.
- `observe(world, place)` commits a `world_event_stage` event for each stage reached but not yet in `seen`, in order. It runs:
  - at every world season (`SEASON_HOOKS`);
  - on arrival and on each scene.
- `live(world)` returns the occurrences not yet over, cached per time.

### 3.3 Scheduling

- A `SEASON_HOOKS` entry rolls `cycle = "season"` types for season n.
- The roll is seeded by `rng_for(seed, f"sky:{type}:{place.seed_path}:{n}")`.
- Dates count from season n (`n * SEASON`). An occurrence whose whole span ends before now is not created (the 4c catch-up lesson).
- There is at most one live occurrence per type per place.
- Trigger types are started by listeners (§4.1).

### 3.4 Modifiers

- `factor(world, place, key)` is the product of `modifiers[key]` over the live, active occurrences covering the place. It is clamped to **0.25–4.0** and cached per time.
- Covering follows scope:
  - `world`: everywhere;
  - `region`: every town in the region;
  - `town`: that town;
  - `site`: that town.
- Keys read by existing systems:

| Key | Read by |
|---|---|
| `cultivation` | `cultivation.energy_rate` (player) and the life clock's growth (NPCs) |
| `breakthrough` | breakthrough chance, player and NPC |
| `encounter` | road encounter chance (`beasts_only` types scale beasts only) |
| `clash` | faction clash chance (`wars.CLASH_CHANCE`) |
| `demonic` | the combat weight of unorthodox and demonic arts |
| `practice` | technique practice and learning progress |

- Price effects go through 4c `market.EVENT_FACTORS` as `prices = { rice = 1.3 }` in the TOML.

### 3.5 News

- When a stage is committed, a `phenomenon` fact is recorded if the TOML asks for news. Its variant carries the kind, the stage and a **reading**: the town's superstitious interpretation, seeded per town from the type's `readings` list.
- The fact spreads through 3a rumours.
- `sky_line(world, place)` gives the scene brief's sentence (§7.1).

## 4. The eight phenomena

| Type | Scope | Cycle | Stages (days) | Effects |
|---|---|---|---|---|
| Tribulation lightning | town | trigger | active 1 | §4.1 |
| Qi tide | region | season, 0.04 | announced 10, active 90, aftermath 20 | `cultivation ×1.5`, `breakthrough ×1.2` |
| Blood moon | world | season, 0.03 | foretold 5, active 10 | `demonic ×1.3`, `encounter ×1.5`; righteous members challenge bandits more |
| Comet omen | world | season, 0.02 | foretold 30, active 90 | `clash ×1.5`; `prices` salt ×1.3, rice ×1.3; readings differ by town |
| Treasure light | site | season, 0.03 | announced 5, active 20 | a race (§5) |
| Beast tide | region | season, 0.03 | announced 5, active 15, aftermath 30 | `encounter ×3` (beasts only); town attacks, herbs ×1.5, magistrate bounty |
| Dao resonance | town | season, 0.01 | active 5 | `practice ×2`; names the master |
| Star fall | site | season, 0.01 | announced 3, active 30 | a race (§5); the prize is star iron |

### 4.1 Tribulation lightning
- **Trigger:**
  - the player's `breakthrough` into realm index 3 (First-rate) or higher;
  - an NPC's `broke_through` to the same realms.
- **Effects:**
  - Everyone in the town gains a `witnessed` memory.
  - A `tribulation` fact names the person and the realm reached (weight 2.0), and the Pavilion's informants weigh it.
- **The player's roll:**
  - The outcome is seeded by the breakthrough event.
  - The chance of a clean result rises with body purity and with resting in the 3 days before (`rested` events).
  - There are three outcomes:
    1. **clean**: 70% at average purity with rest;
    2. **scarred**: harm and 10 days of rest;
    3. **crippled meridians**: 3% at worst, never below purity 0.5.

### 4.2 Qi tide
- Only the modifiers.
- NPC breakthroughs cluster naturally, and each one triggers a tribulation.

### 4.3 Blood moon
- **Demonic arts:** combat weight ×1.3 for any art whose doctrine is `unorthodox` or `demonic`.
- **Encounters:** road encounter chance ×1.5.
- **Patrols:** righteous-faction members' challenge chance against bandits in town ×2.

### 4.4 Comet omen
- **Foretold:** astrologers' rumours of the coming comet, as facts.
- **Active:** the war and price effects in the table.
- **Readings:** `war`, `a dynasty falls`, `a demon is born`, `a sage descends`. Each town has its own, seeded.

### 4.5 Beast tide
- When active, each town in the region rolls an attack (chance 0.3).
- An attack:
  - kills 1–3 townsfolk, through a `died` event with cause `beasts`;
  - starts a town price event (herbs ×1.5);
  - leads the magistrate to post a 3b beast bounty worth 30–80 silver, which the player can claim by winning three beast fights in the region before the aftermath ends.

### 4.6 Dao resonance
- The master is the highest-realm NPC in the town.
- Everyone in town gains `practice ×2` while it lasts.
- The master's name is recorded as a fact (weight 1.5).

## 5. Treasure races (treasure light, star fall)

- **At start:**
  - The prize is fixed from the occurrence's rng:
    - treasure light: a manual (a 2b technique, completeness 0.6–1.0), a pill (worth 1–3 years of qi) or a spirit herb (worth 200–600 silver at sale);
    - star fall: star iron, an item worth 400–900 silver.
  - The site is a town in the region.
- **Champions:**
  - At `announced`, each staffed faction with a seat within 2 regions sends its highest-realm member, if it has anyone at realm 2 or above.
  - Wandering masters join at 0.3 chance each, up to 2.
- **The contest:**
  - When the active stage ends, champions are ordered by realm and then by id. They fight in pairs through the 2b duel resolver, seeded.
  - The last one standing claims the prize with a `treasure_claimed` event, which sets the owner and records a weight 1.5 fact.
- **The player:**
  - `seek` while the occurrence is active and you are within 2 regions: you travel to the site, with normal travel time.
  - Being at the site when the contest resolves enters you: you duel each champion in turn (ranked, the lowest first), with a rest between duels.
  - Win them all and the prize is yours. Leave, or lose, and the NPC contest decides it.
- **Rule:** a prize is claimed at most once. The item has one owner.
- **4f link:** a treasure light's module can open a secret realm instead. 4f adds that branch; 4d leaves an `on_stage` hook point.

## 6. Rankings

### 6.1 The Pavilion
- An `institution` entity, "the Heavenly Ranking Pavilion", located in the city nearest region (0, 0), seeded.
- It is created on the first season hook, which also covers old saves.
- It is a knower in the 3a belief system.

### 6.2 Informants
- Each world season, the Pavilion considers the facts with predicates in `RANKING_FACTS`:
  - duel results (`defeated`, `killed`, `crippled`, `spared`);
  - `tribulation`, `treasure` and `phenomenon` (dao resonance), plus 4e's tournament facts later.
- It considers only facts it does not yet believe and that are at least one season old.
- Each is believed with chance `0.9 × 0.85^distance`, where distance is the Chebyshev distance in regions from the Pavilion's city. The roll is seeded per fact.
- It is re-rolled once a year for facts not yet believed.

### 6.3 Scoring (the Pavilion's beliefs only)
- **Realm tier:** the highest realm the Pavilion believes the person has, from `tribulation` facts or from defeating someone it believes to be of that realm. The score is `tier × 100`.
- **Deeds:** each believed win adds `10 + 0.6 × (the loser's score at the last revision)`. A kill of a ranked person counts the same as a win.
- **Fading:** deed points decay by ×0.8 for each full year since the fact. Tier never decays.
- **The dead:** anyone the Pavilion believes dead (a believed `died` fact) is left off the list.

### 6.4 Lists (revised each spring, the first season of the year)
- **Heaven:** the top 10.
- **Earth:** places 11–30.
- **Human:** places 31–60.
- **Young Dragons:** the top 10 of those the Pavilion believes are 30 or under. Believed age comes from the fact's recorded age plus years elapsed. This list may overlap the main lists.
- **Publishing:**
  - A `rankings_published` event stores the snapshot `{list: [[person, score], ...]}` plus the year. This is history.
  - One `ranked` fact per entry (weight 1.0; its variant names the list and the place).
  - Renown follows the facts.
- **Epithet:** someone on a list is known by their rank ("Seventh of Heaven") ahead of their 3a epithet.
- **Challengers:** in the 3a rival-encounter roll, a ranked NPC counts as renown ×2.

### 6.5 What the player knows
- The player knows a list if they believe its `ranked` facts.
- Entering a city after a revision teaches the whole latest list, because cities post it.
- `rankings.known(world, player)` returns the latest known snapshot and its age.

## 7. Screens

### 7.1 Briefs
- `sky_line`: one sentence per live occurrence covering the place, in the stage's grammar with the local reading.
- Brief facts include the kind, the stage, the days left and the reading.

### 7.2 Commands and pages
- `sky`: known occurrences (seen, or heard as facts), with where, the stage, the reading and the days left.
- `rankings` / F9: the known lists, your rank, the copy's age, and a note when a listed name is someone you know to be dead.
- `seek`: §5.
- **Tribulation:** a scene line on the turn of the breakthrough ("The clouds gather over you…"), then the outcome.

### 7.3 Sheet, journal, lineage
- **Sheet:** active modifiers on you (e.g. "Qi tide: cultivation ×1.5"), and your rank.
- **Journal:** witnessed stage starts, tribulations, claims and rank changes (`ranked` facts about you).
- **Lineage page:** each ancestor's best rank.

## 8. Debug rules

1. An occurrence's type exists. Its stage ends are ordered, `seen` is a prefix of the stage order, and `over` is true only when the aftermath has ended.
2. There is at most one live occurrence per type per place.
3. Every `factor()` result is within 0.25–4.0.
4. **Rankings:**
   - every listed person is someone the Pavilion holds a belief about;
   - each list is sorted by score with no duplicates;
   - Heaven, Earth and Human share no person;
   - every Young Dragon is 30 or under by the Pavilion's belief.
5. A race's prize is claimed at most once, and its item has exactly one owner.

## 9. Testing

- **Framework:**
  - stages follow dates;
  - one `world_event_stage` per transition;
  - a catch-up does not start old occurrences now;
  - modifiers combine and clamp;
  - a test-only TOML type loads and runs with no engine edits.
- **Phenomena:**
  - each knob moves its system (cultivation rate, breakthrough chance, encounter chance, clash chance, demonic weight, practice, prices);
  - news with local readings;
  - tribulation triggers for the player and for NPCs;
  - the player's roll is seeded and affected by rest;
  - beast tide attacks and bounty;
  - dao resonance names a master.
- **Races:**
  - the contest is deterministic;
  - a player win claims the prize;
  - the prize is never claimed twice;
  - a player who leaves loses their place.
- **Rankings:**
  - only beliefs count;
  - a hidden master stays unranked;
  - the dead stay listed until the Pavilion hears;
  - beating the 7th takes most of their score;
  - a city teaches the new list;
  - Young Dragons use believed age.
- **Engine:** `sky`, `rankings`/F9, `seek`, `sky_line` in briefs, sheet and journal lines.
- **Fuzz:** `test_a_sky_watcher`, 300 turns crossing phenomena and a race; every rule holds.
- **Old save:** loads, gets the Pavilion, and publishes at the next spring.
- **Speed (CPU time, the flake lesson):**
  - `factor()` under 0.2 ms;
  - the season hook with 50 regions under 20 ms;
  - a ranking revision over 2,000 believed facts under 50 ms;
  - the rankings page under 30 ms;
  - the 500-year soak stays green, with occurrences and database size bounded.

## 10. Out of scope for 4d

- Tournaments (4e), secret realms (4f), succession crises (4g).
- Forging with star iron (phase 5).
