# DeepMurim Phase 5b: Alchemy, Medicine and Poison

**Status:** design approved in brainstorming (2026-09-26). Phase 5 is now six sub-phases:
- **5a** items with history (done);
- **5b** alchemy, medicine and poison (this spec);
- **5c** the alchemy world: sect pill halls and herb gardens, alchemist ranks, physicians and famous doctors, recipe lore, control pills, NPC alchemy;
- **5d** forging and formations;
- **5e** the dao heart;
- **5f** karma and tribulations.

Builds on master at 4a13bce:
- 2's body (energy, purity, deviation, bottleneck, meridians, injuries) and arts (elements);
- 4c's markets;
- 4d's treasure races;
- 4f's secret realms;
- 4h's poisoning;
- 5a's items.

## 1. Goal

The player learns herbs, discovers recipes by experiment, refines pills, and lives with what they do to the body.
- Pills raise cultivation, heal, cure, poison, and temper the body.
- Every pill leaves residue.
- A poison in the body spreads until it is sealed, forced out or cured.
- A practitioner of the poison arts can turn poison into qi, and may become a Poison Body.

### Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Refining | Experiment to discover recipes from herb properties; refine a known recipe with one roll. |
| Pill kinds | Cultivation, healing and medicine, poisons and antidotes, body tempering. |
| Herbs | Gathering, markets, legendary herbs. Sect gardens move to 5c. |
| Toxicity | A residue gauge; active poison apart from it; the poison path and the Poison Body (genre research). |
| The world's alchemy | Sect pill halls, alchemist ranks, physicians and recipe lore: phase 5c. |

## 2. Herbs

### 2.1 What a herb is
- **Entity:** a herb is an entity `kind = "herb"` with `name` (from the herb table), `grade` (0-3 by age: a year, ten years, a hundred years, a thousand years), and the properties of its name.
- **The herb table** (`systems/data/herbs.toml`): about 24 named herbs, each with:
  - `element`: fire, water, wood, metal, earth, poison, or none;
  - `polarity`: yin, yang or balanced;
  - `potency`: 1-5;
  - `toxicity`: 0-5;
  - `terrains`: where it grows;
  - `price`: base silver.
- **The same everywhere:** properties belong to the name, identical in every world.
- **Legendary herbs** (thousand-year ginseng, Heavenly Mountain snow lotus, Nine-Yin Spirit Grass, Blood Dragon Fruit) are the grade-3 forms of named herbs, or unique entries marked `legendary`.

### 2.2 Knowing a herb
- **What the player sees:** a herb's name and age, always. Its properties only once known: the player's `herb_lore` lists the herb names whose properties they know.
- **Tasting** (an action) teaches a herb's properties and spends that herb.
  - A herb of toxicity 3 or more also puts a poison in the body at that strength (§4.2).
  - A poison-path practitioner converts it instead (§4.3).
- **Experience:** a herb used in a successful experiment or refining also becomes known.

### 2.3 Where herbs come from
- **Gathering:**
  - "Search for herbs" in a town's surroundings takes half a day.
  - It finds 0-2 herbs of the region's terrain, with chance by insight and grade by luck: grade 0 at 70%, 1 at 25%, 2 at 5%.
  - A grade-2 find is guarded by a beast (a road-encounter fight) with chance 0.5.
  - A grade-3 herb is never gathered; it is only a treasure.
- **Markets:**
  - A town's herbalist (added to the market page) sells 4-8 herbs of the region, seeded each season, grade 0-1.
  - Prices follow 4c: dearer where the herb does not grow, by the region factor.
  - The herbalist also sells a bronze furnace (200 silver).
- **Legendary herbs:**
  - 4d's treasure-race prize `herb` becomes a grade-2 or grade-3 herb of the table.
  - 4f's secret-realm treasure chambers may hold a grade-3 herb.
  - The Pavilion (4d) hears of a legendary herb found, as a `treasure` fact.

## 3. Recipes, experiments and refining

### 3.1 Recipes
- **Entity:** a recipe is `kind = "recipe"` with:
  - `effect`: one of `qi`, `bottleneck`, `purity`, `healing`, `mending`, `calming`, `cleansing`, `antidote`, `poison`, `venom`, `tempering`;
  - `needs`: the property sums it asks of its herbs;
  - `name`: seeded, like "Azure Sea Qi Pill".
- **The needs:**
  - `element`: the dominant element, from the herbs' potency-weighted elements;
  - `polarity`: yin, yang or balanced, from the herbs' net polarity;
  - `potency`: a minimum total;
  - `toxicity`: a maximum total, or a minimum for poisons.
- **The base recipes** (`systems/data/recipes.toml`): one or two per effect, 16 in all. A world's recipes are made lazily from them, seeded at `recipe:{effect}:{n}`.
- **Knowing:** the player knows a recipe through a `knows_recipe` relation with a `mastery` value (0-1).

