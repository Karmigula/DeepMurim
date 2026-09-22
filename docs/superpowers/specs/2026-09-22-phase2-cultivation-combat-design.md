# DeepMurim Phase 2: Cultivation, Body, Techniques, Combat

Date: 2026-09-22
Status: Draft, awaiting user review
Parent spec: `2026-09-22-deepmurim-design.md` (§5.1–5.3, §6.0, §8 item 2)

## 1. Goal

Give the player a body that remembers everything done to it, a slow and meaningful road of cultivation, martial arts that are *things in the world* (taught, stolen, flawed, invented), and duels where the realm gap, the technique, the body and the player's choices all matter.

Every one of these systems must also:
- report its state to the narrator as `Brief` facts plain enough for Haiku (parent §6.0);
- add rules to `debug/invariants.py`;
- be exercised by the fuzz test.

### Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Pacing | Slow, driven by time skips. Seclusion for days, weeks, months or a season. Rising to First-rate takes in-game **years**. |
| Defeat | Injured, never killed (death arrives with lineage in phase 4). Losing can mean robbery, humiliation, or **permanent** injury from ruthless foes. |
| Numbers | Murim descriptions on the main screen. Exact numbers on the **F4 character sheet**. |
| Getting arts | All of: a starting art, wandering teachers, manuals, observing/sparring for fragments, creating your own. |
| Combat | Exchange rounds (intent + technique + qi output), 3–8 exchanges per fight. |
| Opponents | Spar or challenge NPCs, road encounters, NPCs challenging you. |
| Realms | Murim ranks, continuing into an immortal path later (defined but locked in phase 2). |
| Creation | Three modes offered: Origin, Random, Point-buy. |

### Split
One spec, two build plans:
- **2a, Body & Cultivation:** body model, realms, techniques as entities, creation modes, cultivation actions, the purse, the F4 sheet with body chart, menu grouping, briefs, invariants.
- **2b, Combat & Sources:** duel engine and opponent AI, sparring and challenges, road encounters, NPC challenges, teachers, manuals, fragments and technique creation.

2a comes first because 2b consumes its bodies and techniques.

## 2. Architecture

The phase 1 patterns continue:
- Pure systems produce `Event`s, `commit` applies them, briefs feed the narrator, and invariants police the result.
- There are no new tables. Structured data lives in entity `data` JSON, and relationships use `relations`. Schema stays at version 1.

```
world/body.py          Body, Meridian, Injury dataclasses + (de)serialise; body generation from seed
systems/realms.py      realm ladder, stages, bottlenecks, breakthrough conditions
systems/cultivation.py meditate / seclusion / practise / open meridian / rest / breakthrough; deviation
systems/techniques.py  technique entities, parts, compatibility, mastery, name generation
systems/purse.py       silver
systems/creation.py    origins, random, point-buy → starting body/arts/silver
systems/combat.py      (2b) duel state, exchange resolution, consequences
systems/opponent.py    (2b) intent choice from personality + read of player habits
systems/encounters.py  (2b) road encounters, NPC challenges
systems/learning.py    (2b) teachers, manuals, fragments, technique creation
engine/game.py         menus + handlers for the above; grouped menus
narrate/brief.py       new brief kinds and body/combat facts
render/body_chart.py   ASCII body figure coloured by injury + meridian list (pure)
```

- **Bodies are created lazily.** The player's body is made at character creation. An NPC's body is generated from `seed_for(world_seed, npc.seed_path + "/body")` plus their stored `realm` the first time a system needs it (a fight, teaching, the sheet), then stored.
- **Old saves:** on load, a player with no `body` gets one rolled with the "wanderer" origin, recorded as a `body_awakened` event.

## 3. The body (`world/body.py`)

```
Body
  energy_years: float        accumulated internal energy, measured in years (murim convention)
  qi: float                  current combat pool; max = 10 + 10 * energy_years * purity
  purity: float 0.3..1.0
  nature: {yin, yang, metal, wood, water, fire, earth} weights (the elements sum to 1; yin+yang = 1)
  meridians: {name: Meridian}
  physique: {strength, agility, endurance, comprehension}  each 1..20 (10 = average)
  constitution: str | None   hidden; discovered by event
  constitution_known: bool
  injuries: [Injury]
  deviation: float 0..100
  realm: int, bottleneck: bool
  insight: float             general martial insight
  flags: set[str]            e.g. "life_and_death_insight", "sensed_qi"
Meridian: state ∈ {open, blocked, damaged, scarred, severed}, flow 0..1, opening_progress 0..1
Injury: id, location, kind ∈ {bruise, cut, fracture, internal, meridian}, severity 1..5,
        permanent: bool, since: time, heals_at: time | None, cause: str (event summary)
```

