# DeepMurim Phase 3b: Factions — Joining, Ranks, Duties, Politics, Law

Date: 2026-09-23
Status: Draft, awaiting user review
Parent spec: `2026-09-22-deepmurim-design.md` (§5.6, §6.0, §8 item 3)
Builds on: phase 3a (merged at `b930481`): facts, beliefs, rumours, attitude, reputation, kin, masks.
Next: **3c**, founding your own sect (land, resources, disciples, a faction that acts).

## 1. Goal

The martial world is organised into factions. Some are famous across the world, others only in their valley, and all of them are made of real NPCs. You can join one, prove yourself, rise through its ranks by doing its work, learn its arts, and get caught up in its politics. Its enemies become yours. The law hunts the notorious. Leaving is not always allowed. Everything a faction knows about you comes from 3a's rumours, so what you do and who sees it decide how each faction treats you.

Every system:
- reports its state to the narrator as `Brief` facts that Haiku can phrase (parent §6.0);
- adds rules to `debug/invariants.py`;
- is covered by the fuzz test.

### Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Split | **3b:** factions in the world, joining, trials, ranks, duties, arts, taboos, politics, enemies by association, law, leaving and spying. **3c:** founding. |
| Types | Orthodox sects, demonic and unorthodox factions, martial clans, the Beggars' Sect, merchant guilds, the imperial office and the Orthodox Alliance (all four groups chosen). |
| Member life | Duties and merit, sect arts and library, internal politics, enemies by association (all four chosen). |
| Membership | **One martial faction plus side ties.** Guild, clan and imperial ties can stack with it. Leaving needs a release, or you are a deserter. Secretly joining a second martial faction makes you a spy, who is exposed through rumours or recognition. |
| Existence | **Great and minor.** 10 world-spanning great factions with seats and branches, plus lazily seeded minor factions in each region. |

## 2. Architecture

The 3a patterns continue. Pure systems produce `Event`s, `commit` applies them via `@effect`s, `@listen` writes facts, fact hooks spread beliefs, and engine behaviour arrives as `GameHooks` mixins. Everything a faction knows goes through the knowledge layer (`systems/beliefs.py`).

**No save-format change.** The schema stays at version 2.

| Thing | Stored as |
|---|---|
| Faction | Entity `kind="faction"`. Its `data` holds `type`, `tier`, `home` (region coordinates), `seat` (town id or null until materialized), `doctrine`, `ranks`, `power`, `wealth`, `treasury`, `arts` (technique ids, filled lazily), `halls` and `branches` (town ids). |
| Faction relation | Relation `stance` between factions (faction → faction, `value` in −1..1). It is symmetric and written both ways. |
| Membership | Relation `member_of` (person → faction). `value` = rank index. `data` = `{merit, hall, sponsor, secret, joined_at, status}`, where `status` is one of `member`, `expelled`, `deserter`, `released`. |
| Duty | Entity `kind="duty"` with `data={faction, holder, kind, target, place, deadline, difficulty, status, issued_at}`. |
| Branch hall | The town's `data["halls"]` lists faction ids with a hall there. |

The seeded paths are `world/factions`, `world/faction:{i}`, `{region_path}/minor:{i}`, `duty:{faction}:{holder}:{n}`, `{faction_path}/member:{town}:{i}`, `rival:{faction}:{player}` and `law:{town}:{time}`.

### 2.1 New modules

| File | Responsibility |
|---|---|
| `systems/factions.py` | The great roster (`ensure_roster`), minor factions per region, seats and branches, seeding members, stances, `faction_of`, `members_of`, and `standing(world, faction, subject)`. |
| `systems/membership.py` | Eligibility, trials, joining (open or secret), merit, promotion, stipends, arts, release, desertion, and spy exposure. |
| `systems/duties.py` | Generating duties, reading progress from committed events, completing, failing and deadlines. |
| `systems/politics.py` | Halls and sponsors, the rival disciple, framing, taboos, judgement, deny, and exposing the rival. |
| `systems/law.py` | Bounty per town, wanted status, arrest, fines and cells, and bounty hunters. |
| `engine/factions.py` | The `FactionsMixin`: conversation choices, the standing page (F6), duty hooks, and summonses. |
| `narrate/faction_text.py`, `narrate/grammar/factions.toml` | Outcomes, summaries and grammar. |
| `assets/art/gate.art`, `assets/art/hall.art` | Scene overlays for seat towns and branch towns. |

