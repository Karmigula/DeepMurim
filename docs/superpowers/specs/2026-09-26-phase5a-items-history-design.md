# DeepMurim Phase 5a: Items with History

**Status:** design approved in brainstorming (2026-09-26). The first of phase 5's five sub-phases:
- **5a** items with history (this spec);
- **5b** alchemy and medicine;
- **5c** forging and formations;
- **5d** the dao heart;
- **5e** karma and tribulations.

Builds on master at dd9b4bd: 2's combat, 3a's rumours, 3b's law, 4b's lineage, 4c's markets, 4e's rankings and wagers, and 4f's secret realms.

## 1. Goal

Weapons and armour become real things that matter in a fight and carry their past.
- A blade's grade strengthens the arts of its form. Fighting a sword art bare-handed is weaker, and armour softens wounds.
- Every notable item remembers its maker, its owners and its deeds.
- A few famous weapons exist in the world. They are known by legend, change hands by duel, death and sale, and are ranked each spring.

### Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Phase 5's split | Five sub-phases, 5a to 5e, in the order above. |
| How much items matter | Mechanics and story: grades in combat, plus provenance and legend. No durability, no growing weapons. |
| Where gear comes from | Markets, the fallen, the sect armoury, and famous weapons. |
| NPC gear | Lazy: a seeded grade on the person, made a real item only when it matters. |

## 2. Gear and grades

### 2.1 Grades
| Grade | Index | Power | Armour takes off |
|---|---|---|---|
| iron | 0 | ×1.0 | 10% |
| fine | 1 | ×1.15 | 15% |
| spirit | 2 | ×1.3 | 20% |
| treasure | 3 | ×1.5 | 25% |
| divine | 4 | ×1.8 | 30% |

### 2.2 Weapons
- **Kinds:** a weapon's `form` is one of the weapon forms of 2's arts (`sword`, `saber`, `spear`, `staff`).
- **Arts that need no weapon:** palm, fist, finger and footwork arts.
- **Power of an art:** a weapon art is multiplied by the wielded weapon's grade power when the forms match.
  - A near form (sword↔saber, spear↔staff) counts at ×0.85 of that.
  - With no weapon, or a far form, the art fights at ×0.6.
- **Breakage:** when a weapon meets one two or more grades above it in a duel exchange, the lesser weapon breaks with chance 0.05 an exchange. It stays as a broken item (`broken = true`, power as unarmed) with its history.

### 2.3 Armour
- **One slot**, one of `robe`, `mail`, `inner_vest`.
- **Effect:** the grade's share (2.1) is taken off each wound's severity before it is recorded.

