# DeepMurim Phase 5d: Forging and Formations

**Status:** design approved in brainstorming (2026-09-28). Phase 5 is six sub-phases:
- **5a** items with history (done);
- **5b** alchemy, medicine and poison (done);
- **5c** the alchemy world (done);
- **5d** forging and formations (this spec);
- **5e** the dao heart;
- **5f** karma and tribulations.

Builds on master at a8e1af9:
- 2b's duels (`fighter_for`, fleeing) and road encounters; 3b's factions and duties; 3c's own sect, its buildings and its gate;
- 4a's lives and agendas; 4d's star iron; 4e's host cities; 4f's formation trials;
- 5a's gear (grades, items, famous weapons, the smith's stall); 5b's alchemy (the model for a craft: lore, mastery, a level);
- 5c's pill halls, gardens and theft, NPC crafts as a lives agenda, and the pattern of commissions and masters.

## 1. Goal

The player forges and lays formations, and the world does too.
- Weapons and armour are forged from materials, held gear is refined a grade, and a masterwork is named and becomes a famous weapon.
- Formations are patterns learnt and mastered, laid with flags: to guard a sect, to fight within, to hide and to cultivate in peace, and to read the ancient arrays of secret realms.
- NPC smiths and formation masters practise their crafts in their seasons, take commissions, and meet once a year in a contest of forging and refining.

### Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Forging | Full smithing: materials into gear, refining held gear, named masterworks that become famous weapons. |
| Formations | All four: sect defences, battle arrays, concealment and wards, secret realm trials. |
| World side | Like 5c: NPC smiths and formation masters with seeded skill that grows, commissions, and a yearly contest of forging and pill refining. |
| Size | One phase, about eight tasks. |
| Architecture | Reuse 5b's craft shape (lore, mastery per thing known, a level from experience) and 5c's (lazy NPC crafts, commissions). |

### Genre notes

- The master smith who forges one great blade in a lifetime and names it; star iron fallen from the sky.
- Formation masters (the geomancers and fortune tellers of wuxia) and their flags: the Eight Trigrams Array, the Heavenly Gate array, arrays that confuse, bind and kill.
- A sect's mountain gate hidden behind a formation; a secluded master's warded cave.

## 2. Materials and the forge (`systems/materials.py`)