## 3. Factions in the world

### 3.1 The great roster
`ensure_roster(world)` runs once, at `Game.new` or on load when it is missing. It is seeded by `world/factions` and creates exactly 10 great factions:

| # | Type | Count | Name pattern (seeded) | Doctrine path |
|---|---|---|---|---|
| 1 | `orthodox_sect` | 3 | "<Azure/Pure/Iron/Jade/Cloud/Pine...> <Summit/Cloud/Sword/Pine/Lotus...> Sect" | righteous |
| 2 | `demonic_cult` | 1 | "<Blood/Night/Heaven-Devouring...> <Lotus/Moon/Demon...> Cult" | ruthless |
| 3 | `unorthodox_clan` | 1 | "<Ten Thousand/Five/Black> Poison <Valley/Clan/Hall>" | ruthless |
| 4 | `martial_clan` | 1 | "<surname> Clan" | neutral |
| 5 | `beggars` | 1 | "Beggars' Sect" | neutral |
| 6 | `merchant_guild` | 1 | "<place> Merchant Guild" | neutral |
| 7 | `imperial` | 1 | "Imperial Martial Bureau" | righteous |
| 8 | `alliance` | 1 | "Orthodox Martial Alliance" | righteous |

**Homes.**
- Each faction's home region is seeded within Chebyshev radius 6 of (0, 0).
- The first orthodox sect's home is always within radius 2 of (0, 0), so a newcomer can find one.
- The imperial office, the alliance, the beggars and the guild have their seats in the most populous region within radius 3.

**Seats and branches.**
- A faction's seat is town 0 of its home region. It is created when needed, using `ensure_town`.
- Sects, cults and clans have branches in each town within 2 regions of home, with chance 0.35 per town, rolled when the town is populated.
- The beggars have a branch in every town that has a beggar, the guild in every town with a merchant, and the imperial office in every town (every town has constables).
- The alliance has no branches. It acts through the imperial office's law in orthodox regions (§8).

**Stances** are set at roster creation:
- orthodox and orthodox: +0.6;
- orthodox and the alliance: +0.8;
- orthodox or the alliance against demonic or unorthodox: −0.8;
- the imperial office against demonic: −0.6;
- the imperial office and orthodox: +0.2;
- every other pair: 0;
- demonic and unorthodox: +0.2.

### 3.2 Minor factions
When a region is materialized, `minor_factions(world, region)` seeds 0–2 minor factions from `{region_path}/minor:{i}`. Each is one of:
- `school` (a small orthodox school);
- `bandit_fort` (ruthless);
- `local_clan` (neutral).

A minor faction has the rank ladder of its type, a seat in one of the region's towns, no branches, and a stance of 0 with everyone except bandit forts, which stand at −0.5 with orthodox factions and the imperial office.

### 3.3 Members
- **Seat staff.** When a seat town is populated, it gains seeded staff from `{faction_path}/member:{town}:{i}`:
  - the leader: top rank, two realms above the faction's base;
  - 2 elders, one heading each hall;
  - a hall keeper;
  - 4 disciples.
- **Branch staff.** A branch gains a hall keeper and 2 disciples.
- **Base realm** by type: sects and cults third-rate, clans and the guild mortal, beggars mortal, the imperial office third-rate. Staff use the existing NPC generator with forced occupation and traits biased by doctrine (cult staff are drawn from `cunning`, `hot-tempered` and `proud`).
- **Natural members.** Existing town NPCs are enrolled at population time: constables in the imperial office (rank 0), beggars in the Beggars' Sect, and merchants in the Merchant Guild. They only get a `member_of` relation; no extra NPCs are created.
- **Halls.** Each great faction has 2 halls, named after their elders ("Elder Mu's hall"). Seat staff are split between them.

### 3.4 Standing: how a faction sees you
`standing(world, faction, subject) -> Standing(score, word, reasons)`. The subject may be a persona, which is handled through `apparent_to` and `identities` as in 3a.