- **Meridians.**
  - The 12 regular ones: Lung, Large Intestine, Stomach, Spleen, Heart, Small Intestine, Bladder, Kidney, Pericardium, Triple Burner, Gallbladder, Liver. They start *open*, with flow rolled between 0.4 and 0.9.
  - The 8 extraordinary ones: Governing, Conception, Penetrating, Girdle, Yin Linking, Yang Linking, Yin Heel, Yang Heel. They start *blocked*.
- **Body locations** for injuries: head, torso, left arm, right arm, left leg, right leg, plus any meridian name for meridian injuries.
- **Healing:**
  - An injury heals in `severity² × 5` days, divided by `endurance/10`. Resting doubles the speed.
  - `damaged` meridians heal back to `open`, but only if flow is at least 0.5; otherwise they become `scarred`. `scarred` meridians never return to `open`.
  - Anything `permanent` never heals.
- **Constitutions** (hidden; each rolled body has a 4% chance of one): Nine Yin Body, Pure Yang Body, Heavenly Sword Bones, Myriad Poison Body, Iron Bone Body, Dragon Vein Body.
  - Each gives a clear bonus and a flaw. For example, Nine Yin Body: +50% cultivation for yin arts, and cold deviation when using yang arts.
  - A constitution is discovered on the first breakthrough, the first qi deviation, or the first time a matching art is practised to Minor Success.

## 4. Realms (`systems/realms.py`)

| # | Realm | Enter at energy (years) | Breakthrough condition (besides energy) |
|---|---|---|---|
| 0 | Mortal | 0 | — |
| 1 | Third-rate | 1 | Has sensed qi (the first week of meditation grants it) |
| 2 | Second-rate | 5 | Governing **or** Conception open |
| 3 | First-rate | 20 | Governing **and** Conception open (Small Heavenly Circuit); a martial art at Major Success |
| 4 | Peak (Jeoljeong) | 40 | A martial art at Great Completion; flag `life_and_death_insight` |
| 5 | Transcendent (Hwagyeong) | 60 | All 8 extraordinary meridians open (Large Heavenly Circuit); insight ≥ 200 |
| 6 | Profound (Hyeongyeong) | 120 | Created your own art and brought it to Great Completion |
| 7 | Life-and-Death (Saengsagyeong) | 240 | Flag `returned_to_origin` (an event in a later phase) |
| 8+ | Immortal path: Foundation Establishment, Core Formation, Nascent Soul… | — | **Locked in phase 2.** The names are defined, and the condition reports "the way beyond is not yet open to you". |

- **Stage** within a realm comes from the position of `energy_years` between this realm's threshold and the next: under 25% is early, under 50% middle, under 75% late, otherwise peak.
- **Bottleneck:** once energy reaches the next realm's threshold, energy stops growing (it is capped there) and `bottleneck = True`.
- **Breakthrough:**
  - It can be attempted at a bottleneck. If the condition is unmet, the attempt still happens but the success chance is multiplied by 0.1.
  - Success chance = `0.35 + 0.05 × (comprehension − 10) + 0.1 × purity + insight_bonus`, clamped to 0.05–0.95.
  - Success: realm +1, purity +0.05, max qi recomputed.
  - Failure: 1–2 meridians on the heart method's route become `damaged`, deviation +30, energy −5%.
- **Realm multiplier for combat:** `[1, 3, 6, 12, 24, 48, 96, 192]`, and the stage adds 0%, 10%, 20% or 30%.

## 5. Techniques (`systems/techniques.py`)

A technique is an **entity** of kind `technique`. Its `data` holds:

```
category: "heart_method" | "martial"
form: sword | saber | spear | staff | palm | fist | finger | footwork | inner   (inner = heart method)
stance: str                 flavour + which intent it favours (+10% to that intent)
route: [meridian names]     2–6 meridians, ordered
element: one of the five | yin | yang | neutral
grade: 1..6                 1 = third-rate art … 6 = transcendent art (multiplier 1.0,1.5,2.2,3.2,4.5,6.5)
power, speed, defence: 0.5..1.5 profile
creator: entity id | None, origin: "seeded" | "created"
```

