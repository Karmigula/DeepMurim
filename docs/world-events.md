# World events: adding your own

DeepMurim's scheduled world events (phase 4d) are data plus a little code. A fork adds an event
without touching the engine: one entry in `systems/data/world_events.toml`, and, if it needs to
do more than lend modifiers, one module under `systems/events/`.

## 1. The TOML entry

~~~toml
[meteor_shower]
module = "systems.events.meteor_shower"   # optional
scope = "region"          # world | region | town | site (site: a town chosen in the region)
cycle = "season"          # "season": rolled each world season; "trigger": your code starts it
chance = 0.02             # per eligible place per season
stages = { foretold = 5, announced = 3, active = 10, aftermath = 10 }   # days; leave a stage out to skip it
modifiers = { cultivation = 1.2 }          # knobs, while active (see below)
prices = { iron = 0.8 }                    # 4c price multipliers, while active
readings = ["good fortune", "a hero's death"]   # what towns make of it; each town picks one
news = { predicate = "phenomenon", weight = 1.5, stages = ["announced", "active"] }
~~~

A type can instead come round on a fixed period (phase 4e):

~~~toml
[grand_assembly]
module = "systems.events.grand_assembly"
scope = "town"
cycle = "every"           # held every `every` seasons, where the module's `places` hook says
every = 12
stagger = false           # true: each place keeps its own turn (sect contests), so they do not all fall at once
sky = false               # not a phenomenon: kept off the sky page and the scene's sky lines
stages = { foretold = 60, announced = 20, active = 8, aftermath = 30 }
~~~

Each occurrence is a `world_event` entity. Its stage is worked out from the calendar; the first
time a stage is observed (every world season, and every time the player sees the place) a
`world_event_stage` event is committed and your module reacts.

## 2. The module's hooks (all optional)

| Hook | When | Returns |
|---|---|---|
| `eligible(world, place, n)` | after the chance roll (for `every`: only at a place whose turn it is), before it starts in season `n` | bool |
| `places(world, n, rng)` | `every` types, each season: where it would be held | a list of places |
| `summary(world, place, n, rng)` | `every` types whose place the player is not at: settle it in a line, with no occurrence | a list of events |
| `start_data(world, place, n, rng)` | when it starts | a dict kept on the occurrence (`None`: do not start) |
| `on_stage(world, occurrence, stage)` | the first time a stage is observed (`foretold`, `announced`, `active`, `aftermath`, `over`) | a list of events to commit |
| `on_observe(world, occurrence)` | every observation of a begun occurrence (a tournament's days pass) | a list of events to commit |

A module can also register hooks of its own when it is imported: the blood moon adds its patrols
to `encounters.HUNTER_HOOKS`. `systems/sky.py` imports every module named in the TOML at start.

To start a `trigger` event from your own code: `systems.sky.start_events(world, kind, place, starts, data)`.

## 3. The knobs

`systems.world_events.factor(world, place, key, at=None)` multiplies the `key` modifiers of every
occurrence active over a place, clamped to 0.25-4.0. These keys are read today:

| Key | Read by |
|---|---|
| `cultivation` | meditation (player) and the life clock's growth (NPCs, at the season being lived) |
| `breakthrough` | breakthrough chance, player and NPC |
| `practice` | practising and learning arts |
| `encounter` | the road encounter chance |
| `beasts` | road encounters, and the share of them that are beasts |
| `clash` | the faction clock's clash chance (world-wide occurrences) |
| `demonic` | the combat weight of demonic-cult and unorthodox-clan members |
| `patrol` | righteous patrols calling out the ruthless |
| `prices` (a table, not a key) | 4c market prices, through `market.EVENT_FACTORS` |

A new knob is one `factor()` call in the system it should move, and a key in your TOML.

## 4. Names that must not collide, and what is saved

- **Event kinds and verbs are global.** Every event kind has exactly one effect (`world.events.EFFECTS`), and every
  player verb is a `_do_<verb>` method found through the `Game` class's bases. A new kind or verb that reuses an existing
  name silently replaces or shadows it, so pick names that no other system uses (`grep -rn '@effect("'` lists them).
- **A misspelt field is refused.** `full_spec` raises on an unknown field or stage, so a typo in your TOML fails at start.
- **Saved state.** Occurrences are `world_event` entities, and treasures are `treasure` entities. The meta rows are:
  - `sky_index`: the occurrences that still matter;
  - `capital`: the Pavilion's city;
  - `pavilion`: the Pavilion itself;
  - `pavilion_mark`: the newest fact its informants have weighed;
  - `pavilion_retry`: facts waiting for their second chance.

## 5. The worked examples

`systems/data/world_events.toml` holds eight: the qi tide and the comet (modifiers only), the
blood moon (a hook of its own), dao resonance (`eligible`, `start_data`, `on_stage`), tribulation
lightning (a trigger), the beast tide (attacks and a bounty), and the treasure light and star fall
(races, in `systems/races.py`). The debug rules in `debug/invariants.py` (`check_sky`,
`check_races`) guard every type, including yours.

## 6. Adding a tournament kind (phase 4e)

A tournament is an `every` type with `sky = false`, whose module leans on `systems/tournaments.py`:

- **The module** (see `systems/events/grand_assembly.py`):
  - `SIZE` (a power of two) and `ROUND_DAYS` (one day per round, the final last);
  - `places` (the host) and `start_data`, which returns `T.start_data(kind, SIZE, ROUND_DAYS, prize, title, edition)`;
  - `qualifies(world, occurrence, person, slack)`: who may enter;
  - `invite(world, occurrence)`: who is asked, usually `T.pool(...)`;
  - `on_stage` and `on_observe`, which hand over to `T.on_stage` and `T.on_observe`;
  - optionally `rewards(world, occurrence, champion)`, the events that follow the crown.
- **The shared tables:**
  - `T.KINDS`, `T.KIND_WEIGHT` (how much a win is worth to the Pavilion) and `T.NEWSWORTHY` (bouts talked of far away);
  - `T.RULES` and `T.BONDS`: the entry rule's words and the bond;
  - `intrigue.CHANCES`: the dark interventions it may suffer;
  - `narrate.tournament_text.KIND_NAMES`.
- **Saved state:** the bracket lives in the occurrence's `data["data"]` (registrations, rounds, bets, the plot),
  compacted to its podium when the aftermath ends. Player data gains `titles`, `invitations` and `tour_seen`.
- **The rules:** `check_tournaments` in `debug/invariants.py` guards brackets, advancing, bouts, bets and eligibility for
  every kind, including yours.