The **knowledge** used is the union of the belief pools of the faction's seat town and branch towns, plus the beliefs of its members. For each fact, the most confident version is kept. For every believed fact where the subject is the actor, the fact adds `weight × confidence ×`:
- **−1.0** if the target is a member of this faction, or a faction whose stance with it is ≥ +0.5;
- **+0.5** if the target is a member of a faction with stance ≤ −0.5;
- a **doctrine** term: for a righteous faction, `PATH[predicate]` from 3a reputation; for a ruthless one, `−0.5 × PATH`; for a neutral one, 0.

There are also fixed terms:
- **+1.0** if the subject is a member in good standing;
- **−2.0** for each martial faction with stance ≤ −0.5 against this one that the knowledge says the subject belongs to;
- **−3.0** if expelled from this faction or a deserter from it (a permanent `status`).

| score | word |
|---|---|
| ≥ 3 | honoured |
| ≥ 1 | welcome |
| > −1 | neutral |
| > −3 | distrusted |
| otherwise | enemy |

`reasons` holds the two largest terms as short phrases, following the 3a attitude reason style.

**Enemies by association.** 3a's `attitude()` gains one term: −1.0 × |stance| when the NPC is a member of a faction with stance ≤ −0.5 toward a martial faction the NPC believes the subject belongs to. The reason reads "you are of the Blood Lotus Cult".

## 4. Joining

- *Ask to join* appears when talking to a hall keeper, elder or leader of a faction the player is not in. For a martial faction it needs the player not to be an open member of another martial faction, or the secret option (§7.3).
- **Eligibility:**
  - standing is `neutral` or better;
  - a righteous faction also refuses if the seat town's reputation path for the subject is `ruthless`;
  - the imperial office requires the player to be at least third-rate and to have a bounty of 0 in this town (§8).
- **Trials** are held as an open *trial* state stored on the player (`data.trial = {faction, kind, target?, deadline}`):

| Faction | Trial |
|---|---|
| orthodox sect, school | Test spar against a disciple (duel mode `test`, exactly as the 2b teacher test). Passing means joining. |
| demonic cult, poison clan | *Blood proof*: kill a named person. The target is seeded from the members of a faction with stance ≤ −0.5 within 2 regions, or else a townsperson of the seat region. Deadline 30 days. |
| martial clan, local clan | *Service*: complete one duty (§5) issued as a trial duty. |
| Beggars' Sect | *Ears*: tell the recruiter 3 rumours the recruiter did not hold (uses 3a telling: 3 accepted `told` events to that recruiter while the trial is open). |
| merchant guild | Pay a fee of 50 silver, then complete one escort duty. |
| imperial office | No trial beyond eligibility. |
| bandit fort | Beat the chief in a duel, or pay 30 silver in tribute. |
| alliance | Not joinable in 3b. The option is not offered. |

- **Joining** commits `joined` (player, recruiter), with data `{faction, secret, hall}`. Its effect relates `member_of` at rank 0 with merit 0. The hall is the recruiter's hall, or the seeded choice for a non-staff recruiter, and the sponsor is that hall's elder. Its listener writes a fact `member_of` (subject = player or the worn persona, object = faction id, weight 1.0). The fact spreads normally unless the membership is secret (§7.3).
- **Signature arts.** Each great faction has 3 arts (minor factions have 2), generated on first need, seeded, in its favoured forms, at grades 2, 3 and 4. The art of grade `n` needs rank ≥ `n − 2`. *Learn a sect art* (from an elder, free) teaches the next one the player's rank allows. At the seat, *Study in the library* offers the faction's manuals at inner rank or above; they are studied with the existing `study` action.

## 5. Ranks, merit, duties

**Ranks.** Ladders by type, with rank 4 unreachable in 3b:

| Type | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| orthodox_sect, school | outer disciple | inner disciple | core disciple | elder | sect leader |
| demonic_cult | blood servant | cult follower | blood envoy | cult elder | cult master |
| unorthodox_clan | apprentice | poisoner | master poisoner | elder | valley master |
| martial_clan, local_clan | retainer | sworn retainer | household guard | clan elder | clan head |
| beggars | one-pouch beggar | three-pouch beggar | five-pouch beggar | seven-pouch elder | nine-pouch chief |
| merchant_guild | associate | factor | senior factor | master | guild head |
| imperial | constable | senior constable | inspector | commander | bureau chief |
| bandit_fort | lackey | bandit | lieutenant | second | chief |

**Promotion** from rank r to r+1 needs:
- merit ≥ `(30, 90, 250)[r]`;
- a realm of at least `(mortal, third-rate, second-rate)[r]`;
- for rank 3, the sponsor's attitude toward the player at friendly or better.