- **Knowing a technique:** relation `knows` (person → technique), where `value` = mastery (0..1) and `data` = `{completeness, known_completeness, source, teacher, since}`.
- **Mastery stages:**
  - Initial: under 0.34
  - Minor Success: under 0.67
  - Major Success: under 1.0
  - Great Completion: 1.0
  - Mastery can never exceed `completeness`.
- **Compatibility** = route × nature × body, clamped to 0..1.3:
  - **route:** the product over the route's meridians of: open 1.0, scarred 0.8, damaged 0.5, blocked 0.3, severed 0. Any severed meridian makes the technique unusable.
  - **nature:** 1 + 0.3 × alignment, where alignment is between −1 and 1 and comes from the technique's element against the body's `nature` weights. Clamped to 0.6..1.3.
  - **body:** the governing physique by form is sword/finger/footwork → agility; saber/fist → strength; spear/staff → the mean of strength and agility; palm/inner → the mean of endurance and comprehension. The factor is 0.8 + 0.4 × (stat/20).
  - **Words for it:** under 0.4 "fights your body", under 0.7 "sits awkwardly", under 1.0 "suits you", otherwise "made for you".
- **Names** are generated from seeded parts: `[Pale|Iron|Nine Bends|Falling Leaf|Azure|Blood|Silent|…] [Crane|Tiger|Plum|Thunder|Serpent|Cloud|…] [Palm|Saber|Sword Art|Fist|Finger|Steps|Heart Method|…]`.

## 6. Cultivation actions (`systems/cultivation.py`)

A **Cultivate…** menu with these choices:
1. **Meditate:** 1 day, 1 week, 1 month, or a season in seclusion (90 days).
2. **Practise** a known martial art for 1 week.
3. **Open a meridian:** pick a blocked extraordinary meridian. The work happens over weeks.
4. **Rest:** 1 week, healing twice as fast.
5. **Attempt breakthrough:** only offered at a bottleneck.
6. **Back.**

Each action is one Event (`cultivated`, `practised`, `opening_meridian`, `rested`, `breakthrough`), plus a `deviation` or `discovery` event when triggered. Time advances accordingly. All randomness comes from `rng_for(world_seed, f"cultivate:{event-count}")`, so replay is exact.

- **Energy per day of meditation:**
  - Formula: `0.01 × grade_mult(heart_method) × (comprehension/10) × purity_factor × route_flow × seclusion × injury_penalty`.
  - `purity_factor` = 0.5 + purity.
  - `route_flow` = the mean flow of the heart method's route meridians, with blocked, damaged and severed counting 0.
  - `seclusion` = 1.2 when the stretch is at least 30 days.
  - `injury_penalty` = 0.5 while any internal injury is unhealed.
  - Pacing target: an average mortal with a grade-1 heart method reaches Third-rate in roughly 60–150 days, and Second-rate (energy 5) takes years. Tested.
- **Practise:** mastery += `days × 0.004 × (comprehension/10) × compat / grade_mult`, capped at completeness. Practising at compat < 0.5 adds deviation `days × (0.5 − compat) × 2`.
- **Open a meridian:**
  - Needs energy ≥ 2 + 3 × (number already open).
  - Progress += `days × 0.01 × (comprehension/10)`. At 1.0 the meridian is `open`, with flow 0.3.
  - Each week there is a 3% chance of forcing it, which damages a regular meridian and adds deviation +15.
- **Rest:** healing ×2. Deviation −1 per day, compared with −0.5 per day for any other time passing.
- **Qi deviation:** when deviation ≥ 100:
  - 1–2 meridians on the practised or cultivated route go down a state: open → damaged, damaged → scarred.
  - Energy −10%, and deviation resets to 40.
  - The Brief states the cause, which is what lets a flawed manual reveal itself (2b).
- **Qi pool:** refills to max after any rest or meditation of at least 1 day.

## 7. Character creation (`systems/creation.py`)

After you enter your name, a **Creation** screen offers 3 modes.

1. **Origin** (pick one of these; the seed rolls the rest within its bias):

