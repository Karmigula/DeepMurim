# DeepMurim Phase 5c: The Alchemy World

**Status:** design approved in brainstorming (2026-09-26). Phase 5 is six sub-phases:
- **5a** items with history (done);
- **5b** alchemy, medicine and poison (done);
- **5c** the alchemy world (this spec);
- **5d** forging and formations;
- **5e** the dao heart;
- **5f** karma and tribulations.

Builds on master at 08545cc:
- 3b's factions, merit, duties, ranks and law; 3c's own sect and its buildings;
- 4a's lives and agendas; 4h's scheming and poisoning;
- 5a's armoury, spoils and famous-keeper seeding;
- 5b's herbs, recipes, refining, pills, residue, poisons and death at a turn's end.

## 1. Goal

The world practises alchemy around the player.
- Sects keep pill halls and herb gardens, drawn on for merit, worked for in duties, and raided at night.
- An Alchemists' Guild ranks alchemists 1-9 by examination; recipes are bought, taught, sold and stolen.
- Physicians heal for silver; famous doctors cure anything, on their own terms; the player can heal others, or poison for hire.
- NPCs refine and take pills in their seasons, lazily.
- Control pills bind servants to masters: the player can be bound, can bind, and can free the bound.

### Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Scope | All four: pill halls and gardens; Guild ranks and physicians; recipe trade and theft; NPC alchemy and control pills. |
| Size | One phase, about eight tasks. |
| NPC alchemy | Lazy and seasonal: numbers and seeds; pill entities only when the player touches them. |
| Pill halls | Merit for pills, alchemy duties, the player's own sect's hall and garden, theft. |
| Roles | Patient, healer, Guild rank, poisoner for hire. |
| Control pills | Victim, master, and the world's masters and servants. |
| Architecture | Reuse the sect machinery: the Guild is a faction, a hall is an armoury-like table, a garden a lazy count. |

### Genre notes

- The Alchemists' Guild with graded alchemists, examinations and pill kings (*Battle Through the Heavens*).
- Divine doctors, the Medicine and Poison valleys, the famous doctor who heals only whom they choose (wuxia).
- The Three Corpse Brain Pill: a monthly antidote from the master, or the worms wake (Jin Yong).
- Gardens of spirit herbs watched by a guardian beast.

## 2. Sect pill halls and herb gardens (`systems/pill_hall.py`)

### 2.1 The pill hall
- **The table:** each sect's hall is a table of pills by grade and effect (qi, healing, antidote, bottleneck), seeded by `pill_hall:{sect}`.
  - A great sect stocks grades 1/2/3 at 6/4/2; any other sect grades 1/2 at 4/2.
  - It restocks to its seed each spring.
  - Bandit-like clans (unorthodox and without a seat) keep no hall.
- **Drawing:** a member draws a pill for `grade × 20` merit.
  - Rank caps the grade: rank 1 grade 1, rank 2 grade 2, an elder grade 3.
  - The pill entity is made only when drawn (the hall is a count).
  - A drawn pill is the member's to keep, even on leaving (a consumable, unlike 5a's armoury gear).
- **Secret recipes:** each sect has 1-2, seeded from the base recipes (§4.1); the hall holds their scrolls.

### 2.2 Alchemy duties
- A third kind of 3b duty, offered only where the sect keeps a hall:
  - **Bring herbs:** N herbs of a named kind that grows on the sect's land (N = 2-4);
  - **Refine:** one pill of a named recipe the player knows.
- Reward: `10 × difficulty` merit (difficulty 1-3), as 3b's duties.

### 2.3 The herb garden
- **Contents:** 3-6 herb names from those growing on the sect's land, each a count, seeded by `garden:{sect}`.
- **Growth:** +2 per herb each season, to a cap of 12. Each season a herb has a 1% chance to age a grade, to "a hundred years" at most.
- **Harvest:** a member takes up to 2 herbs a season, for `5 × (grade + 1)` merit each. The herbs become entities when taken.
- **The player's own sect** (3c) can build:
  - **Herb garden:** 250 silver, upkeep 10; seeded from the land at the seat.
  - **Pill hall:** 300 silver, upkeep 15. Each season, the sect's alchemist disciples fill it: each refines `1-3` pills of grade `⌈rank/2⌉` (§5.4).

### 2.4 Theft
- **When and where:** at night, at a sect's seat (a garden or a hall).
- **Chance:** `0.5 + 0.1 × (the thief's realm − the guard's realm)`, bounded 0.1-0.9. The guard is the sect's strongest member present, or a seeded guard realm.
- **A guardian beast:** a garden holding a hundred-year herb keeps one; it must be fought first (a beast encounter).
- **Caught:** the 3b crime of theft (the fact `stole` against the faction), the sect's hatred, and the goods returned.
- **Unseen:** a fact without a doer ("someone stole from the garden").
- **Taken:** herbs (up to 3) or pills (up to 2), or a secret recipe's scroll (§4.2).