*Ask for promotion* (to an elder or the leader) commits `promoted`. It writes a fact `promoted` (weight 0.5) and resets the rank's stipend clock.

**Stipend.** Every 30 days a member may collect `10 × rank` silver from a hall keeper (*Collect your stipend*).

**Duties.** A member asks a hall keeper for one with *Ask for a duty*, and may hold only one at a time. Each duty is seeded by `duty:{faction}:{player}:{n}`. The kind is weighted by faction type (table below), with difficulty 1–3 from the rank. The deadline is `issued_at + (3 × regions of travel + 7) days`.

| Kind | What | Completes when | Weights (orthodox / cult / clan / beggars / guild / imperial) |
|---|---|---|---|
| `hunt` | defeat (a cult requires *kill*) a named bandit or beast roamer materialized in a region within 2 | a `duel_ended` won against the target (with verdict `kill` for cults) | 3 / 3 / 2 / 0 / 1 / 3 |
| `deliver` | carry a sealed letter to a town within 3 regions | arrival in that town | 2 / 1 / 2 / 3 / 2 / 1 |
| `escort` | escort a caravan to a town within 2 regions; road encounters ×2 on the way | arrival | 0 / 0 / 1 / 0 / 3 / 0 |
| `collect` | recover a debt from a named NPC | the debtor pays (*Demand payment*: pays if afraid, honest or kind, otherwise a duel; winning forces payment) | 0 / 2 / 2 / 0 / 3 / 1 |
| `gather` | learn something about a named member of a hostile or rival faction | the player holds any belief whose actor or target is that person, learned after issue | 1 / 1 / 0 / 3 / 1 / 1 |
| `guard` | stay at the seat for `5 × difficulty` days | the time spent resting, meditating or practising at the seat since issue reaches that total. Each resting stretch there has a 0.3 chance of a raid: a duel against a member of a hostile faction, and losing fails the duty. | 2 / 1 / 2 / 0 / 0 / 2 |

- **Hunt targets are waiting.** Travelling into the target's region forces the road encounter with them, overriding the normal roll.
- **Reporting.** *Report on your duty* to any hall keeper of the faction: `duty_done` gives merit `10 × difficulty` and silver `5 × difficulty`, and gives the sponsor a `respect` memory. Delivery and escort complete on arrival without a report; their merit is paid at the next hall visit.
- **Failure.** A duty past its deadline fails at the next engine turn: `duty_failed` costs merit `−10` (floored at 0) and gives the sponsor an `annoyed` memory. The player may also *Abandon the duty*, which counts as failure.
- **Trial duties** (clan, guild) follow the same flow. Completing one triggers `joined`.

## 6. Politics

### 6.1 Halls and the sponsor
The sponsor is the elder of the player's hall. Their attitude toward the player (3a `attitude`) gates the rank 3 promotion and weighs in judgements. *Offer a gift* to an elder costs `20 × (rank + 1)` silver and gives them a `grateful` memory at intensity 0.4.

### 6.2 The rival disciple
- On joining a great faction, the player gets a seeded rival (`rival:{faction}:{player}`): a staff disciple of the same faction, or a new one created at the seat, at the player's rank.
- `player.data.rivals[faction] = id`.
- The rival is **proud** and holds an `annoyed` memory of the player from the joining. That makes them a 3a grudge challenger in town.

**Framing.** Each time the player completes a duty, there is a 0.15 chance (seeded) that the rival frames them:
- The rival tells an invented fact (3a `told`, with `invented=true`, `liar=rival`, `accepted=true`) to the sponsor's rival elder, which puts it in that elder's belief and in the seat pool.
- The predicate is chosen to break the faction's taboos (§6.3). For example, the rival claims the player "robbed" a townsperson of the seat town.
- 3a's rule 2 (every lie has a liar) already covers NPC liars.

### 6.3 Taboos and judgement
Taboos are checked against what the faction **believes** (its knowledge from §3.4), never against ground truth.

| Faction type | Taboo predicates in believed facts (the subject is the player or their known persona) |
|---|---|
| orthodox, school, alliance | `killed` or `robbed` a non-bandit mortal; being believed a member of a demonic or unorthodox faction |
| demonic, unorthodox | `spared` a member of a faction with stance ≤ −0.5 |
| martial or local clan | any harm to a member of the clan |
| beggars | any harm to a beggar |
| merchant guild | `robbed` a merchant; a failed escort |
| imperial | any fact that raises a bounty (§8) |