| Origin | Starting heart method / art | Body bias | Silver |
|---|---|---|---|
| Hunter's child | Grade-1 inner method; grade-1 spear or fist art | strength/endurance +2 | 30 |
| Fallen clan scion | Grade-2 inner method (known completeness 1.0, true 0.8); grade-1 sword art | comprehension +2, one meridian scarred (the fall) | 80 |
| Temple orphan | Grade-1 inner method (yang); grade-1 palm or staff art | purity +0.1, endurance +2 | 10 |
| Merchant's runaway | Grade-1 inner method; grade-1 footwork | agility +2 | 200 |
| Beggar-sect urchin | Grade-1 inner method; grade-1 staff or fist art | agility +2, comprehension +1 | 5 |

2. **Random:** a random origin, a random body, no bias.
3. **Point-buy:** 12 points across strength, agility, endurance and comprehension, starting at 8 each with a maximum of 16 before rolls. Plus "meridian openness", where 2 points raise every regular meridian's flow by 0.1. The heart method and art are grade 1, with a form you choose. Silver 50.

- The constitution is always rolled hidden, in every mode.
- The start is recorded as a `began` event with the origin in its data. The journal and briefs mention the origin.
- The origin's seeded starting techniques are entities with `creator = None`, and the fallen clan's method has a **real hidden flaw**. That is the first "manual lie" (knowledge vs truth, parent §5.5): only `known_completeness` is ever shown.

## 8. Silver (`systems/purse.py`)

- `data.silver` on a person, changed only through events (`paid`, `received`, `robbed`).
- An invariant enforces `silver ≥ 0`.
- NPC silver is seeded by occupation.

## 9. Combat (2b, `systems/combat.py`, `systems/opponent.py`)

### 9.1 State
- `Game.combat: Duel | None` holds the participants, mode ∈ {spar, duel, encounter}, exchange count, each side's `harm` (0–100), current technique, qi output, recent intents, revealed tendencies, and witnesses.
- Harm is written to the body as injuries as the fight goes. The duel itself lives in the engine and is rebuilt on load from the last `duel_started` event if a fight was interrupted.

### 9.2 One exchange
The player's choices are `1 Strike · 2 Feint · 3 Guard · 4 Probe · 5 Change technique · 6 Qi output: <current> · 7 Yield · 8 Flee`. The opponent picks its intent hidden (§9.4). Outcome by intent pair, where A is the attacker's intent and B the defender's:

| A \ B | Strike | Feint | Guard | Probe |
|---|---|---|---|---|
| Strike | both hit (each ×0.7) | A hits ×1.0 | blocked; B gains *opening* (+20% next exchange) | A hits ×1.0 |
| Feint | B hits ×1.0 | nothing | A hits ×0.8 (guard broken) | B reads it: B hits ×0.6, reveals A |
| Guard | A gains opening | B hits ×0.8 | both recover 2 qi | B reveals A's style |
| Probe | B hits ×1.0 | A hits ×0.6, reveals B | A reveals B's style | both reveal |

(The table is symmetric in meaning. Each cell is resolved once, from both sides.)

- **Effective power** = `realm_mult × stage × T × Q × C × phys`, where:
  - T = grade_mult × (0.5 + mastery) × compat. Bare hands: T = 0.5.
  - Q = qi output: restrained ×0.7 (costs 1 qi), steady ×1.0 (3), full ×1.3 (6), all-in ×1.7 (12, and deviation +8). With too little qi, the output drops to what can be paid.
  - C = condition: fresh 1, bruised 0.95, hurt 0.85, badly hurt 0.7.
  - phys = the technique's body factor (§5), times 0.85 for each unhealed injury on a location the form uses (arms for weapons, palm, fist and finger; legs for footwork).
- **A hit** does `damage = 10 × (eff_hitter / eff_target)^0.8 × cell_mult × rng(0.8..1.2)` to the target's harm.
  - Condition bands: bruised at 15, hurt at 35, badly hurt at 60, broken at 85.
  - A hit of 8 damage or more makes an injury at a location chosen by the hitter's form, with `severity = min(5, 1 + damage // 12)`.
- **Flee:** chance = `sigmoid((agility_self − agility_other)/4 + leg_penalty + condition_penalty)`. A failed flee gives the opponent a free Strike ×1.0.
- **Yield** ends the fight as a loss.