### 3.2 Experimenting
- **The action:** "Experiment" at a furnace with 2-4 herbs the player carries. They are spent.
- **Closeness:** the herbs' combined properties are compared with every base recipe. For each recipe, closeness counts the needs met (element, polarity, potency, toxicity) out of four.
  - **4 of 4:** the recipe is discovered (known at mastery 0.1), and the batch yields one pill of it.
  - **3 of 4:** a *hint*, telling which need was missed ("too yang for any calming brew"), recorded in `alchemy_hints`. No pill.
  - **Otherwise:** a sludge. With a total toxicity of 5 or more, the fumes poison the alchemist (§4.2).
- **The seed:** the result is seeded from the herbs and the season, so the same herbs give the same answer.

### 3.3 Refining
- **The action:** "Refine" a known recipe at a furnace with herbs that meet its needs.
- **Chance:** `0.35 + 0.4 × mastery + 0.03 × (comprehension − 5) + 0.05 × alchemy level`, bounded 0.1-0.95.
- **Success:**
  - 1-3 pills (by potency surplus);
  - grade = the herbs' lowest grade + 1, raised by one at mastery 0.8;
  - purity = `0.4 + 0.5 × mastery`, −0.1 per point of the herbs' toxicity over the recipe's allowance.
- **Failure:** ash. A roll below one tenth of the chance cracks the furnace (it breaks) and burns the alchemist (a severity-2 burn on an arm).
- **Growth:** success raises the recipe's mastery by 0.05 (to 1.0) and the alchemy experience by the grade. The alchemy level is `floor(sqrt(experience / 10))`.
- **Furnaces:** a `gear`-like item `kind = "furnace"` owned by the player; or an apothecary's, used for 20 silver in a town with an herbalist. A refining takes two watches.

## 4. Pills, residue and poison

### 4.1 Pills
- **Entity:** a pill is an item `kind = "pill"` with `effect`, `grade` (1-5), `purity` (0-1), `recipe`, and `maker`.
  - 4d's existing pills (`qi_years`) are read as qi pills of grade 2; nothing is converted.
- **Swallowing:** the pill works at `potency = grade × (1 − residue / 150)`.

| Effect | What it does |
|---|---|
| `qi` | +0.5 × potency years of energy |
| `bottleneck` | removes a bottleneck, or +0.1 × potency to the next breakthrough's chance |
| `purity` | +0.02 × potency purity (bounded 1.0) |
| `healing` | halves the remaining healing time of the potency worst injuries |
| `mending` | one damaged meridian heals; at grade 4 or more, a severed one becomes damaged |
| `calming` | −10 × potency deviation |
| `cleansing` | −10 × potency residue |
| `antidote` | cures active poisons of grade ≤ the pill's |
| `poison` | a brewed poison (§4.2) to be slipped or taken |
| `venom` | coats the wielded weapon: its next 3 wounds poison at the venom's grade |
| `tempering` | one medicinal bath (§4.5) |

### 4.2 Active poison
- **In the body:** the body's `poisons` is a list of `{grade, strength, source}`.
- **Each watch:**
  - each poison deals internal harm (an internal injury of severity `grade`, once a day);
  - its strength falls by 1;
  - if strength reaches 0 it is spent;
  - a poison of grade 4 or more that outlasts the victim's `realm + 2` days kills them (cause `poisoned`).
- **Sealing the acupoints:** any fighter of third-rate realm or above can seal. It halts every poison for 4 watches, once a day.
- **Forcing out:** first-rate realm or above.
  - Costs 10 qi.
  - Removes a poison whose grade ≤ realm index − 1, else halves its strength.
- **Antidotes:** cure every poison of their grade or lower.
- **Deliveries:**
  - tasting toxic herbs;
  - experiment fumes;
  - weapon venom;
  - venomous beasts;
  - poison-path strikes (§4.3);
  - 4h's slipped poison, now a brewed poison pill. An untreated grade-4 poison kills a leader in the night, as 4h's did.
- **The index:** the meta row `poisoned` lists the entities with active poisons. Only they are ticked.