- **Summons.** A newly believed breach, meaning a fact id not in `membership.data.judged`, summons the player the next time they are in a seat or branch town of that faction. It works like a 2b challenge: a gated special state with a menu.
- **Choices:**
  - **Accept the punishment:** merit −30 (floored at 0). If merit is 0 and rank > 0, the player is demoted by one rank.
  - **Demand trial by combat:** a duel against the sponsor's rival elder. Winning clears the charge. Losing means the punishment plus the loss.
  - **Deny** (only when the fact is *false*, as the faction would come to learn): the chance is `0.4 + 0.25 × sponsor_attitude − 0.25 × accuser_attitude + 0.4` if any NPC present holds a first-hand belief contradicting the charge. Success clears the charge and, when a liar is identified, starts §6.4. Failure is treated as refusing.
  - **Refuse:** the player is expelled (§7.2).
- The judged fact id is added to `data.judged`.

### 6.4 Exposing the rival
When the player holds a belief of the framing lie whose `source` is the rival, *Expose <rival>* appears when talking to the sponsor. Success is certain with that evidence:
- `lie_exposed` is written with the rival as liar (the 3a exposure event, generalized to a `liar` actor);
- the rival is expelled, becoming a hostile NPC with an avenger-like grudge (`wronged`);
- the player gains merit +20.

## 7. Leaving, desertion, spying

### 7.1 Release
*Ask for release* (to the sponsor):
- **Orthodox, clan, beggars, guild, imperial:** release is granted for a final duty, or immediately for `50 × (rank + 1)` silver. `status` becomes `released`, merit is forfeited, and the `member_of` fact is superseded by a `released` fact.
- **Demonic and unorthodox:** refused. The player can only desert.

### 7.2 Expulsion and desertion
- **Deserting:** *Walk away* while under a refused release or an unfinished punishment.
- Being expelled, or deserting, sets `status = expelled` or `deserter`, writes a fact (`expelled` or `deserted`, weight 2.0), and gives every staff member of the faction a `wronged` memory about the player. The standing becomes −3.
- **Hunters:** for as long as the player is in the faction's region or within 2 of it, faction members in town issue grudge challenges (as 3a avengers do, chance 0.6), and a road encounter of kind `sect_hunter` fires with chance 0.2 per journey. The hunter is a disciple or elder at the rank or realm above the player.

### 7.3 Spying
- **Joining a second martial faction** while an open member of one is possible only as a **secret** joining, and only if the recruiting faction's knowledge does not already hold `member_of(player, first)`.
- A secret joining's `member_of` fact is written with `spread=False`. Only the recruiter and the faction's seat pool learn it, as a direct belief with `channel "told"`.
- **Exposure:** at any point, when faction F's knowledge holds `member_of(player, G)` for a martial G ≠ F while the player is a member of F, F expels the player **as a spy**. That writes the fact `spy` (weight 2.5), and F's hunters pursue the player (§7.2).
- **Side ties** (guild, imperial, beggars, martial clan) can be held alongside one martial faction, openly and without penalty. The only exception is imperial membership together with a demonic or unorthodox faction, which the imperial office treats as the spy case.

## 8. Law: bounties, arrest, bounty hunters

**Bounty per town.** `bounty(world, town, subject)` is worked out from that town's gossip pool: `20 × Σ weight × confidence` over the believed facts in which the subject:
- `killed` a non-bandit;
- `robbed` a non-bandit;
- `crippled` anyone;
- is a member of a demonic or unorthodox faction (weight 1.5 per `member_of` fact).

Facts listed in `player.data.atoned` are excluded. Personas are handled as in 3a, so a masked killing puts the bounty on the persona.
- A bounty under 30 silver is ignored.
- In a region whose nearest great orthodox seat is within 3 regions, the alliance doubles the bounty for cult membership.