### 9.3 Endings and consequences
- The fight ends when someone is **broken**, yields, flees, or (in a spar) the first hit of 8 damage or more lands or 3 exchanges pass.
- **An NPC who wins** decides by personality:
  - kind, honest or loyal: spares you;
  - greedy: robs 30–100% of your silver;
  - bandit, or cunning and greedy together: 25% chance to cripple you, meaning one **permanent** injury (a severity-5 fracture, or a severed meridian);
  - no death in phase 2.
- **When the player wins,** a choice menu: Spare / Rob / Cripple.
  - Crippling gives the NPC a permanent injury and an **indelible** hatred memory: the grudge seed for phase 3.
- **Memories:**
  - The loser remembers *humiliated*, or *grateful* if spared by a stronger opponent.
  - The winner remembers *respect* or *contempt*.
  - Witnesses (people present) get a `witnessed_duel` memory.
- **Insight** comes from:
  - a fight against someone of higher realm: +5 × realm gap;
  - a spar: +3;
  - winning while badly hurt, or against a higher realm: flag `life_and_death_insight`.
- **Events:** `duel_started`, one `exchange` per exchange (weight 0.2), and `duel_ended` (weight 1). Each exchange event carries the resolved outcome, so replay and briefs are exact.

### 9.4 Opponent AI
- **Base intent weights by trait:**
  - hot-tempered or proud: Strike 3, Feint 1, Guard 1, Probe 1;
  - cautious: Guard 2, Probe 2;
  - cunning: Feint 3;
  - otherwise all 1.
- **Reading the player:** for each of the player's last 3 intents, +0.5 weight to the intent that beats it.
- **Behaviour:**
  - When badly hurt: a cautious or kind opponent yields 40% of the time; a bandit flees 30% of the time.
  - Chooses qi output all-in when behind and hot-tempered.
- All choices come from `rng_for(world_seed, f"duel:{duel_event_id}:{exchange}")`.

### 9.5 Balance targets (tested by a solver)
- Mortal against Third-rate (equal otherwise): Third-rate wins ≥ 95% of 200 simulated duels.
- Equal realm and equal stats, player intents random: win rate between 35% and 65%.
- No fixed player strategy ("always Strike", "always Guard"…) wins more than 70% against the adaptive AI at equal strength.

## 10. Opponents and sources (2b)

- **Spar or challenge:** a conversation gains `Spar with them` and `Challenge them` when the NPC is at least an acquaintance, or on request.
  - A challenge makes the NPC's memory *challenged*. A proud NPC always accepts.
- **Road encounters:**
  - Each region has a seeded `danger` between 0 and 1. A road trip triggers an encounter with chance `danger × 0.35`.
  - The kind depends on terrain: bandits (all terrain), beasts (forest, mountains, marsh), or a rival wanderer.
  - Choices: Fight / Flee / Pay toll (bandits) / Talk. Talk succeeds based on the opponent's traits.
  - Bandits and wanderers are **real persons** materialized in that region. They persist and remember you.
  - Beasts are persons of kind `beast` with a fixed simple AI.
- **NPC challenges:** on arrival or on Look, any present NPC who is proud or hot-tempered *and* holds an *annoyed* or *humiliated* memory of you challenges you with 30% chance. Choices: accept, or decline (the NPC records *contempt*).
- **Teachers:**
  - Occupations wandering swordsman, monk and hunter (60%, 50% and 20% of them respectively) know 1–2 seeded arts.
  - A conversation gains `Ask to learn…` when you're at least an acquaintance.
  - Price: silver of `20 × grade²`, or a test spar you must survive for 3 exchanges.
  - Learning creates a `knows` relation with mastery 0.05, completeness 1.0, source `taught`, and the teacher's id.
- **Manuals:**
  - Items (kind `manual`) carrying a technique id, `true_completeness` (0.4–1.0), and `claimed_completeness` (usually 1.0).
  - Sold by merchants and scholars (40% carry 1–2). Carried by bandits (25%).
  - Studying takes 2 weeks and creates `knows` with completeness = true and known_completeness = claimed.
  - Mastery beyond the true completeness is impossible. Practising past it adds deviation, and the deviation event's Brief says "the manual's instructions are wrong". Only then is `known_completeness` updated to the truth.
