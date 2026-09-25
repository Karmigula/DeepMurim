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
| `summary(world, place, n, rng)` | `every` types whose place the player is not at: settle it in a line, with no occurrence | a list of events, or `None` to hold it in full after all |
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

## 7. Secret realms (phase 4f)

A secret realm is a lasting `secret_realm` entity (its gate town, its master and their art, its entry rule, its
period, its floors of chambers, its history). Its openings are two event types in the TOML:

- `realm_opening`: an `every = 1` type whose `places` hook names the gates of realms due this season (each realm
  keeps its own period, 12-40 seasons for the ancient ones); heralded like any phenomenon.
- `realm_awakening`: a trigger type, a newborn realm's first opening, started when a treasure light cracks a realm
  open (`secret_realms.CRACK_CHANCE`).

**The tables** in `systems/secret_realms.py`: `PLACES` and `EPITHETS` (names), `WEAPONS`, `GUARDIANS`, `TRIALS`,
`RULES_ANCIENT` and `RULES_NEWBORN` (the entry rules: ceiling, token, open, quota), and `CHAMBER_WEIGHTS` (what a
floor holds). The knobs of chance live beside the code that rolls them: `realm_gates` (tokens, who the sects send,
fates far away), `chambers` (guardians, trials), `delvers` (the bands inside) and `sealed` (the years inside).

**Saved state:**
- the meta row `secret_realms` lists every realm, ancient first;
- a person's `sealed_in` (`{"realm", "season"}`) marks them shut in until the next opening, and a sealed person is
  off the life clock until they walk out;
- the player's `delve` (`{"realm", "floor", "chamber"}`) is their place inside; a band member's `delve_at` is theirs;
- guardians, reflections and a master's remnant are `realm_spirit` persons who live inside.

**The rules:** `check_realms` in `debug/invariants.py` guards the inheritance (claimed once), who may be inside, the
ceiling, and the player's place inside.

## 8. Succession crises (phase 4g)

A crisis is a `succession_crisis` occurrence: a trigger type, started by the faction clock (never on a calendar)
when a leader has died and the seat is in doubt. Its stages carry the framework's fixed names: `announced` is the
mourning (claims are made), `active` the canvass (camps are made), and the contest is decided as the `aftermath`
begins. Force of arms (`strife`) runs on after the stages, a season at a time, on the faction clock.

**Where the rules live:**
- `systems/succession_crisis.py`: `doubt` (why the seat is in doubt: `violence`, `token`, `heir`, `close`),
  `leaderless_events` (the clock's question), `begin_events`, the contest and the summary far from the player.
- `systems/claimants.py`: the chief disciple (`heir` on the faction, named once a year), who claims (`declare`,
  `MAX_CLAIMANTS`), who votes (`voters`), how they lean (`lean`, `PROOF_LEAN`, `AMBITIOUS`).
- `systems/testament.py`: the will (`WILL_CHANCE`, `WILL_STATES`), the leader's token (`sect_token`, one per faction),
  deathbed transmission (`TRANSMIT_CHANCE`), the Grand Elder (`EMERGE_CHANCE`, `secluded`).
- `systems/schism.py`: strife (`YIELD`, `STRIFE_SEASONS`) and breakaways (`PREFIXES`, `MAX_BREAKAWAYS`, `MAX_MINORS`).
- `systems/regency.py`: a sect the player leads (the heir's claim, `ABSENCE`, stepping down) and regents for a child.
- `systems/crisis_play.py` and `engine/crisis.py`: what the player can do (declare, claim, sway, champion, search,
  the token and the will).

**Saved state:**
- on a faction: `crisis` (its live occurrence), `heir` (the chief disciple), `fallen` (how its leader died),
  `transmitted`, `history` (one line per crisis), `parent` (a breakaway's), `regent`, `regency_for`, `visited`,
  `usurped_from`;
- the occurrence's `data["data"]`: claimants, declared camps, sways, champions, the will, the token, the trial,
  strife, the outcome and its phase;
- a Grand Elder is a person `secluded` in the seat's region: in no scene, at no tournament.

**The rules:** `check_crises` in `debug/invariants.py` holds one live crisis a faction, the faction pointing at it,
no one but a claimant in the leader's seat during it, a token in exactly one place, and at most two breakaways a sect.