- **Materials** are items (`kind = "material"`: a `material` name and its `grade` 0-4), from a table (`systems/data/materials.toml`): iron ingot (0), black steel (1), spirit iron (2), star iron (3), beast bone (1), beast core (2), and the like.
- **Sources:**
  - the smith sells iron ingots and black steel (seeded stock, as 5a's stall), and in a city spirit iron;
  - a slain beast gives its bones, and one of realm 2 or more its core ("Take the beast's bones", as 5b's butchering);
  - 4d's star iron counts as a material of grade 3, and stays a treasure that sells as one (as 5b ruled for prize herbs).
- **The forge:** the player's own forge, or a town smith's to rent (30 silver); the player's own sect can build a `forge` (3c: 300 silver, upkeep 15).

## 3. Forging and refining (`systems/forging.py`)

- **Forging:** a slot and a form (sword, saber, spear, staff; robe, mail, inner vest) and 1-3 materials.
  - The grade is the materials' mean grade, rounded down, plus one at mastery 0.8 or more, at most 4 (divine).
  - The roll: `0.35 + 0.4 x mastery + 0.03 x (strength - 10) + 0.05 x level`, bounded 0.1-0.95.
  - Success makes the item (5a's `make_item`, its maker the player), raises that form's mastery by 0.05 and the forging level's experience by the grade + 1.
  - Failure spends the materials; the worst tenth of failures burns the smith (5b's cracked furnace).
- **Mastery** is per form, starting at 0.1 the first time a form is forged; the **level** is `floor(sqrt(xp / 10))`, as 5b's alchemy level.
- **Refining:** a held weapon or armour and a material of grade at least its grade + 1 raise it one grade (to 4), on the forging roll less 0.2. Failure spends the material; one failure in ten cracks the item (5a's broken).
- **Masterworks:** a weapon of grade 3 or more that the player forged may be named, once: it becomes a famous weapon (5a's `famous_weapons`), its legend "forged by <the player>", a fact that spreads. Three seeded names are offered.

## 4. Formations (`systems/formations.py`)

- **Patterns** (`systems/data/formations.toml`): each has a use, a flag cost, a difficulty and an effect:
  - **defence:** the Heavenly Gate array (a sect's gate), the Veiled Garden ward (a sect's garden and hall);
  - **battle:** the Confusion array, the Binding array, the Killing array;
  - **wards:** the Concealment array, the Seclusion ward.
- **Knowing a pattern:** a `knows_formation` relation whose value is its mastery; the **formation level** is `floor(sqrt(formation_xp / 10))`.
- **Learning:** a formation manual (an item, as 5c's scrolls), bought from a formation master, found in a secret realm, or taught; and passing a 4f formation trial now and then teaches a pattern at 0.1.
- **Flags:** formation flags are items (a count on one item, `kind = "flags"`), bought from a formation master (20 silver each) or forged from spirit iron (grade 2, five to a forging).
- **Laying:** at a place, spending the pattern's flags; the roll `0.3 + 0.4 x mastery + 0.03 x (comprehension - 10) + 0.05 x level - 0.1 x difficulty`, bounded 0.1-0.95. Success lays it (`formations` on the place: `{pattern, owner, until, strength}`, strength `0.5 + mastery / 2`) and raises mastery by 0.05 and the level's experience; failure spends the flags.
- **Realm trials (4f):** a formation trial's chance gains `0.05 x formation level`.

## 5. What formations do

### 5.1 Sect defences
- **The Heavenly Gate array** at the player's own sect's seat: 3c's gate chance falls by `0.5 x strength`, and a defender fights at `1 + 0.2 x strength`; it lasts a year.
- **The Veiled Garden ward** at a sect's seat: 5c's theft chance falls by `0.3 x strength`; it lasts a year.
- **NPC sects:** each great sect keeps a seeded ward of strength 0-1 (`ward:{sect}`), weighed in 5c's theft.

### 5.2 Battle arrays
- Laid in a town, they last until the next dawn, and favour their owner in any fight there:
  - **Confusion:** the owner's foes fight at `1 - 0.2 x strength`;
  - **Binding:** the owner's foes cannot flee;
  - **Killing:** the owner fights at `1 + 0.2 x strength`.
- Applied in `fighter_for` (as 4d's blood moon) and in fleeing; NPC masters lay none (ruling at plan time if needed).

### 5.3 Concealment and wards
- **Concealment:** laid in a town, for 30 days: no avenger, rival or bounty hunter finds the owner there (2b's challenges, 3b's hunters).
- **Seclusion ward:** laid where the owner meditates, for 90 days: cultivation there at `1 + 0.2 x strength`, and a deviation's risk halved.

## 6. The world's crafts (`systems/craft_world.py`)

- **NPC smiths:** blacksmiths by trade carry a seeded skill 1-5 that rises one step with chance 0.1 a season (a lives agenda, one roll, no entities made).
  - A town's best smith of skill 4 or more lifts its stall's grade cap by one (5a).
- **Formation masters:** fortune tellers by trade carry a seeded skill 1-5, rising the same way; they sell flags and manuals of patterns up to their skill, and lay formations on commission.
- **Commissions:**
  - **forging:** a smith forges a named slot and form for `2 x` the stall's price of the grade their skill reaches (grade `min(4, skill - 1)`), ready in ten days, collected from them;
  - **formations:** a master lays a pattern they know at the player's sect or where the player stands, for `100 x difficulty` silver, at strength `0.5 + skill / 10`.
- **The Meet of Hammer and Furnace:** once a year in a host city (4e's), for 30 days: entrants show a forged weapon or a refined pill; a score (`10 x grade + 10 x purity or quality`) against seven seeded masters; the best of each craft wins 500 silver, a title, and a fact that spreads.

## 7. The player (`engine/crafts.py`)

- **Menus:** the forge (forge, refine, name a masterwork); materials and flags on a crafts page; formations (lay a pattern known where one stands, see what is laid here); a smith's and a formation master's commissions and wares; the Meet.
- **Choices in scenes:** take a slain beast's bones or core; lay a battle array before a fight; collect a commission.
- **Pages:** forging mastery and level, formation patterns and level, formations laid here, on a crafts page and the sheet.
- **Typed commands** and help for all of these; journal lines, grammar and rumours for every new event kind.

## 8. Knowledge vs truth

- A formation laid is known to its owner; others see it only as "something is laid here" until they know the pattern.
- An NPC master's skill is told when you talk shop with them (as 5c's alchemist ranks).
- A masterwork's legend spreads as a fact; its maker is known by it.
- The Meet's champions are news.

## 9. Debug rules (`check_crafts`)

- Materials name a row of the table, with a grade in 0-4; flags counts are at least 1.
- Forging and formation masteries are within 0-1.
- Formations laid name a pattern and a person, with strength in 0-1.
- A named masterwork is in 5a's famous index.

## 10. Level of detail and speed

- NPC skills are seeds until they rise; commissions and formations are small records.
- **Speed** (CPU time, averaged after `gc.collect()`):
  - a season of 200 NPCs with the craft agendas stays within +10% of 5c's season;
  - the forge, formations and commission menus are each under 20 ms;
  - `fighter_for` with an array laid stays within +10%;
  - the 500-year soak keeps its limits.

## 11. Testing

- **Unit tests** for each system: materials and their sources; forging, mastery, the level, cracks; refining; masterworks; patterns, manuals, flags, laying; each formation's effect (gate, theft, a duel, fleeing, hunters, seclusion); realm trials; NPC skills; commissions; the Meet.
- **Knowledge:** formations and skills shown only as known.
- **Fuzz:** `test_a_wandering_smith`: a smith and formation master who buys, butchers, forges, refines, names, lays arrays, fights in them, commissions and enters the Meet, at random. No crash, no rule broken.
- **The fork guide:** section 13.
- **Performance:** the limits of §10.

## 12. Out of scope

- **5c's absent masters:** an NPC master away from their bound for a season lets them starve. Deferred to the end of phase 5, by decision (2026-09-28).
- **A smith who dies with a commission unforged:** the silver paid is lost with them (found in review). Taken up with the absent masters at the end of phase 5.
- Weapon spirits and cursed blades: 5e.
- Tribulation arrays and heavenly lightning: 5f.
- Formations on the roads and sieges between sects: later.
