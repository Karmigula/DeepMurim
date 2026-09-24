# DeepMurim Phase 4e: Murim Tournaments

Date: 2026-09-24
Status: Draft, awaiting user review
Parent spec: `2026-09-22-deepmurim-design.md` (§5.7 scheduled world events)
Builds on: phase 4d (merged, master at `0934e9a`): the world-event framework, heavenly phenomena, the Heavenly Ranking Pavilion.

## 1. Goal

The Murim measures itself in public. Every three years the Grand Martial Assembly fills a famous city. Every two years the Dragon-Phoenix Meet shows the young who will matter. Every sect tests its disciples each year, and in any town a fighter may hold the lei tai platform against all comers.

You enter and fight your bouts live. You watch rivals, bet silver on what you believe, catch the eye of elders, make enemies of the proud, and sometimes uncover a fixed match, or a cult that cannot resist a crowd.

Every system:
- reports to the narrator in `Brief` facts plain enough for Haiku;
- adds rules to `debug/invariants.py`;
- is covered by the fuzz test.

### Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Kinds | Grand Martial Assembly, Dragon-Phoenix Meet, sect contests, lei tai platforms. |
| Taking part | **Enter, then fight live.** Register under entry rules; your matches are interactive bouts; NPC matches resolve in the background. |
| Stories | Betting, scouting and spectating, grudges from the arena, dark interventions. |
| Rounds | **Round by day.** Each round has its own day of the active stage; NPC matches resolve lazily; your match is called at the venue on your day. |

## 2. Architecture

- **Every kind is a 4d world-event type:**
  - a TOML entry in `systems/data/world_events.toml`;
  - a module in `systems/events/`: `grand_assembly.py`, `dragon_phoenix.py`, `sect_contest.py`, `lei_tai.py`;
  - shared machinery in `systems/tournaments.py`.
- **A tournament is the occurrence.** Its `data` holds the bracket, registrations, results, bets and interventions.
- **No save-format version change.** New:
  - event kinds `registered`, `bout_called`, `match_resolved`, `tournament_won`, `bet_placed`, `bet_settled`, `watched`, `invited`, `intervention`, `exposed`, `disqualified`;
  - duel mode `bout`;
  - fact predicates `won_tournament`, `placed`, `fixed`, `vanished`, `raided`, `disgraced`;
  - player data `titles`.

### 2.1 New modules

| Module | Role |
|---|---|
| `systems/tournaments.py` | Entry rules; registration; filling and seeding brackets; rounds by day; resolving matches; rewards; results; compaction. |
| `systems/events/grand_assembly.py`, `dragon_phoenix.py`, `sect_contest.py`, `lei_tai.py` | The four kinds: schedule, eligibility, pools, rewards. |
| `systems/wagers.py` | Bookmakers, odds from beliefs, bets, settlement. |
| `systems/intrigue.py` | Dark interventions: raids, fixed matches, vanishings; exposure. |
| `engine/tournament.py` | `TournamentMixin`: register, the call, bouts, watch, bet, the pages, the lei tai challenge. |
| `engine/tournament_page.py` | The tournaments page (F11) and the bracket and odds pages. |
| `narrate/tournament_text.py`, `narrate/grammar/tournament.toml` | Narration and journal lines. |

## 3. The four kinds

| | Grand Martial Assembly | Dragon-Phoenix Meet | Sect contest | Lei tai |
|---|---|---|---|---|
| Host | a city, seeded per edition | a city, seeded per edition | the sect's seat | any town |
| Cycle | every 3 years (12 seasons), a fixed seeded offset | every 2 years (8 seasons) | yearly, per staffed sect with 4 or more disciples (materialized seats only) | seasonal chance 0.05 per populated town |
| Stages (days) | foretold 60, announced 20, active 8, aftermath 30 | 30 / 10 / 5 / 20 | announced 5, active 1 | active 1 |
| Size | 32 | 16 | 8 | holder and challengers |
| Rounds | days 1, 3, 5, 7, 8 of active | days 1, 2, 3, 5 | all on day 1 | through the afternoon |
| Entry | Second-rate or higher, and a sponsor, a Pavilion rank or a 100-silver bond | 30 or under, and a sponsor or a 30-silver bond | a member of the sect, disciple or above | anyone present |
| Prize | 300–800 silver, the title "Champion of the Nth Grand Martial Assembly", a weight-3.0 fact | 100–300 silver, the title "Dragon-Phoenix of year Y", a weight-2.0 fact; sect standing (+5 power) | merit, one rank step, a chance of a master's notice | a 20–60 silver purse, a local renown fact |