### 2.4 Items
- **What an item is:** a gear item is an entity of `kind = "gear"`. Its data:
  - `slot` (`weapon` or `armour`), `form` (a weapon's), `grade` (0-4), `maker` (a person, a faction or none), `made_at`;
  - `owners`: the owners in order, `{person, since, how}`, where `how` is `bought`, `taken`, `drawn`, `inherited`, `won`, `given`, `found` or `made`;
  - `deeds`: up to 12 event ids, the weightiest kept;
  - `famous` (bool), `epithet` (or none), `armoury` (the faction it belongs to, if drawn), `broken`.
- **Ownership:** the owner holds it through `owns`, as 2's manuals are held. A person has at most one `wields` relation (to a weapon) and one `wears` relation (to armour), each to an item they own.

### 2.5 Lazy NPC gear
- **Seeded gear:** a person's data may carry `gear = {weapon: grade | None, armour: grade | None, form}`, seeded at `gear:{person}` from their rank and realm.
  - The weapon form is their best art's (none for a palm, fist, finger or footwork art).
  - Unranked commoners carry none. Disciples carry iron, keepers fine, elders spirit. A sect leader of a great faction carries treasure grade (or their famous weapon, §3).
- **Only a grade until it matters:** seeded gear is not an entity. It is used in combat as a grade.
- **Made real:** it becomes an item (`materialize_gear`) when:
  - it is taken, bought from them, or inherited;
  - it is looked at on an item page;
  - its wielder dies at the player's hand.
- **Its history then** starts with `owners = [{person, since: now, how: "carried"}]`, and the person's `gear` points at the item.

## 3. Provenance and legend

### 3.1 Deeds
- **What makes a deed:** a weapon wielded in a notable event gains the event's id in `deeds`. Notable events are:
  - killing someone of rank 3 or more, or two realms or more above the lowest;
  - winning a duel against a ranked fighter (4e's rankings);
  - winning a tournament final;
  - killing a sect leader.
- **Which are kept:** the weight of a deed is its fact's weight. The 12 weightiest are kept.
- **For a lazy NPC weapon,** the deed is kept on the person's `gear` as `deeds` and carried over when the item is made real.

### 3.2 Legend as facts
- **Deeds are told:** each deed of a famous weapon, or of any weapon of grade 3 or more, records a fact about the item (`predicate = "wielded_in"`, `subject` the item, `object` the event's first actor, a variant naming the wielder and the deed). The fact spreads by 3a's rumours.
- **Recognition:** a person knows a weapon when they see it if they believe any fact about it.
  - When the player enters a scene carrying a weapon someone there recognizes, that person reacts:
    - a `proud` or `greedy` fighter within one realm of the player may challenge them for it (4e's wager duel, the weapon at stake) with chance 0.2 per scene;
    - kin of anyone the weapon killed gain a hatred memory of the player (not indelible);
    - a member of the faction it was taken from demands it back, once per scene: the player hands it over (the faction's stance toward them rises by 0.1), or refuses (it falls by 0.2).
  - The player recognizes weapons the same way. The scene brief names them.

### 3.3 Famous weapons
- **Seeded per region** at `famous:{region}`: two or three named weapons, treasure or divine grade, each with a seeded name ("Frost Moon Sword", "Nine Dragons Spear"), a founding legend (a fact made at seeding), and a keeper:
  - a great sect's leader (the sect's treasure);
  - a clan's heirloom (the clan's leader, or lost: `lost_at` a place);
  - a wandering master;
  - buried with a 4f secret-realm master: that realm's weapon becomes famous the first time it is taken.
- **Always entities:** famous weapons are items from the start. The meta row `famous_weapons` lists them.
- **How they change hands:**
  - a wager duel for the weapon;
  - death: it passes to the killer if the killer takes it, else to the heir (4a's kin, 4b's lineage), else it lies where they fell (`lost_at`);
  - sale (a famous weapon costs 20× its grade's market price);
  - taken from the fallen;
  - given.
- **Heirlooms:** a clan heirloom returned to its clan earns the clan's lasting favour: a `grateful` indelible memory for its leader, and stance +0.3 toward the player's sect. Carrying it openly makes the clan's members hostile (as §3.2's demand).
- **Epithets:** a famous weapon that kills someone of fame (a ranked fighter, a sect leader) gains an epithet ("which slew the Blood Demon"), kept on the item and told in its legend.
- **The Hundred Weapons Chronicle:** each spring the Pavilion (4e's rankings) ranks the famous weapons by grade, then by the weight of their deeds, as facts of the rankings' kind (`predicate = "weapon_ranked"`). A weapon entering the list, or rising into the top ten, is news.

### 3.4 Far away
- Famous weapons change hands only when their owner dies (4a's life clock) or a tournament is summarised (4e): to the heir, or to the winner if the final was a wager.
- Their legend grows by the facts those summaries make. Lazy NPC gear is never made real far away.

## 4. Sources

### 4.1 Markets
- **The smith's stall:** a town's market (4c) gains one, stocked each season (seeded `smith:{town}:{season}`).
  - 3-6 weapons of the forms of the arts common in the region, and 1-3 armours.
  - Grades are capped by the town's size: a village sells iron, a town up to fine, a city up to spirit.
- **Prices:** base by grade (iron 20, fine 60, spirit 250 silver; armour ×0.8), moved by 4c's price level.
- **Selling:** the player sells gear back at half price. Famous weapons are sold only to an NPC buyer at a city (a sect leader or a rich merchant), at 20× the grade price.
- **Stock is lazy:** a stall's stock is only a seeded list until something is bought (then made an item, `maker` a seeded smith name).

### 4.2 The fallen
- **Taking:** after the player wins a duel or a road fight, a choice "Take their weapon" (and "Take their armour") appears while the loser is present (or lies dead).
- **Consequences:**
  - The loser, if alive, gains an indelible `wronged` memory; `proud` losers gain `hatred`.
  - Taking from someone lawful (not a bandit, not a demonic cult member, not an outlaw with a bounty) is theft under 3b's law: a `stole` fact (weight 1.5) in the town.
- **NPC wins:** an NPC who defeats the player may take the player's weapon: `greedy` or `ruthless` ones do, with chance 0.5.

### 4.3 The sect armoury
- **The armoury** is a grade table on the sect, `armoury = {grade: count}`, seeded from its tier and power. It is not items.
- **Drawing:** a member draws one weapon (of the form of their best weapon art, or chosen) and one armour, at most:
  - rank 1: iron; rank 2: fine; rank 3: spirit; an elder: treasure, once per person;
  - only if the table has one left.
  - The item is made then, with `armoury = faction` and `maker` the sect.
- **Returning:** an armoury item can be returned (the count goes back up).
- **Leaving with it:** leaving the sect while holding one (3b's leaving or expulsion) is theft: a `stole` fact, and the sect's stance toward the player falls by 0.1.
- **Seasons:** the armoury is restocked by one of its lowest grade a season, up to its seed.

### 4.4 Wagers and lineage
- **Wagers:** 4e's wager duel gains a stake of a weapon or armour, the player's or the opponent's. Staking an armoury item is refused.
- **Lineage:** 4b's heir inherits the wielded weapon and worn armour first, then other gear, with `how = "inherited"`.

## 5. The player

- **Inventory** (a page): wielded weapon and worn armour, other gear, and treasures. Each line shows name, grade, and a history line ("carried by Mok Ho; taken at Azure Village").
- **Actions:** `wield <item>`, `wear <item>`, `unwield`, `inspect <item>` (the item page), take (§4.2), draw and return (§4.3), buy and sell (§4.1).
- **The item page:** kind, grade, maker (if known), owners as known, deeds as known, epithet, and a "known as" line from the legend the player believes.
- **Character sheet:** the wielded weapon and its multiplier for each art ("Frost Moon Sword: sword arts ×1.8, saber arts ×1.53").
- **The sky page:** the Hundred Weapons Chronicle, the entries the player has heard.
- **Scene brief:** "X carries the Frost Moon Sword" when the player recognizes it.
- **Help and typed commands** for the above.

## 6. Knowledge vs truth

- An item's page shows only the deeds and owners the player witnessed or believes facts about. The maker is shown if the player bought it, drew it, or believes a fact naming them.
- Recognition (§3.2) reads beliefs only.
- `check_people` accepts names from item legends the player believes.

## 7. Debug rules (`check_items`)

- Every gear item has at most one owner (`owns`), and the owner's name is last in `owners` (unless it lies lost, `lost_at` set).
- A `wields` or `wears` relation points at an item its source owns, of the right slot, and there is at most one of each per person.
- The meta row `famous_weapons` lists exactly the famous items, each once.
- Every id in `deeds` is a real event.
- A sect's armoury counts are non-negative and no higher than its seed.
- A person's `gear` pointing at an item points at an item they own.

## 8. Level of detail and speed

- Lazy gear adds no entity for an NPC who never matters. Famous weapons are the only NPC items made at seeding: 2-3 a region.
- Speed (CPU time, `time.process_time`, averaged over 10 calls after `gc.collect()`):
  - reading gear adds under 1 ms to a duel's setup;
  - recognition adds under 2 ms to a scene;
  - the Chronicle's spring survey takes under 20 ms;
  - the 500-year soak keeps its limits.

## 9. Testing

- **Unit tests:**
  - grade power, near forms and bare hands in combat; armour's share off wounds; breakage;
  - lazy gear seeded, and made real on each trigger;
  - deeds kept and capped; legend facts; recognition and its reactions;
  - famous weapons seeded, passed on death, won by wager, returned as heirlooms, renamed by an epithet; the Chronicle;
  - the smith's stall (caps, stock, prices, selling); taking from the fallen (theft, memories); the armoury (drawing, returning, leaving with it); lineage.
- **Knowledge:** the item page shows only known deeds; the brief names only recognized weapons.
- **Far:** a famous weapon passes to an heir on a far death.
- **Fuzz:** `test_an_armed_wanderer`: buys, draws, takes, wields, wagers and sells at random; no crash, no rule broken.
- **Performance:** the limits of §8.

## 10. Out of scope

- Forging (5c) and alchemy (5b).
- Cursed or bloodthirsty blades (5d's heart).
- Weapons that grow with or choose their wielder.
- Durability and repair.
- Hidden weapons and thrown darts.
- More than one armour slot.
