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

## 9. Succession intrigue (phase 4h)

A hidden truth is a `plot` entity: `type` one of `murder`, `puppet`, `spy`, `frame`, `forgery`; its plotter,
patron, target, faction and the claimant it serves; its `clues` (each pointing at a person, some deliberately
false: `RED_HERRING`); who knows it (`known_by`); its `state` (`open`, `exposed`, `cold`, `void`; the spec's `buried` never comes, since a lost witness leaves a
`missing` clue behind); and a
secret fact of its truth (recorded with `spread = False`). The meta row `open_plots` lists the open ones: the
seasonal hooks (leaks, burial, `COLD_SEASONS`, each type's own) read only it.

**Where the rules live:**
- `systems/plots.py`: the model, clues, `suspicions`, `accuse_events` (two clues: `ACCUSE_CLUES`), exposure and
  `EXPOSE_HOOKS`, `SEASON_HOOKS`, `BEGUN_HOOKS`, the leaks (`LEAK_CHANCE`), burial (`BURY_CHANCE`), the quarters
  search, and `contest_exposures` (NPCs who know speak before the elders).
- `systems/murder.py`: `MURDER_CHANCE`, `motives`, `POISONS`, the body, the witness, the letters.
- `systems/puppets.py`: `PUPPET_CHANCE`, the gift-sways, the lent fighter, the pocket (`in_pocket`); cult spies
  (`SPY_CHANCE`, `THEFT_CHANCE`).
- `systems/frames.py`: `FORGE_CHANCE`, `FRAME_CHANCE`, exile (`exiles`, `RETURN_SEASONS`) and the return.
- `systems/legitimacy.py`: the supreme art (`ART_KNOWN`), the founder's test (`TEST_BOUNDS`, `TEST_DEATH`),
  marriage (`MARRY_CHANCE`), arbitration (`ARBITER_CHANCE`, `DEFY_CHANCE`), an outsider (`OUTSIDER_CHANCE`).
- `systems/scheming.py`: the player's poison, spy, puppet, frame and forgery, and their exposure (`DEEDS`).

**Saved state:** on a faction, `poisoned` (a murder's plot until its crisis begins), `pocket`, `supreme_art`,
`art_manual`, `heir_since`, `outsider`; on a person, `spy_of`, `framed`, `searched`; the meta rows `open_plots` and
`exiles`.

**Tests:** `tests/intrigue.py`'s `still(monkeypatch)` stills every intrigue for tests of what came before it.

**The rules:** `check_plots` in `debug/invariants.py` holds the index to the open plots, the plots' people real,
every clue pointing at its plotter (unless marked false), spies members of the sect they spy on, exposed plotters
struck from the claims, and exiles with a return to come.

## 10. Items with history (phase 5a)

A weapon or an armour is a `gear` entity: its `slot`, `form`, `grade` (0 iron to 4 divine; `gear.POWER` multiplies an
art of its form, `gear.ARMOUR_SHARE` softens a wound), `maker`, `owners` (who held it and how), `deeds` (its twelve
weightiest), and the marks `famous`, `epithet`, `armoury`, `heirloom_of`, `claimed_by`, `lost_at` and `broken`. A
person `wields` one weapon and `wears` one armour, each an item they own.

**Lazy gear:** an NPC carries only a seeded grade (`gear.seeded`), or their own record (`gear` on the person), until
it matters; `gear.materialize` then makes the item, its history begun. Nothing is made for those who never matter.

**Where the rules live:**
- `systems/gear.py`: grades, what someone carries, items, taking up and putting away, passing hands, breakage
  (`BREAK_CHANCE`, its own roll), the heir's inheritance.
- `systems/provenance.py`: deeds and `DEED_HOOKS`, the legend (`wielded_in`), knowing a blade on sight, and what
  people do about it (covet, hate, demand it back).
- `systems/famous.py`: the famous weapons (`famous_weapons`, seeded once their keeper exists), how they pass at a
  death, heirlooms, epithets, and the Hundred Weapons Chronicle (`weapons_ranked`).
- `systems/smithy.py`, `systems/armoury.py`, `systems/spoils.py`: the smith's stall, a sect's armoury, the fallen's gear.

**The rules:** `check_gear` in `debug/invariants.py` holds one owner per item and an owner that ends its history,
wielding only what one owns (one at a time), deeds that happened, famous weapons listed once, and armouries within
their seed.

## 11. Alchemy, medicine and poison (phase 5b)

**Herbs** are entities (`kind = "herb"`: a `herb` name and a `grade` of age, 0-3) whose properties belong to the
name, in `systems/data/herbs.toml` (element, polarity, potency, toxicity, terrains, price). A 4d treasure herb
counts as a herb of the table (`herbs.herb_info`). A person's `herb_lore` lists the names they know.

**Recipes** are the base needs in `systems/data/recipes.toml` (a dominant element, a polarity, a total potency, a
toxicity bound); a world's recipe entity (`recipe:{key}`) is made when first found, and a person knows it through a
`knows_recipe` relation whose value is their mastery. **Pills** are entities (`kind = "pill"`: `effect`, `grade`,
`purity`, `recipe`, `maker`).

**The body** gains `residue`, `venom`, `poisons` (active: grade, strength, days, sealed_until, named), `resist`,
`baths` and `breakthrough_aid`, all run lazily by `world.body.settle`. The meta row `poisoned` lists the NPCs
carrying a poison, so only they are looked at for a poison's death.

**Where the rules live:**
- `systems/toxins.py`: residue, active poison, sealing, forcing out, antidotes, death by poison; the registries
  `WOUND_HOOKS` (a wound that poisons) and `ABSORB_HOOKS` (what a body lets in).
- `systems/herbs.py`, `systems/alchemy.py`, `systems/pills.py`: herbs, experiments and refining, pills and venom.
- `systems/poison_path.py`: the poison path, the Myriad Poison Body, venomous beasts (`encounters.BEAST_HOOKS`),
  tempering baths.

**The rules:** `check_alchemy` in `debug/invariants.py` holds herbs of the table, well-made pills and masteries
within 0-1; `check_body` keeps residue and venom within 0-100 and poisons well formed; `check_toxins` keeps the
poisoned index to NPCs.

## 12. The alchemy world (phase 5c)

**Halls and gardens** are numbers on the faction, read without writing. A sect's `pill_hall` is
`{"grade:effect": count}`, stored only once something is drawn (until then it is the seed `pill_hall:{sect}`), and
set back to its seed each spring. Its `garden` is `{"at": season, "herbs": {name: [count, grade]}}`, stored only
when something is taken; `pill_hall.garden` brings it forward from `at` (growth, ageing). The player's own sect
builds a `herb_garden` and a `pill_hall` (3c's `BUILDINGS`); its hall is filled by its alchemist disciples, worked
out from `pill_hall_at` when read.

**The Guild** is no faction: a person's `guild_rank` (0 once joined; an NPC alchemist's is seeded until first
written) and the fact `guild_rank`, whose variant carries the `rank`. **Scrolls** are entities (`kind =
"scroll"`: `recipe`, `key`, `source`, and a sect's `faction`). Secret recipes live in
`systems/data/secret_recipes.toml` (`alchemy.SECRET`), never in `recipes.toml`, so `best_match` never finds them.

**The clinic and the doctors:** a town's physician is the person `physician:{town}`, made when first paid. A
famous doctor is `doctor:{bx}:{by}` for each block of 4 x 2 regions, made when first asked after; the asker's
`doctors_seen` remembers where. `physic.CURE_HOOKS` lets a later system add what a doctor cures (the control pill
does). A player's `healings` counts healings by town; five make them its healer.

**NPC alchemy** is a lives agenda: an NPC's `pills` is `{grade: count}`, made into pill entities only when the
player robs, strips, buys or inherits them.

**Control pills:** the bound carry `bound_to = {master, since, fed_until, hurt_to}`; the meta row `bound` lists the
bound NPCs (never the player, who is watched turn by turn), so only they are looked at each season.

**Where the rules live:** `systems/pill_hall.py`, `systems/hall_theft.py`, `systems/guild.py`,
`systems/recipe_trade.py`, `systems/physic.py`, `systems/npc_alchemy.py`, `systems/control.py`; the player's side
in `engine/alchemy_world.py` and `engine/alchemy_world_page.py`.

**The rules:** `check_alchemy_world` in `debug/invariants.py` holds gardens to herbs of the table within 0-12, halls
to no less than nothing, Guild ranks within 0-9, NPCs' pills to real grades, every scroll to one owner and a
recipe, and the bound index to the living bound of living people.

## 13. Forging and formations (phase 5d)

**Materials** are entities (`kind = "material"`: a `material` name and its `grade`, 0-4) of the table in
`systems/data/materials.toml` (grade, price, the towns whose smith sells it, or how else it is had). 4d's star iron
counts as a material of grade 3 (`materials.material_info`). A smith's ore is a seeded stock by the season (town data
`ore_sold`). A forge is an entity the player owns, a smith's rented for the day, or the own sect's `forge` building.

**Forging** keeps a person's `forge_mastery` (`{form: mastery}`) and `forge_xp`; a forged item is 5a's gear with
`forged_by`. A named masterwork joins 5a's `famous_weapons` with a `blade_legend` fact. `World.rename` renames an
entity.

**Formations** are the patterns of `systems/data/formations.toml` (use, flags, difficulty, days). A person knows one
through a `knows_formation` relation to the pattern entity (`formation:{key}`), whose value is its mastery, and keeps
`formation_xp`. Flags are one `flags` item with a `count`; manuals are `formation_manual` items. What is laid lives on
the town (`formations`: `{pattern, owner, until, strength}`), read by `formations.laid` and `strength`.

**Where the rules live:**
- `systems/materials.py`, `systems/forging.py`: materials, the forge, forging, refining, masterworks.
- `systems/formations.py`: patterns, manuals, flags, laying, and 4f's formation trials (`trial_bonus`).
- `systems/arrays.py`: what formations do, read where each rule lives (3c's gate, 5c's theft, 2b's fighters and
  fleeing, 2b's challengers, 2a's meditation).
- `systems/craft_world.py`: smiths' and formation masters' `craft_skill` (a lives agenda), their wares, and
  `commissions` (a person's list of forgings awaited).
- `systems/meet.py`: the Meet of Hammer and Furnace, one meta row (`meet`), opened each spring and decided after.

**The rules:** `check_crafts` in `debug/invariants.py` holds materials to the table, masteries within 0-1, flags to at
least one, formations laid to a pattern and a person, craft skills within 1-5, a named masterwork to the famous index,
and the Meet to a town and a span.

## 14. The dao heart (phase 5e)

**The heart** is person data `heart = {steady, lean, demons, daos, oaths}`: `steady` 0-100 (at rest 60), `lean` -100
(ruthless) to 100 (righteous). An NPC has none until something writes it; `heart.heart_of` reads a seeded one from
their traits. Deeds move it: the rows of `systems/data/heart_deeds.toml` (an event kind, the actor it moves, its way
and weight) and a duel's verdict. Its effects pivot at 60, so a heart at rest changes no older balance.

**Demons** (`{kind, whom, weight, since}`, at most five: guilt, grudge, fear, grief) are gathered and laid to rest by
listeners in `systems/demons.py`; the heaviest rises at a breakthrough to Second-rate or beyond (`demons.rising`,
`trial_events`), and `cultivation.breakthrough_events` takes `fail` and `shift` for what the trial left.

**Daos** (`daos`: `{form or element: 0-1}`) grow by epiphanies (`systems/daos.py`); one completed sets 2a's
`returned_to_origin`, the way to Life-and-Death. **Oaths** (`oaths`: `{kind, whom, until, sworn_at}`, at most three)
are settled by deaths and the seasons (`systems/oaths.py`), and are facts that spread.

**Blades** count `kills`; a woken `spirit` (`{nature, bond, master, known_by}`) lives on the item
(`systems/blade_spirits.py`); a cursed famous blade's is read from its seed until written. **Madness** is a lives
agenda (`systems/heart_world.py`): a mad NPC carries `mad_until` and hunts the player through 3b's `HUNTER_HOOKS`.

**The rules:** `check_heart` in `debug/invariants.py` holds hearts, demons, daos and oaths to their bounds, and the
mad to the living; `check_spirits` holds a spirit to a nature and a bond within 0-1.

## 15. Karma and tribulations (phase 5f)

**Karma** is person data `karma = {merit, sin, threads}`: heaven's ledger, apart from 5e's heart. An NPC has none until
something writes it; `karma.karma_of` reads a seeded one from their trade and traits. Deeds count through the rows of
`systems/data/karma_deeds.toml` (an event kind, the actor it counts for, its merit or sin), a duel's verdict, and a
`died` listener for killing.

**Threads** (`{whom, kind, weight, since}`, at most twelve) tie the player to people saved or wronged
(`systems/threads.py`); a 2b road hook (`encounters.ROAD_HOOKS`) brings the heaviest within reach back: a repayment,
or a `wronged` encounter that takes amends.

**Tribulations:** `systems/tribulations.py` weighs one by karma (`plan`) and keeps it gathering over the player as
person data `tribulation = {realm, minor, strength, waves, wave, failed}`; `systems/tribulation_waves.py` plays it
wave by wave (endure, a pill, a `tribulation` array of 5d's table, the heart's demon). A great tribulation is still
4d's `"tribulation"` event at its start, with its lightning and its news; a minor one is the player's own.
4d's lightning over an NPC now rolls their fate by their karma.

**The world** (`systems/karma_world.py`): a lives agenda strikes the wicked (`struck_down`); a season hook turns a
heavy sinner's luck; a town with a monk has a temple that takes alms.

**The rules:** `check_karma` in `debug/invariants.py` holds merit and sin to at least 0 and a gathering tribulation to
its wave kinds and a strength of at least 1.

## 16. The Claude layer (phase 6a)

**The rule:** Claude never writes the world. In 6a it only writes prose; from 6b it proposes, and `ai/validate.py`
turns what passes into ordinary events. Every failure leaves the procedural text standing.

**The door** is `ai/bridge.py`: one `claude -p` call per request, stripped bare (no settings, skills, hooks or MCP
servers of the user's own; no built-in tools; low effort), its reply checked against the `Job`'s schema by
`conforms`. Three failures in a row pause it for five minutes. Tests use `ai/fake.py`'s `FakeClaude`, which answers
from a script through the same `call(job, prompt)`.

**What Claude is told** is the state pack (`ai/pack.py`: HERE, LIMITS, CARRYING, LATELY, YOU, built from the pages
the player can read) and, for prose, the turn's briefs (`Brief.to_prompt`). A new system that wants Claude to know
something puts it on a page or in a brief, never straight into a prompt.

**Adding an MCP tool:** a function in `mcp_server/tools.py` taking the `View` (the world opened with
`World.open_readonly`, as its player knows it) and returning plain text with no ids, wrapped in `_safe`; then a
wrapper of the same name in `mcp_server/server.py`'s `build` and an entry in `TOOLS`. A read that would write (a
seeded body, say) fails on the read-only world and is told as not known.

**Prose** (`ai/narrate.py`): `Narration` asks once per turn, in a worker thread, over the lines the narrator wrote
(`Turn.narrated`); `ai/guard.py`'s `refusal` turns away prose that names someone unheard of or a thing the turn did
not, states a number it did not, or drops one it did. The modes are `off`, `assist` and `ai_only` (F1, saved as
`ai_mode`).

**Tests that call the real CLI** are marked `live` and also need `DEEPMURIM_LIVE=1`; no ordinary run makes one.

## 17. Two backends, the AI menu, one MCP server (phase 6b)

**Backends** (`ai/backends.py`): every job goes through `call(job, prompt) -> dict | None`, with 6a's rules (any
failure is None; three in a row pause it). `ClaudeCode` runs Claude Code through the Agent SDK on the player's own
login (their plan), one client per job kept open, each call a fresh session, `ANTHROPIC_API_KEY` taken out of its
environment. `OpenCode` keeps a hidden `opencode serve` warm and attaches each `opencode run` to it, with
OpenCode's own agent (its free models answer no other), calling `opencode.exe` directly, never the `.cmd` shim; the
job's JSON shape rides in the message, and the last text part is parsed. A new backend subclasses `Backend` and
implements `_ask(job, prompt) -> (reply, error)`.

**The AI menu** (`ai/menu.py`, F1): the mode, the backend, a model for prose and one for typed actions and talk
(6c). OpenCode lists only its free models (`ai/models.py` reads `opencode models --verbose` and keeps those of cost
0). The Connect page tells whether each backend is installed, warns of `ANTHROPIC_API_KEY`, and gives the
copy-paste setup for reaching DeepMurim's MCP server from one's own Claude Code or OpenCode.

**The MCP server** (`mcp_server/live.py`, `LiveServer`): one, over streamable HTTP on localhost, while the AI is on;
`build(save, fresh=True)` opens the save anew on every request (the game writes meanwhile).

**Prefetch** (`ai/prefetch.py`): for 6c's typed actions and talk, the people here, what those in play remember, and
what anyone here holds touching the words typed (with the `tell` handles), put in the prompt so the model rarely
needs a tool.


## 18. Typed actions and free talk (phase 6c)

**The router** (`App.submit`): a typed line the command parser does not know (never a number) goes to the model
when the AI is on and its backend can answer: in a conversation (`game.focus`) as a line said to that person (the
`dialogue` job), else as a typed action (the `intent` job). `ai/intent.py` holds both jobs and their prompts (the
state pack, the prefetch, the last paragraphs, this turn's choices as words, the typed line).

**The wait** (`ai/typed.py`, `Typed`): the prompt is built on the game's thread and asked in a daemon thread;
`App.poll` hands the answer to `Typed.resolve` when it comes. Input waits meanwhile, under a line drawn from the
clock (`App.waiting_line`); Esc lets the wait go and nothing happens. A timeout or any failure says "You hesitate".

**Proposals** (`ai/validate.py`): `accept(scene, proposals, kinds)` returns the events that may stand, at most one
engine action (a choice of this turn), and the rest with their reasons. There is no retry. What stands is committed
by `Game.apply_proposals` (`engine/ai_turns.py`) as ordinary events marked `ai: true`; `check_ai` (in
`debug/invariants.py`) holds every such event to its kind's limits.

**Adding a proposal kind:**
1. In `ai/validate.py`: the kind in `KINDS` (and in `DIALOGUE_KINDS` if talk may cause it), its fields in
   `PROPOSAL`, and its checks in `check`, returning an event or a reason.
2. In `ai/deeds.py`: the event's builder (its data carries `ai: True` and the proposal), its kind in `KINDS`, and
   its `@effect`.
3. In `narrate/ai_text.py`: an `@outcome` giving its one engine line (shown under the paragraph in assist mode) and
   a `@summary` for the journal; in `narrate/grammar/ai.toml`, its table.
4. In `ai/intent.py`: a line in `VOCABULARY`, so the model knows it; in `check_ai`, its limits.