**Arrest.** With a bounty ≥ 30 in the current town, a constable (an imperial member present) confronts the player on arrival or look, with chance 0.4. This is a special gated state, like a challenge. The choices:
- **Surrender and pay the fine:** pay the bounty in silver. The contributing fact ids go into `atoned`.
- **Surrender and serve time:** days in a cell equal to the bounty ÷ 5, run as a time skip (rest-like, no meditation). The facts are atoned.
- **Fight:** a duel against the constable. Killing a constable is itself a `killed` fact.
- **Flee:** the existing flee chance. Failing it starts the fight.

**Bounty hunters.** When travelling to a town where the bounty on the player is ≥ 50, a road encounter of kind `bounty_hunter` fires with chance 0.2. The hunter is a wandering roamer at the realm above the player's. They cannot be paid off or talked down.

## 9. Screens and narration

- **F6 standing page**, also opened with the typed `standing` or `factions`. It shows:
  - your memberships (faction, rank, merit, sponsor, hall, secret);
  - the open duty with its deadline in days;
  - an open trial;
  - every faction the player has heard of, with its standing word and main reason;
  - the bounty in the current town and in any town where it is ≥ 30;
  - your rivals.
  It shows only factions the player holds a belief about, has met a member of, or belongs to.
- **Scenes:**
  - Seat towns add "The <faction> keeps its seat here." and use the `gate.art` overlay.
  - Branch towns add "The <faction> keeps a hall here." and use `hall.art`.
  - The "Here:" list labels known members: "Elder Mu (Azure Cloud Sect)". An NPC's faction is known if the player holds a `member_of` belief for them, met them in a hall of that faction, or they are staff in the town's hall.
- **Conversation** choices (still at most 9, with extras folded into `extra`) are grouped under *Faction matters...*:
  - join;
  - duty, report, abandon;
  - promotion, stipend;
  - learn an art, library;
  - gift;
  - release;
  - expose.
- **Briefs** gain up to 2 faction facts: "You are an inner disciple of the Azure Cloud Sect.", and "The Blood Lotus Cult counts you an enemy." Talking to a member adds "Elder Mu (your sponsor) favours you." The limits stay at 6 facts and 1,200 characters, with no ids.
- **New events,** each with grammar, an outcome and a summary: `joined`, `trial_begun`, `promoted`, `stipend`, `duty_issued`, `duty_done`, `duty_failed`, `summoned`, `judged`, `released`, `expelled`, `deserted`, `spy_exposed`, `gift`, `arrest`, `fined`, `jailed`, plus the new encounter kinds `sect_hunter` and `bounty_hunter`.

## 10. Debug rules (added to `debug/invariants.py`)

1. **Memberships are valid.**
   - Every `member_of` points at a faction entity.
   - A person has at most one open (non-secret, `status == member`) martial membership.
   - The rank is within the ladder and below 4 for the player.
   - Merit is at least 0.
2. **Duties are consistent.**
   - Every open duty has a living holder who is a member of the duty's faction.
   - Its target exists.
   - Once a hunt target is dead, the duty is `done` or `failed` within the same turn.
3. The dead hold no open duty and no membership with `status == member` on staff lists.
4. Faction stances are symmetric and lie in −1..1.
5. The F6 page and briefs name only factions the player knows (the §9 rule), checked by the 3a name rule extended to faction names.

## 11. Testing

- A unit test file for each module.
- The roster is deterministic: the same seed gives the same 10 factions, homes, stances and names.
- Standing: the doctrine direction, enemies by association, masked deeds counting for the persona only.
- Each trial kind, from start to membership.
- Each duty kind, through completion, failure by deadline, and abandoning.
- Framing, then judgement with each choice, then exposing the rival.
- Release, desertion and spy exposure.
- Bounties, arrest with each choice, and bounty hunters.
- A **sect life fuzz run**: 300 random turns weighted toward joining, duties, promotion, travel, killing and masks, across 2 seeds, with every invariant passing.
- **Speed:** with a save holding 60 factions (the 10 great ones plus minors across 25 regions) and 3a's heavy-save shape, a turn stays under 150 ms including the checks.
- Existing tests stay green. Tests that assumed the 3a conversation menu are updated as rulings.

## 12. Out of scope for 3b

- Founding your own faction (3c).
- Factions acting on their own: wars, power and wealth drift, succession, recruiting NPCs, moving staff (phase 4). Stances and power change only through events the player causes.
- Becoming sect leader, since rank 4 needs phase 4 succession politics.
- Teaching sect arts to others, because the player cannot teach in 3b.
- Marriage into clans.