### 4.3 The poison path
- **The element:** `poison` becomes an art element. Poison-element arts are seeded for demonic cults and unorthodox clans (4d's favoured forms stay).
- **Absorbing:** a practitioner of a poison art (mastery 0.3+) who takes a poison, or a toxic herb, absorbs it instead of suffering it.
  - `conversion = min(0.9, 0.3 + 0.5 × mastery + 0.05 × realm)` of its grade × strength becomes qi (`0.02` years per point).
  - The rest is suffered.
- **Their strikes:** a poison art's wound puts a poison of grade `1 + mastery × 3` in the target at strength 2.

### 4.4 The Poison Body
- **Venom:** absorbed poison adds to the body's `venom` (0-100) by the converted amount.
- **Turning:** at 60 the body becomes a **Poison Body** (`constitution = "Poison Body"`, told as a fact: `poison_body`).
- **Gifts:**
  - immune to poisons of grade 3 or less;
  - its blood is venom: an unarmed or claw hit on it poisons the striker (grade 3, strength 2);
  - drinking its blood poisons.
- **Costs:**
  - healing and mending pills work at half;
  - a town that believes the `poison_body` fact fears the bearer (a reputation effect: righteous factions distrust them, ordinary folk keep away).

### 4.5 Residue and tempering
- **Residue:** `residue` (0-100) on the body.
  - Each pill adds `grade × (1 − purity) × 10`.
  - It fades by 2 a week (twice as fast for a purity over 0.8).
  - Above 60, each pill adds a deviation risk (+15 deviation with chance `(residue − 60) / 40`).
  - Above 90, a meridian may be damaged (chance 0.3 a pill).
- **Tempering baths:**
  - A bath takes a day at an inn (30 silver) or at a sect the player belongs to.
  - It raises one physique stat by 1. A stat can be raised by baths at most 3 times in a lifetime.
  - Pain: a severity-1 internal injury with chance 0.3.
  - A grade-3 legendary herb in a bath may awaken a constitution the body lacks (chance 0.2), from a table fitting its element.

### 4.6 Venomous beasts
- **The encounter:** in marsh and forest regions, a road encounter may be a great venomous beast (a python, a red toad, a golden centipede) with chance 0.03.
- **The fight:** a beast fight, whose bites poison (grade 4).
- **The prize:** slain, it can be butchered: its blood (drunk, it gives +20 poison resistance (grade-2 poisons ignored) and 1 qi year) or its inner core (+3 qi years, and venom +10 for a poison-path practitioner).
- **Knowledge:** a venomous beast killed is told as a fact.

## 5. The player

- **The Alchemy page:**
  - known recipes (name, effect, mastery);
  - herbs carried (name, age, and properties if known);
  - hints;
  - alchemy level;
  - residue, venom, and active poisons as known.
- **Choices:**
  - search for herbs (in the wilds), taste, experiment, refine, swallow a pill;
  - take a bath;
  - coat your blade;
  - seal acupoints, force the poison out;
  - drink the blood or take the core (after a venomous beast's fall);
  - buy herbs or a furnace (the market's herbalist), rent a furnace.
- **Character sheet:** residue, venom, active poisons as known, and the Poison Body.
- **Typed commands** and help for all of these.

## 6. Knowledge vs truth

- A herb's properties are shown only once known (tasted or used).
- An active poison shows only as "you feel poison in your blood (grade unknown)" until an antidote, a force-out or tasting names its grade.
- A recipe's needs are shown once discovered; a hint names only the need that failed.
- The `poison_body` fact spreads like any rumour; the page shows the player their own Poison Body plainly.

## 7. Debug rules (`check_alchemy`)

- Every herb names a herb in the table, with a grade of 0-3.
- Every pill has an effect of the known set, a grade of 1-5 and a purity of 0-1.
- `residue` and `venom` are within 0-100.
- Every active poison has a grade of 1-5 and a strength above 0, and its bearer is in the `poisoned` index (and vice versa).
- A Poison Body has venom ≥ 60 at the turning.
- A recipe's mastery is within 0-1.

## 8. Level of detail and speed

- **Who alchemizes:** NPCs neither gather, refine nor take pills in 5b (phase 5c).
- **Poison ticks** run only over the `poisoned` index; residue fades lazily when a body is read (as 2's healing does).
- **Speed** (CPU time, averaged after `gc.collect()`):
  - an experiment or a refining is under 5 ms;
  - the poison tick with 20 poisoned is under 5 ms a watch;
  - the 500-year soak keeps its limits.

## 9. Testing

- **Unit tests:**
  - the herb table and properties; tasting and its poison;
  - gathering by terrain and the guarded find; the herbalist's stock and prices;
  - legendary herbs as prizes;
  - experiments: discovery, hints, sludge, the same seed;
  - refining: the chance, mastery, failure, the cracked furnace;
  - every pill's effect;
  - residue: dulling, thresholds, fading;
  - active poison: spread, sealing, forcing out, antidotes, death; 4h's poisoning through it;
  - the poison path: conversion, strikes; the Poison Body: its gifts and costs;
  - tempering baths and their limits; venomous beasts.
- **Knowledge:** properties hidden until known; a poison's grade hidden until named.
- **Fuzz:** `test_a_wandering_alchemist`: gathers, buys, tastes, experiments, refines, swallows and fights at random. No crash, no rule broken.
- **Performance:** the limits of §8.

## 10. Out of scope (phase 5c and later)

- The alchemy world:
  - sect pill halls and herb gardens;
  - alchemist ranks and examinations;
  - physicians and famous doctors;
  - recipe teaching, selling and stealing;
  - control pills;
  - NPC alchemy, and NPCs taking pills.
- Pill tribulations (heaven's lightning on a divine pill): phase 5f.
- Gu insects.