- **Fragments and creation:**
  - Probing an opponent who uses an art gives a fragment 30% of the time. So does watching a duel where you're present but not fighting.
  - Sparring gives a fragment 50% of the time.
  - A fragment is `{technique, form, element, route_segment (2 meridians)}`, stored on the player.
  - **Create technique** (in Cultivate…) needs 3 fragments, insight ≥ 20 and a week of seclusion.
    - The new art's form is chosen from the fragments' forms.
    - Its route is fragment segments joined through your open meridians.
    - Its grade is `min(realm + 1, 1 + insight // 40)`, and mastery starts at 0.1.
    - Its creator is you, and the name is generated, or typed on the command line if you want.

## 11. Menus and screens

- **Menu grouping** (generalising phase 1): the main menu is built from groups in this priority order: people, routes, cultivation, then look and journal.
  - If the flat list is longer than 9, groups fold into `Talk to someone here (N)`, `Travel (N routes)` and `Cultivate…`, in that order, until the list fits.
  - Typed commands (`talk li`, `go north`, `meditate week`, `practise palm`) still reach folded choices.
- **F4 character sheet:**
  - The log area shows exact numbers: energy (years and stage), qi, purity, nature, physique, deviation, silver, and each known art with mastery stage, compatibility words, and known completeness.
  - The art frame shows the **body chart**: an ASCII figure whose parts are coloured by their worst injury, with each meridian listed by symbol: `●` open, `◐` damaged, `◌` scarred, `×` severed, `·` blocked.
  - F4 again closes it.
- **During combat:**
  - The art frame shows the opponent's portrait with a harm bar underneath.
  - The status bar shows your technique, qi output, qi, and both conditions in words.
- **The main screen** uses words, never raw numbers ("about three years of internal energy", "your qi feels unruly" once deviation passes 60).

## 12. Briefs

- **New kinds:** `cultivated`, `practised`, `opening_meridian`, `rested`, `breakthrough` (with success or failure), `deviation`, `discovery`, `exchange`, `duel_started`, `duel_ended`, `encounter`, `learned`, `studied_manual`, `created_technique`.
- **Player facts, ranked:**
  1. Permanent injuries and severed meridians ("Your right arm never healed straight after the fight with Peng Haoming.").
  2. Current unhealed injuries.
  3. Deviation when high.
  4. Realm and stage ("You are a Second-rate warrior at the middle stage.").
  5. The art in use and its mastery.
- **Exchange briefs** carry the resolved outcome as facts: both intents, who hit, injuries caused, both conditions, and anything revealed. For example: "Your Pale Crane Palm slipped past their guard. They are badly hurt. Your left wrist is sprained."
- The narrator never decides who won. It only phrases what the engine decided.
- All limits hold: at most 6 facts, a prompt of at most 1,200 characters, no entity ids. Truth the player hasn't learned (true manual completeness, hidden constitution) never appears.

## 13. Invariants (added to `debug/invariants.py`)

- `0 ≤ qi ≤ max_qi`; `energy_years ≥ 0`; `0 ≤ deviation ≤ 100`; `silver ≥ 0`.
- Realm is between 0 and 7. `energy_years` lies within [threshold(realm), threshold(realm+1)], and equals the upper bound only at a bottleneck.
- A realm never rises by more than 1 per event.
- Every injury's location is valid, and its severity is 1–5. Permanent injuries have no healing date.
- Every meridian state is valid. A `scarred` meridian never becomes `open`.
- Every `knows` target is a technique entity, and `mastery ≤ completeness`.
- Combat: exactly two participants in the same place, harm 0–100, and the duel ends when either side is broken.
- Briefs never contain `true_completeness` values or an undiscovered constitution's name.

## 14. Testing

- Unit tests per system, headless against a temporary world.
- **Pacing:** the mortal to Third-rate time falls within the target band across 50 seeds.
- **Duel solver:** the §9.5 balance targets.
- **Determinism:** cultivation and fights replay identically (`--replay`), and the fuzz test gains Cultivate, fight, flee, learn and creation actions.
- **Knowledge isolation:** a player with a flawed manual never sees the true completeness in any output until the deviation event reveals it.
- **Migration:** a phase 1 save loads and gets a `wanderer` body, and every rule check passes.

## 15. Out of scope for phase 2

- Death and heirs (phase 4); factions and sect arts (phase 3).
- Spirit locations and pills (phase 5).
- Reputation spreading as rumors (phase 3). Phase 2 only writes the memories rumors will later spread.
- The immortal realms beyond Life-and-Death (named, locked).