- **Sponsor:** a faction you belong to, or one whose attitude toward you (3b) is warm or better. The bond is refunded if you reach the second round.
- **Your own sect's contest (3c):** at registration you choose to compete or to preside. Presiding lets you reward the winner or take them as a disciple (4b `take_disciple`).
- **Old saves:** the first edition of each kind falls at its next cycle point.

## 4. Brackets and matches

### 4.1 Filling
- The pools are:
  - each staffed faction's best member who meets the rules;
  - ranked names the organisers believe in (from the Pavilion's lists as the host town believes them);
  - the player and other registrants;
  - seeded wanderers to fill the size.
- The strongest are invited first; if more are eligible than the size allows, the weakest by belief are left out.

### 4.2 Seeding
- By the organisers' belief: rank tier, then the host town's renown for the fighter, then id.
- The top seeds are placed apart (1 against 32, 2 against 31, …).
- An entrant the town has never heard of seeds last. That is how hidden masters make upsets.

### 4.3 Rounds by day
- Each round belongs to a day of the active stage. When that day is observed:
  - every NPC match of the round resolves through the 2b duel simulator (seeded per match);
  - a match that includes the player waits for the player.
- **Your call:** if you are at the venue on your day, a `bout_called` scene offers **Fight** or **Forfeit**.
- **Forfeits:**
  - if the day passes without you (you left, or waited past it), you forfeit;
  - a vanished entrant (§5.4) forfeits.
- **Byes** advance automatically.

### 4.4 The bout
- A new duel mode, `bout`, fought at full strength.
- It ends when a fighter:
  - yields;
  - is broken (harm 85 or more);
  - or is driven from the platform (a ring-out chance on an opening of 20 or more).
- There is no verdict step: the winner advances.
- NPCs never choose to kill in a bout.
- **If you kill:** you are `disqualified`, with a `disgraced` fact (weight 2.0) and `hatred` in the victim's sect and kin.

### 4.5 Results
- Each round's results become `placed` facts (weight 0.5–1.5, by round).
- The champion's `won_tournament` fact carries the prize weight.
- The Pavilion's informants listen for `won_tournament` and `placed`:
  - a won bout counts like a `defeated` win (§6.3 of the 4d spec);
  - a championship adds 60 deed points (Assembly) or 40 (Meet).

## 5. Around the brackets

### 5.1 Betting
- A bookmaker trades in the host town from `announced` until each match starts.
- **Odds** come from the bookmaker's beliefs: the rank and host-town renown of each fighter, turned into a win probability `p = s_a / (s_a + s_b)` with a 10% margin.
- **Stakes** are at most 10% of your silver. You may bet on any match, including your own.
- **Settlement** happens when the match resolves.
- **Betting against yourself** and then losing records a `fixed` fact about you if anyone saw the bet: the bookmaker's town gossips.

### 5.2 Watching
- `watch` at the venue on a match day. Each watched match gives you:
  - one art fragment of each fighter (as 2b reveals);
  - their stance tendency;
  - a witnessed memory.
- **Elders in the crowd:** each round's winner rolls to be noticed (chance 0.2 × the round number / the number of rounds) by an elder of a sect present in town:
  - the player gets an invitation (3b membership, trials waived) or, if already a member, a gift of silver;
  - an NPC is recruited by that sect.

### 5.3 Grudges
- **Losers:**
  - `humiliated` after a loss by a clear margin, `respect` after a close one;
  - `grateful` if you let them yield without a finishing blow.
- **Revenge:** a proud or hot-tempered loser, or one from a sect hostile to the winner's, gains a 4a revenge agenda target (chance 0.3).
- **A disqualified killer** earns `hatred` from the victim's sect and kin.

### 5.4 Dark interventions (seeded, at most one per tournament)

| Intervention | Chance (Assembly / Meet / others) | Effect | Discovery |
|---|---|---|---|
| Demonic raid | 0.10 / 0.05 / 0 | The final is interrupted: cultists fight the crowd; you may join the defence (a duel with a cultist). The final is replayed the next day, or void if a finalist dies. | A `raided` fact, weight 3.0. |
| Fixed match | 0.15 / 0.10 / 0.05 | One entrant is poisoned or bribed: their strength ×0.6 in one bout. | A hidden `fixed` fact (unspread) until exposed. Asking the bookmaker (a chance based on renown), watching the bout, or a rumour can reveal it; `expose` spreads it and grants renown. |
| Vanished entrant | 0.05 / 0.05 / 0 | A favourite disappears the night before their round and forfeits. | A `vanished` fact, weight 1.5. It is left open for later phases (4g, 5). |

## 6. Screens

- **`tournaments` / F11:**
  - known tournaments with kind, host, stage, entry rules and your status;
  - built only from beliefs and what you have seen.
- **`register`:** at the venue during `announced`. Refusals are explained.
- **`bracket`:** the bracket as you know it (witnessed or heard results), the next round's day and your next opponent.
- **`watch`, `odds`, `bet <match> <silver>`**, and `expose` when you know of a fix.
- **Your call:** "The herald calls your name…", with **Fight** and **Forfeit**.
- **Lei tai:** "Challenge the platform holder" while it is active.
- **Brief:** a line for the host town ("The Grand Martial Assembly: round 3 today; the odds favour X").
- **Arrival lines** for heralds and opening days.
- **Journal lines** for every new event kind.
- **Sheet:** titles and open bets.
- **Lineage page:** ancestors' titles.
- **Death mid-tournament:** you forfeit. Bets are void and refunded to your estate, and your heir inherits the titles as family pride.

## 7. Debug rules

1. **A valid bracket:**
   - the size is a power of two, with byes;
   - each match has at most one winner, one of its two fighters;
   - a round's matches resolve on or after that round's day.
2. **Advancing:** each winner advances exactly once; the champion is set only when the final resolves; there is at most one champion per tournament.
3. **No killing:** a bout ends in death only with a matching `disqualified` event.
4. **Bets:**
   - each is settled at most once;
   - the stake is at most 10% of the silver held when placed;
   - none is open after its tournament is over, except those voided by death and refunded.
5. **Eligibility:** entrants meet their tournament's rules (the Meet's age, the Assembly's realm, sect membership for contests).

## 8. Testing

- **Types:** each kind is a TOML type with its schedule, stages and cycle.
- **Brackets:**
  - filled and seeded from beliefs (a hidden master seeds last);
  - NPC rounds are deterministic;
  - byes and forfeits.
- **Player:**
  - registration, each rule and refusal;
  - the call;
  - a live bout (NPCs never kill; a player kill disqualifies);
  - missing a day forfeits;
  - death mid-tournament.
- **Rewards:** titles, silver, sect merit and rank, disciple offers, Pavilion points.
- **Stories:**
  - odds from beliefs, payouts, betting on yourself;
  - watching gives fragments and memories;
  - elders invite;
  - losers' memories and revenge;
  - each intervention, and its discovery and exposure.
- **Engine:** F11, the bracket and odds pages, briefs, sheet, lineage, the More... fold.
- **Fuzz:** `test_a_tournament_season`, 300 turns with every tournament made frequent, entering, betting, watching and fighting; every rule holds.
- **Old save:** the first editions fall at the next cycle points.
- **Soak and speed (CPU time):**
  - the 500-year soak stays within budget, and finished brackets are compacted into a results summary after 10 years;
  - a Grand Assembly round (16 NPC matches) resolves in under 60 ms;
  - the tournament pages render in under 30 ms.

## 9. Out of scope for 4e

- Secret realms (4f).
- Succession crises (4g).
- Tournaments the player founds and hosts.
- Where a vanished entrant went: that thread is left open for later phases.