## 3. The Alchemists' Guild (`systems/guild.py`)

- **The faction:** one Guild, a faction of kind `guild`, with a branch in every city. Joining is free, at rank 0.
- **Examinations:**
  - For rank r, the candidate must know a recipe of grade `⌈r/2⌉` or more (a recipe's grade is its pills' grade from Guild-provided herbs: `⌈r/2⌉`).
  - The fee is `50 × r` silver; the Guild provides the herbs.
  - The roll is the candidate's refine chance for that recipe (5b §3.3). Success raises the rank by one.
  - One attempt a season.
- **What rank gives:**
  - herb prices −3% a rank (the herbalist, 5b);
  - Guild recipe scrolls of grade ≤ `⌈r/2⌉` (§4.1);
  - `+0.05 × r` attitude from anyone who knows the rank;
  - the title in rumours and on pages: "a fifth-rank alchemist".
- **NPC alchemists:** `alchemist` NPCs and sect pill masters carry a seeded rank, which rises in their seasons (§5.4).

## 4. Recipes as lore (`systems/recipe_trade.py`)

### 4.1 Scrolls
- A **recipe scroll** is an item (`kind = "scroll"`) with a recipe key and a source: `guild`, `sect`, `master` or `stolen`.
- **Reading** one teaches the recipe at mastery 0.1 (5b's `knows_recipe`), or nothing if known; the scroll is kept.
- **Sources:**
  - the Guild sells scrolls of the base recipes at `100 × grade²` silver, up to the reader's rank (§3);
  - a sect's hall gives its secret recipes to members of rank 2 or more for `50 × grade` merit;
  - an NPC alchemist at attitude ≥ 0.5 with the player teaches one they know, for silver;
  - theft (§2.4).
- **The control pill** (§6) is a secret recipe of unorthodox sects only: it is never sold by the Guild and cannot be discovered by experiment (it is marked `secret` and left out of 5b's `best_match`).

### 4.2 Selling and betrayal
- A scroll sells at the Guild for half its price.
- A sect's secret scroll sells to a rival of its sect for triple: the fact `sold_secret` (the seller, the sect) spreads; the sect hates the seller once it believes it.

## 5. Physicians, the healer, the poisoner, and NPC alchemy

### 5.1 The town physician (`systems/physic.py`)
- One in every town: a seeded NPC of occupation `physician`, made on the first visit to the clinic.
- **Treatment:** an injury for `10 × severity²` silver, healing at three times the speed (a permanent one stays).
- **Cure:** a poison of grade ≤ 3 for `20 × grade²` silver.
- **Reading the body:** 5 silver names every poison's grade and the residue (knowledge, 5b §6).

### 5.2 Famous doctors
- Seeded one per 8 regions (like 5a's famous keepers): a name, a title ("the Ghost Doctor of the Southern Marsh"), and a whim:
  - **gold:** a steep price (`1000` silver);
  - **task:** bring a legendary (thousand-year) herb;
  - **righteous:** treats only the orthodox;
  - **eccentric:** treats one who beats them at go (a comprehension roll).
- **Cures:** any poison, a damaged meridian, a control pill (§6), a permanent injury.
- **Whereabouts:** they wander; asking in a town tells a rumour of where one was last seen (lazy; the doctor is made on first ask in their region).

### 5.3 The player as healer, and as poisoner
- **Healing:** "Offer to treat X" for an injured or poisoned NPC present who does not hate the player.
  - It spends a fitting pill (healing, mending, antidote), or herbs and a roll on the player's alchemy level.
  - Success: attitude +0.3 and a `healed` fact that spreads.
  - Five healings earn the epithet "the healer of <town>"; a known healer is sometimes asked for help in a scene (a sick relative is brought).
- **Poison for hire:** unorthodox NPCs who believe the player knows poison (a `poison_body` or `sold_poison` fact, or a 4h poisoning) offer a contract in conversation: poison a named NPC for silver, through 4h's slip-poison flow and law.

### 5.4 NPC alchemy (a lives agenda, `systems/npc_alchemy.py`)
- **Alchemists** (`alchemist` NPCs, sect pill masters) refine each season: `1-3` pills of grade `⌈rank/2⌉`, added to a count on the person. Their Guild rank rises by one with chance 0.1 a season, to 9.
- **Pill takers:** NPCs of realm ≥ 1 with silver take a pill in a season with chance 0.3:
  - +0.5 years of cultivation (energy) per pill;
  - residue +3 × grade;
  - with residue ≥ 60, a 2% chance of a deviation injury (rarely deadly; the cause `deviation`).
- **Materializing:** an NPC's pills become entities only when the player robs or strips them (5a spoils), inherits from them, or buys from an alchemist's stall.
- One roll per NPC per season; no entities made.

## 6. Control pills (`systems/control.py`)

- **The recipe:** `control`, grade 4, element poison; a secret recipe (§4.1).
- **The bound state:** on the bound person's data, `bound_to = {master, since, fed_until}`.
  - The master feeds an antidote every 30 days: a control pill from the player; an NPC master's feeding is lazy (always, unless the master is dead or absent over a season).
  - **Missed:** each day past `fed_until` does an internal injury (severity 2); past 90 days, death with the cause `control_pill`.
  - Checked lazily in `settle`, and at a turn's end for the player (as 5b's poison death).
- **Freedom:**
  - the master's death (nothing more is owed);
  - a grade-5 antidote;
  - a famous doctor;
  - forcing it out at realm ≥ 5 (a roll, costly in qi).
- **The player bound:**
  - After a real duel lost to an unorthodox master of realm ≥ 3 who spares them, with chance 0.25 (never in a spar or a tournament).
  - The master demands a service each month: carry a message, beat someone, steal (4h-style tasks). Doing it feeds the pill; refusing lets the days run.
  - The sheet shows "bound to <master>".
- **The player as master:**
  - "Force a control pill on them" after defeating and sparing an NPC; it spends a control pill; a crime if the NPC is lawful; a grudge.
  - The bound NPC obeys (3c's disciple orders) but holds the feeling `bound` (hatred); each season, 25% seek a cure (a doctor, lazily).
  - Feeding is a monthly duty; the starved die, and their kin hate the master.
- **The world:** unorthodox NPC masters bind 0-2 NPCs, seeded and lazy, told in rumours. Freeing one (the master's death, a cure) earns the freed one's gratitude and a fact.

## 7. The player (`engine/alchemy_world.py`)

- **Menus:**
  - the sect's pill hall (draw, secret recipes) and garden (harvest);
  - the Guild (join, sit an exam, buy scrolls, sell scrolls);
  - the clinic (treat, cure, read the body) and "Ask after famous doctors";
  - a famous doctor's terms;
  - binding and feeding (the bound as master; the demand as victim).
- **Choices in scenes:** treat an NPC; steal from a garden or hall at night; force a control pill; free a bound NPC; a poison contract in conversation.
- **Pages:** the Guild rank and alchemist titles on the sheet and an NPC's page (as known); "bound to" on the sheet; scrolls on the alchemy page.
- **Typed commands** and help for all of these; journal lines for every new event kind.

## 8. Knowledge vs truth

- A sect's hall and garden are known to its members, or to a thief after a look.
- A secret recipe's existence is a fact its members know.
- A famous doctor is known by rumour; where they were last seen goes stale.
- A Guild rank is known once heard or seen.
- Being bound is known to the bound; others learn it by facts; a bound NPC's master is known once told.

## 9. Debug rules (`check_alchemy_world`)

- Garden counts are within 0-12 and name herbs of the table; hall tables are non-negative.
- Guild ranks are within 0-9.
- `bound_to` names a person; the dead master's bound are free after the next settle.
- No scroll is owned by two people; every scroll names a recipe.
- A control-pill death always has its cause.

## 10. Level of detail and speed

- Halls, gardens, NPC alchemy and NPC binding are numbers and seeds; entities appear only when the player draws, steals, buys, robs, binds or cures.
- Famous doctors are made per region on the first ask.
- **Speed** (CPU time, averaged after `gc.collect()`):
  - a season of 200 NPCs with the alchemy agendas stays within +10% of 5b's season;
  - the hall, garden, Guild and clinic menus are each under 20 ms;
  - the 500-year soak keeps its limits.

## 11. Testing

- **Unit tests** for each system: the hall table and draws; duties; garden growth, harvest and ageing; theft (caught, unseen, the guardian); the Guild's exams and ranks; scrolls (reading, buying, teaching, selling, betrayal); the physician; famous doctors and their whims; healing and the healer's fame; poison contracts; NPC alchemy (refining, taking, deviation); control pills (the bound, feeding, starving, freedom, the three sides).
- **Knowledge:** hall contents, secret recipes, doctors' whereabouts, ranks and bonds shown only as known.
- **Fuzz:** `test_a_wandering_physician`: an alchemist-physician who joins the Guild, draws from a hall, steals, heals, is bound and freed, at random. No crash, no rule broken.
- **The fork guide:** section 12.
- **Performance:** the limits of §10.

## 12. Out of scope

- Pill tribulations: 5f.
- Gu insects: later.
- Pill-refining contests: a later polish (perhaps 5d, beside forging contests).
