# DeepMurim Phase 5e: The Dao Heart

**Status:** design approved in brainstorming (2026-09-28). Phase 5 is six sub-phases:
- **5a** items with history (done);
- **5b** alchemy, medicine and poison (done);
- **5c** the alchemy world (done);
- **5d** forging and formations (done);
- **5e** the dao heart (this spec);
- **5f** karma and tribulations.

Builds on master at 78e2f25:
- 2a's body (`insight`, `deviation`, `flags`) and breakthroughs, 2b's duels and verdicts, road challenges and avengers;
- 3b's factions and their paths (righteous, ruthless), 3c's sworn followers; 4a's lives and agendas; 4b's kin, graves and grief roles;
- 4d's dao resonance and tribulation lightning; 5a's gear, deeds, famous weapons and `DEED_HOOKS`;
- 5b's poisoning and healing, 5c's contracts and theft, 5d's smiths (who appraise a blade).

## 1. Goal

The player's heart is shaped by what they do, and weighs on how far they go.
- A **dao heart** gauge, steady or troubled, and a **lean** between the righteous and the ruthless, both moved by deeds.
- **Heart demons** gathered from guilt, grudges, fear and grief rise at a breakthrough, to be faced or buried.
- **Epiphanies** grow a **dao** of a form or an element; a dao completed is the "return to the origin" the last realm asks for.
- **Oaths** sworn on the heart steady it when kept and crack it when broken.
- **Weapon spirits** wake in blades that have killed enough, and **cursed blades** hunger for blood.
- The world's masters carry hearts too: some go mad with their demons, some are enlightened, and oaths are news.

### Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Pillars | All four: heart demons; epiphanies and daos; oaths on the heart; weapon spirits and cursed blades. |
| The heart | A steadiness gauge, plus a lean between righteous and ruthless shaped by deeds (separate from sect membership). |
| World side | Like 5c/5d: NPC hearts seeded lazily, masters driven mad by their demons (news), NPC epiphanies, oaths in rumour. |
| Size | One phase, about eight tasks. |
| Architecture | The heart is person data (`heart`), not body: NPCs have none until something writes it, and their seeded one is read from traits. Deeds move it through listeners on existing events, from one table. |

### Genre notes

- The dao heart (道心): a cultivator whose heart wavers cannot break through; one whose heart is firm cuts through doubt.
- Heart demons (心魔) at the gate of a breakthrough: the face of the one you killed, the master you failed.
- Enlightenment under a waterfall, in the middle of a duel, at a master's passing; "returning to the origin" (返璞歸眞) as the peak of a martial way.
- An oath sworn on one's dao heart; heaven hears it.
- The demonic blade that drinks blood and whispers; the sword spirit that knows its master's hand.

## 2. The heart (`systems/heart.py`)

- **State:** person data `heart = {steady, lean, demons, daos, oaths}`; `steady` 0-100 (starts 60), `lean` -100 (ruthless) to 100 (righteous) (starts 0).
- **NPCs:** no `heart` until written; the seeded heart (`heart:{key}`) reads traits: kind and honest lean righteous, cunning and greedy ruthless (each ±20, jitter ±15); steadiness 40-80, less 15 for hot-tempered and 10 for proud.
- **Deeds** (`systems/data/heart_deeds.toml`): each row a kind of event, the actor it moves, `lean` and `weight`. Examples:
  - killing someone who yielded, poisoning for pay, a hall theft, framing, a murder plot: ruthless;
  - sparing a beaten foe, healing, curing a poison, paying a debt, returning an heirloom: righteous;
  - killing a foe in a fair duel, a beast: none.
- **Steadiness moves with the lean:** a deed that goes the way one leans (lean and deed of the same sign, |lean| ≥ 20) adds `weight`; one against it takes `2 x weight` ("the heart doubts"); a neutral heart is moved by neither. Meditation restores 1 a week toward 60.
- **Effects:**
  - a breakthrough's chance `+ 0.002 x (steady - 50)` (±0.1);
  - deviation gained `x (1.5 - steady / 100)`;
  - under 20, the heart is **shaken**: no epiphany comes, and the worst demon may stir at any meditation (5% a week: deviation +10).
