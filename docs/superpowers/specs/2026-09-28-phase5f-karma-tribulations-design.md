# DeepMurim Phase 5f: Karma and Tribulations

**Status:** design approved in brainstorming (2026-09-28). Phase 5 is six sub-phases:
- **5a** items with history (done);
- **5b** alchemy, medicine and poison (done);
- **5c** the alchemy world (done);
- **5d** forging and formations (done);
- **5e** the dao heart (done);
- **5f** karma and tribulations (this spec), and the close of phase 5.

Builds on master at cf45716:
- 2a's breakthroughs and body, 2b's duels, verdicts and road encounters (`ROAD_HOOKS`), 3b's hunters;
- 4a's lives and agendas, 4b's kin and avengers, 4d's tribulation lightning (`systems/events/tribulation.py`);
- 5b's pills and 4d's treasures, 5c's control pills and physicians, 5d's formations and smiths' commissions, 5d's fortune tellers (formation masters);
- 5e's heart, its deeds and demons.

## 1. Goal

Heaven keeps its own account, and it comes due at the gate of each realm.
- **Karma:** a hidden ledger of merit and sin kept by heaven, apart from the heart's view of itself, and **karmic threads** with particular people, saved or wronged, that pull them back across the player's path.
- **Tribulations** are weighed by karma, played through wave by wave (lightning, heavenly fire, the heart's demon), sheltered by a **tribulation array**, and come in a **minor** form at lesser breakthroughs and when sin grows too heavy. The heaviest can kill.
- **The world:** NPCs carry karma; their tribulations can kill them; heaven now and then strikes the wicked; temples take alms.
- **The close of phase 5:** 5c's absent masters, and 5d's commission lost with a smith who dies.

### Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Karma | A hidden ledger of merit and sin, plus karmic threads with particular people that pull them back into the player's path. |
| Tribulations | Weighed by karma; waves played through; tribulation arrays (deferred from 5d); minor tribulations. |
| World side | Like 5c-5e: NPC karma seeded, NPC tribulations weighed by it, retribution now and then, temples for merit. |
| Phase 5's deferred rules | One task of 5f. |
| Size | One phase, about eight tasks. |

### Genre notes

- Heaven's tribulation (天劫): nine waves of lightning, heavenly fire, the heart demon tribulation; the wicked struck harder.
- Karma (因果): the one you spared comes back to repay you; the one you wronged waits on the road.
- A fortune teller who reads the threads of fate around you; a temple where the guilty give alms.

## 2. The ledger (`systems/karma.py`)

- **State:** person data `karma = {merit, sin, threads}`; merit and sin 0 or more; the **balance** is `merit - sin`.
- **NPCs:** no `karma` until written; the seeded one (`karma:{key}`) reads occupation and traits: bandits and the cunning or greedy carry sin 20-80, monks, physicians and the kind or honest merit 20-80, others 0-30 of each.
- **Deeds** (`systems/data/karma_deeds.toml`), each an event kind, the actor it counts for, `merit` or `sin`:
  - sin: poisoning for pay 30, a poison slipped 30, a control pill forced 30, a hall theft 15, a false accusation 20, a secret sold 10, robbing a beaten foe 5, crippling one 15;
  - merit: healing 5, freeing the bound 25, a debt paid 5, an heirloom returned 15, a town kept from the beasts 15, sparing a beaten foe 5.
- **Killing** (a `died` listener): a person killed by the player is sin 10; one who yielded, or a mortal who does not fight, 40; one whose own balance is under -50, merit 15 instead ("slaying the wicked"). Beasts weigh nothing.
- **Knowledge:** karma is never shown as numbers. A fortune teller reads it in words for 50 silver (section 7).

## 3. Karmic threads (`systems/threads.py`)

- **A thread** is `{whom, kind, weight 1-3, since}` in `karma.threads`, at most twelve (the lightest goes):
  - **owed to you:** one you spared (2), healed or cured (1), freed from the worms (3);
  - **owed by you:** one you robbed (1) or crippled (2), the kin of one you killed (3; 4b's kin), one you falsely accused (2).
- **Fated meetings:** a road hook (2b's `ROAD_HOOKS`): each journey, the heaviest living thread whose home is within three regions comes with chance `0.05 x weight`:
  - **owed to you:** they repay (silver `20 x weight x (realm + 1)`, or a pill if they are an alchemist or physician), and the thread is spent;
  - **owed by you:** they stand in the road; the player may pay amends (`50 x weight` silver, the thread spent, merit 5) or fight (a duel, as an avenger's).
- A thread ends when either one dies.

## 4. Tribulations weighed by karma (`systems/tribulations.py`)

- **When:**
  - **great tribulations** at a breakthrough to First-rate or beyond (4d's rule);
  - **minor tribulations** at a breakthrough to Second-rate, and in a season when the player's sin exceeds merit by 150 or more ("heaven takes notice", at most once a year).
- **Weight:**
  - waves: 1 for a minor tribulation; `realm - 1` for a great one (at most 6); one more for each full 100 of net sin;
  - each wave's strength: `realm + max(0, -balance) / 50`, less `balance / 100` when merit leads (not below 1).
- **Wave kinds:** lightning always; heavenly fire from Transcendent (realm 5); the heart's demon wave when the player carries one (5e), at most once.
- **NPC tribulations:** 4d's lightning over an NPC now rolls their fate: death with `0.02 + 0.01 x max(0, -balance) / 10`, bounded 0.02-0.5; a death is news ("fell to the heavenly tribulation").

## 5. Waves played through, and the arrays (`systems/tribulations.py`, `systems/data/formations.toml`)

- **A tribulation scene** replaces 4d's single roll for the player; each wave offers:
  - **endure:** `0.45 + 0.3 x purity + 0.02 x (endurance - 10) + 0.05 x realm - 0.06 x strength`, bounded 0.05-0.95;
  - **spend a treasure or a pill:** one of grade at least `strength / 2` (5b's pills, 4d's treasure pills) turns a lightning or fire wave aside;
  - **shelter** in a tribulation array laid here: it takes the wave, its strength falling by `strength / 3` each time, gone at 0;
  - the **demon wave** is 5e's heart trial (face or bury; turning back is not possible now).
- **A failed wave:** lightning scars (internal injury 2); fire burns a meridian (as 4d's crippling); the demon deviates (+20). Failing the last wave of a tribulation of 6 or more waves when sin leads by 200 or more kills.
- **The whole:** clean (no wave failed), scarred, or crippled, as 4d's outcomes and its news; a clean great tribulation gives insight `+10 x realm` and merit 10.
- **The tribulation array:** a new pattern (ward, 8 flags, difficulty 3, 7 days) laid by the player or on a formation master's commission (5d), strength `0.5 + mastery / 2` as any pattern.

## 6. The world (`systems/karma_world.py`)

- **Retribution:** a lives agenda of one hash: an NPC whose seeded balance is under -100 is struck down with 1% a season ("struck down by heaven", news). The player whose balance is under -150: one season in ten a misfortune (a purse lost, 20% of silver; or an injury) with a line.
- **Temples:** a town with a monk has a temple: alms (`merit = silver / 10`, at most 30 a season) and incense (nothing but a line). The temple is on the town's menu.
- **NPC karma** is read in fated meetings, "slaying the wicked", retribution and NPC tribulations.

## 7. The player (`engine/karma.py`)

- **The tribulation scene:** waves announced one by one, with endure, spend, shelter, face and bury as the wave allows.
- **A fortune reading** in conversation with a fortune teller (5d's formation masters are fortune tellers by trade): the balance in words ("heaven smiles on you" to "heaven's patience is thin"), and the three heaviest threads by name.
- **The temple:** alms and incense.
- **Fated meetings** on the road: repayment told; amends or a fight.
- **Typed commands** (`endure`, `shelter`, `spend <item>`, `temple`, `alms`), help, journal lines, grammar and rumours for each new kind.

## 8. The close of phase 5 (`systems/control.py`, `systems/craft_world.py`)

- **Absent masters (5c):** an NPC master whose home is not the bound's home town for a season does not feed them; they starve as a careless player's bound do (5c's rule, which ruled masters never wander; NPCs do move).
- **A smith who dies with a commission unforged (5d):** the silver is returned to the player by the smith's estate (`commission_refunded`), the commission cleared; a line in the journal.

## 9. Knowledge vs truth

- The ledger and the threads are hidden; only a fortune reading tells them, in words and by name.
- A fated meeting names the one met (they are known: saved, wronged or their kin).
- Retribution and NPC deaths in the lightning are facts that spread.

## 10. Debug rules (`check_karma`)

- Merit and sin at least 0; at most twelve threads, each of a known kind with weight 1-3, naming a person.
- A tribulation scene in progress names a wave kind of the three and a strength at least 1.
- A tribulation array laid is a pattern of the table (5d's rule covers it).

## 11. Level of detail and speed

- NPC karma is a seed until written; retribution is one hash a season per NPC.
- **Speed** (CPU time, averaged after `gc.collect()`):
  - a season of 200 NPCs with the karma agenda stays within +10% of 5e's;
  - a road journey with the threads hook stays within +10%;
  - the tribulation scene and the fortune reading are each under 20 ms;
  - the 500-year soak keeps its limits.

## 12. Testing

- **Unit tests:** the ledger from deeds and kills; seeded NPC karma; threads gathered, fated meetings (repayment, amends, a fight), threads ended by death; the weight of a tribulation, minor tribulations, NPC deaths; waves (endure, spend, shelter, the demon), a death at the heaviest; the array; retribution and temples; absent masters and the refund.
- **Knowledge:** karma only in words and only from a fortune teller.
- **Fuzz:** `test_a_heavy_karma`: a fighter who kills, spares, gives alms, breaks through and meets their tribulations and their threads, at random. No crash, no rule broken.
- **The fork guide:** section 15.
- **Performance:** the limits of section 11.

## 13. Out of scope

- Reincarnation and past lives; heavenly immortals and ascension: later phases.
- Karma bought or sold between people.