- **Words:** steadiness as "unshaken / firm / steady / wavering / troubled / shaken"; the lean as "righteous / upright / unaligned / hard / ruthless", on the sheet and the heart page.

## 3. Heart demons (`systems/demons.py`)

- **A demon** is `{kind, whom, weight 1-3, since}`, at most five (the lightest goes when a sixth comes):
  - **guilt:** killing one who yielded or was unarmed, a murder plot, a broken oath, a master betrayed (walking out or exiled);
  - **grudge:** being robbed, crippled or beaten to the edge of death by someone (their name the `whom`);
  - **fear:** a life-and-death fight lost and survived, a tribulation that crippled;
  - **grief:** a master, a spouse, kin or a sworn sibling dead (4b's grief roles).
- **Laid to rest by deeds:** a grudge when its `whom` is beaten or dies; grief by paying respects at the grave (4b's `buried_at`), or after three years; guilt by amends (silver to the dead one's kin, or healing a stranger, weight 1 each); fear by winning a life-and-death fight.
- **At a breakthrough** (to Second-rate or beyond), with a demon carried, the heaviest rises: a **heart trial** before the roll:
  - **face it:** `0.3 + steady / 200 + 0.03 x (comprehension - 10) - 0.1 x weight`, bounded 0.1-0.9; success lays it to rest, steadiness +10 and insight +10; failure is a failed breakthrough and deviation +20;
  - **bury it:** the breakthrough goes on at -0.1 and steadiness -5; the demon stays, one heavier;
  - **turn back:** no breakthrough; nothing lost.
- **Knowledge:** the player knows their own demons (the heart page names them). An NPC's demons are seeded and hidden.

## 4. Epiphanies and daos (`systems/daos.py`)

- **Daos:** one per martial form (sword, saber, spear, staff, palm, fist, finger, footwork) and per element (metal, wood, water, fire, earth); comprehension 0-1 in `heart.daos`.
- **Epiphanies** (a roll, with steadiness 20 or more):
  - practising in a 4d dao resonance: 20% a week, to the form of the art;
  - winning a life-and-death fight: 30%, to the form fought with;
  - an art brought to Great Completion: always, to its form and element;
  - watching a tournament bout or a master's duel (4e): 5%, to the winner's form;
  - meditating with the lean past ±60: 2% a week, to the element of one's heart method.
- **Gain:** `0.05 + 0.02 x (comprehension - 10)`, bounded 0.02-0.15; told as a line and a journal entry.
- **Effects:** practice of an art of that form or element `x (1 + dao)`; in a fight, the form's `fighter_for` factor `x (1 + 0.1 x dao)`.
- **Returning to the origin:** a dao reaching 1.0 sets 2a's `returned_to_origin` flag. Life-and-Death's requirement was unreachable until now.

## 5. Oaths (`systems/oaths.py`)

- **Kinds:**
  - **vengeance** on a named person the player holds a grudge against: they must die, by any hand, within three years;
  - **protection** of a named person: they must not die by violence within a year;
  - **abstinence:** no killing for a season.
- **Swearing** (from the heart page): steadiness +5; the oath is `{kind, whom, until, sworn_at}`; a fact that spreads ("swore on their dao heart to ...").
- **Kept** (vengeance done, or the time ran out with protection or abstinence unbroken): steadiness +15, lean +10 for protection (righteous), a fact.
- **Broken** (the time runs out on vengeance, the protected dies by violence, the abstinent kills): steadiness -30, a guilt demon of weight 3, a fact that spreads ("broke an oath sworn on their dao heart"); `reputation` counts it as dishonour.
- At most three open oaths.

## 6. Weapon spirits and cursed blades (`systems/blade_spirits.py`)

- **Kills:** a materialized weapon counts `kills` (a `died` listener, as 5a's deeds).
- **A spirit wakes** in a weapon of grade 2 or more at 12 kills (a named masterwork at 6): `spirit = {nature, bond}`, its nature from the wielder's lean then: under -30 **bloodthirsty**, else **loyal**.
  - **loyal:** the wielder fights `x (1 + 0.1 x bond)`; the bond grows 0.1 a kill, to 1; another hand gets nothing from it.
  - **bloodthirsty:** `x 1.15` for anyone; a season with no kill takes steadiness -5 from the wielder (it whispers); at steadiness under 30, the "spare" verdict is refused ("the blade will not be sheathed dry").
- **Cursed blades:** one famous weapon in five (5a's index, seeded `curse:{item}`) is bloodthirsty from its making.
- **Knowledge:** a spirit is known to its wielder after a season of wielding; a smith of skill 3 or more (5d) tells a blade's spirit or curse in conversation ("Have them look at your blade").
- A spirit is lost when the blade breaks.

## 7. The world (`systems/heart_world.py`)

- **Madness:** a lives agenda; an NPC of Second-rate or more whose seeded heart is under 30 steadiness goes mad with 1% a season (one hash): a `heart_madness` event; `mad_until` a year on, a fact that spreads ("went mad with their demons").
  - A mad master in the player's town calls them out as an avenger does (3b's `HUNTER_HOOKS`), fights at `x 1.2`, and never spares.
  - At `mad_until`, they recover (60%) or die of it (seeded).
- **Epiphanies:** 4d's dao resonance adds 0.2 to the enlightened master's dao of their best form (written into their `heart`).
- **Oaths in rumour:** the player's oaths sworn, kept and broken are facts; NPC avengers (2b) are said to have sworn on their hearts in their challenge lines.

## 8. The player (`engine/heart.py`)

- **The heart page:** steadiness and lean in words, demons carried, daos known (by comprehension), oaths open, a blade's spirit if known.
- **Choices:** swear an oath (a menu of kinds and people: grudges for vengeance, companions and kin for protection); pay respects at a grave (at the place of a grieved-for dead); the heart trial at a breakthrough (face, bury, turn back); amends to a dead one's kin (in conversation, from the heart's guilt).
- **Sheet:** a line for steadiness and lean, and the best dao.
- **Typed commands** (`heart`, `swear`, `respects`, `face`, `bury`, `turn back`), help, journal lines, grammar and rumours for each new kind.

## 9. Knowledge vs truth

- The player's own heart is shown in words, never numbers (demons by kind and whom).
- NPC hearts are hidden; madness and oaths are known as facts.
- A blade's spirit and curse are known as in section 6.

## 10. Debug rules (`check_heart`)

- Steadiness in 0-100, lean in -100 to 100, daos in 0-1; at most five demons, each of a kind of the four with weight 1-3; at most three open oaths, each of a known kind.
- A spirit's nature is loyal or bloodthirsty and its bond in 0-1; kills are at least 0.
- A mad NPC has a `mad_until` and is not dead.

## 11. Level of detail and speed

- NPC hearts are seeds until written; madness is one hash a season per master.
- **Speed** (CPU time, averaged after `gc.collect()`):
  - a season of 200 NPCs with the heart agenda stays within +10% of 5d's;
  - the heart page and the oath menu are each under 20 ms;
  - the deed listeners add under 10% to a duel's resolution;
  - the 500-year soak keeps its limits.

## 12. Testing

- **Unit tests:** the gauge and lean from deeds, the seeded NPC heart, steadiness's effects on breakthroughs and deviation; demons gathered and laid to rest, the heart trial; epiphanies and their effects, returning to the origin and the last realm; oaths sworn, kept and broken; kills, a spirit waking, loyal and bloodthirsty effects, cursed blades, the smith's telling; madness and recovery.
- **Knowledge:** the heart in words; hidden spirits and NPC hearts.
- **Fuzz:** `test_a_troubled_heart`: a fighter who kills and spares, swears and breaks oaths, breaks through and faces demons, and carries a cursed blade, at random. No crash, no rule broken.
- **The fork guide:** section 14.
- **Performance:** the limits of section 11.

## 13. Out of scope

- **Karma** as heaven's ledger, and tribulations that weigh it: 5f (the lean is the heart's own reading, not heaven's).
- **5c's absent masters** and **a smith who dies with a commission unforged:** the end of phase 5.
- Sword intent as a visible technique, and demonic arts that feed on the heart: later.
