# DeepMurim Phase 4g: Succession Crises

**Status:** design approved in brainstorming (2026-09-25). Builds on 4a (the faction clock), 4b (lineage and succession), 4d (world events), 4e (tournaments, the duel simulation, level of detail) and 4f (secret realms, sealing) on master at d24f529.

## 1. Goal

When a sect's leader dies and the seat is in doubt, the sect falls into a crisis.

- Claimants rise: the chief disciple, the blood heir, an ambitious elder, a Grand Elder out of seclusion, or a regent for a child heir.
- Camps gather behind them. The will, the leader's token and a deathbed transmission weigh on who is rightful.
- The seat is won by the elders' backing, by trial by combat, or by force of arms. A war that drags on splits the sect, and a breakaway sect is born with a grudge that lasts generations.
- The player hears of crises everywhere, plays in the ones of sects they belong to, and can lose their own sect to one.

### Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Layers | All three: crises across the world, joinable ones in the player's sects, and crises in the player's own sect. |
| Phase split | 4g is the crisis. 4h (intrigue) adds a murdered leader, puppets and spies, arbitration and outsider heirs, marriage, the supreme art, the founder's test and the framed heir's return. |
| Ways to win | The elders' backing, trial by combat, the late leader's will, force of arms. |
| Proofs in 4g | The leader's token, deathbed transmission. (The supreme art and the founder's test are in 4h.) |
| Claimants in 4g | Chief disciple, blood heir against disciple, the Grand Elder from seclusion, a regent for a child heir. (The framed heir is in 4h.) |
| Trigger | Only when the seat is in doubt; otherwise the 4a handover stands. |
| Schism | The losing camp founds a breakaway sect, hostile to the old one, within caps. |
| The player's roles | In a sect they belong to: backer, claimant, token thief or broker. Elsewhere they only hear of it, except for trading the token. |
| The player's own sect | A crisis on their death, while they are gone (a regency, then a usurpation), and when they step down. |
| Approach | Each crisis is a 4d world-event occurrence (`succession_crisis`), started by the faction clock. Camps, claimants, the will and the token live in the occurrence's data. |

## 2. Architecture

### 2.1 New modules
- `systems/succession_crisis.py`: the doubt check, starting a crisis, the stages, resolution, and settling crises far away.
- `systems/events/succession_crisis.py`: the 4d event type (hooks: `places`, `start_data`, `on_stage`, `on_observe`).
- `systems/claimants.py`: who claims, voters, leanings, sways, the chief disciple.
- `systems/testament.py`: the will, the leader's token, deathbed transmission.
- `systems/schism.py`: strife between camps and breakaway sects.
- `systems/regency.py`: the player's own sect (death, absence, stepping down), and regents for child heirs.
- `engine/crisis.py`: `CrisisMixin`, which holds the choices at the seat, the talk extras (sways, the token) and the Succession block.
- `narrate/crisis_text.py` and `narrate/grammar/crisis.toml`.

### 2.2 The event type
- `[succession_crisis]` in `world_events.toml`:
  - `cycle = "trigger"`, `scope = "town"` (the sect's seat), `sky = false`;
  - stages in days: `mourning = 30`, `canvass = 60`, `contest = 15`, `strife = 180`, `aftermath = 20`;
  - news with predicate `crisis`, weight 2.0, on the stages `mourning`, `contest` and `aftermath`.
- At most one live crisis per faction. The faction's data gains `crisis` (the occurrence id, or none).
- `strife` is skipped (it ends at once) unless the contest went to force of arms.

### 2.3 The occurrence's data
- `faction`, `leader` (the late leader), `cause` (the doubt that started it).
- `claimants`: a list of `{person, kind}`, with `kind` one of `chief`, `blood`, `elder`, `grand_elder`, `regent`, `player`. At most 3 NPC claimants, plus the player.
- `camps`: `{claimant: [backers]}` as last settled at a stage change.
- `sways`: `{voter: {claimant: delta}}`, the player's doing, with the stage each was spent in.
- `will`: `{state, names}`, with `state` one of `none`, `read`, `hidden`, `held`, `burned`; `holder` when `held`.
- `token`: the token's id, or none when it is only a flag (far away).
- `transmitted`: the person who received a deathbed transmission, or none.
- `trial`: `{a, b, champions, winner}` once fought.
- `strife`: `{seasons, clashes}` while there is force of arms.
- `outcome`: `{leader, schism, breakaway}` once settled.

### 2.4 Level of detail
- A crisis at a seat in the player's region is played in full: people, items and leanings as below.
- A crisis elsewhere is settled at each stage change by one seeded roll, with the rule in §4.6. No Grand Elder, token item or will item is made for it; they are flags in its data.
- The player's region is the one they stand in (as 4f's `_near_player`).

## 3. The trigger

### 3.1 The seat in doubt
In the 4a faction clock, before `succession_events` promotes a new leader, `SC.doubt(world, faction)` returns a cause or none. The seat is in doubt when:

| Cause | When |
|---|---|
| `close` | The two best candidates (elders, then keepers, as 4a ranks them) are within one realm of each other, and neither is the named heir. |
| `heir` | The named heir is under 16, missing, sealed in a realm, or dead. |
| `violence` | The leader died `killed` or `executed`. |
| `token` | The leader died away from the seat, so the token is not in the hall. |

- With no doubt, the 4a handover stands, and the named heir, if fit, is the one promoted.
- With doubt, `succession_crisis` starts at the seat. While it is live, 4a fills elder and staff posts as usual but never the leader's post.
- Only staffed factions (`F.STAFFED`, not `player_sect`) take the 4a path. The player's own sect has its own triggers (§6.4).

### 3.2 The chief disciple
- Each staffed faction has `heir` in its data: its chief disciple.
- Once a year (the first season of the year), the faction clock names one if the post is empty or its holder has died or left. It picks the best keeper or disciple: highest realm, then youngest, then lowest id.
- A player member of rank 2 or higher is named instead if the leader's attitude toward them is 0.5 or more. It is a `named_chief` event with a fact the player hears.
- When the chief disciple is promoted to leader, the post empties.

### 3.3 Deathbed transmission
- A leader who dies `age` or `illness` has a seeded chance of 0.3 to transmit their inner energy to the named heir, if the heir is at the seat.
- The heir gains one realm (capped at the leader's own). It is a `transmitted` event with a fact, weight 2.0.
- A transmission is the strongest proof (§4.3). If the heir was the only cause of doubt, it removes the doubt.

## 4. The crisis

### 4.1 Claimants (mourning)
Claimants declare in this order, until there are 3:
1. **Chief disciple:** the named heir, if alive and not sealed.
2. **Blood heir:** the late leader's child (`kin_of` role `child`), aged 14 or more. In a `martial_clan` or `local_clan` they claim even if not a member; in any other faction they must be a member.
3. **Ambitious elder:** an elder who is ambitious (the traits `proud`, `cunning` or `greedy`; no new trait is added, to keep world seeds stable), or who is within one realm of the best claimant so far.
4. **Grand Elder:** see §4.2.
5. **Regent:** if the only claimant from rules 1 and 2 is under 16, the senior elder (highest realm, then lowest id) claims as regent for them (§6.5).

A crisis with fewer than 2 claimants after mourning ends at once. The one claimant, or the best candidate, is promoted, as in 4a.

### 4.2 The Grand Elder
- Each great staffed faction has a Grand Elder in closed-door seclusion. They are made lazily and seeded when the faction's first crisis in the player's region starts, at path `world:{faction}:grand_elder`. Their realm is one above the late leader's (capped), their age 90 or more, and they are `located_in` the seat with `secluded = true` (not in the scene).
- During mourning they emerge with chance 0.25.
  - If ambitious, they claim, taking the last claimant's place if there are already 3.
  - Otherwise they back the claimant they lean to most. Their backing counts as 3 voters.
- A Grand Elder outlives many crises. They are on the life clock like anyone, and their seclusion keeps them out of scenes, tournaments and rankings.

### 4.3 Voters and leanings
- The voters are the faction's elders and hall keepers, at the seat and at branches, plus the player if a member of rank 2 or more.
- `lean(voter, claimant)` is the sum of:
  - `attitude(voter, claimant).score` (the 3a attitude, computed; full detail only);
  - +0.2 for each realm the claimant has above the weakest other claimant;
  - the claimant's proofs: named in a `read` will +0.5, received the transmission +0.4, holds the token +0.3, blood heir in a clan +0.3, chief disciple +0.2;
  - the player's sways for that pair;
  - a `loyal` voter adds a further +0.2 to whoever the will or the leader named;
  - an ambitious claimant who is a voter leans only to themself.
- A voter backs the claimant they lean to most, if that lean is 0.2 or more; otherwise they are undecided. Claimants always back themselves.
- Camps are settled at each stage change and when the player asks to see them. They are never settled per turn.

### 4.4 The will
- At the leader's death, a will exists with chance 0.7 for a death by `age` or `illness`, 0.3 otherwise.
- It names the named heir, or, with none, the claimant the late leader's attitude favoured most.
- Its state at mourning (seeded):

| State | Chance | Meaning |
|---|---|---|
| `read` | 0.5 | Read out: its lean counts. |
| `hidden` | 0.3 | It lies in the late master's chambers at the seat. |
| `held` | 0.2 | A claimant it does not name has taken it and hides it. |

- **Hidden:** during canvass, a member at the seat may search the chambers once per season. The chance is 0.35, plus 0.1 per realm above the first. Each NPC camp rolls 0.2 at each stage change. The finder reveals it (`read`) or, if a claimant it does not name, keeps it (`held`).
- **Held:** it can be won from its holder by a duel with the purpose "the will". Its holder, or whoever took it, may reveal it (`read`) or burn it (`burned`, which gives no lean). Burning it is a fact if anyone witnessed it.
- In full detail the will is a `document` item (the 4d treasure model, `kind = "will"`), so it can be owned, taken and shown.

### 4.5 The leader's token
- Each staffed faction has a token: a treasure with `kind = "sect_token"` and `faction`. It is made lazily when first needed, at path `world:{faction}:token`.
- Where it is when the leader dies:
  - **Died at the seat:** in the hall (`located_in` the seat). No doubt, and a claimant picks it up at mourning: the chief disciple, or else the first claimant.
  - **Died away from the seat:** where they fell (`located_in` that town), or with their killer.
  - **Died inside a secret realm:** with their remains (4f), taken by `take_remains`.
- Whoever holds the token gets its lean. It can be:
  - **bought:** the price is 5 × the faction's power in silver, and the holder must be willing (not a claimant);
  - **won:** a duel with the purpose "the token";
  - **picked up:** where it lies, by anyone present;
  - **handed to a claimant:** the claimant pays the price if their camp can, and the giver gains an indelible warm memory with the claimant.
- The new leader holds it after the crisis. A lost token is found by the victor at the aftermath if it lies at the seat; otherwise it stays lost and remains a source of doubt the next time.

### 4.6 The contest
- **A majority:** a camp holding more than half of all votes takes the seat. Every voter counts one vote, the Grand Elder counts three, and undecided voters count in the total.
- **Otherwise, a trial by combat** between the two largest camps' claimants.
  - Each may name a champion from their backers: the one with the highest realm, or the player if the player backs that camp and accepts.
  - An NPC trial is 4e's `duel_sim`. The player's trial is an ordinary duel with the purpose `{"crisis": occurrence}`.
  - The winner takes the seat.
  - A loser who is `proud` or `hot-tempered` refuses the result with chance 0.5, which starts force of arms.
- **Far away** (§2.4), the contest is settled by one roll:
  - Each claimant's weight is 1, plus 0.5 per proof, plus 0.3 per realm above the weakest.
  - The winner is chosen by weight.
  - Force of arms happens with chance 0.2 if the top two weights are within 0.5 of each other.

### 4.7 Strife
- At most 2 seasons, run by the faction clock while the crisis is at `strife`.
- Each season the two camps clash. A camp's strength is the sum of its backers' realms, plus 1 each. The 4a clash odds decide the winner, and the loser loses one backer (dead or injured, at the 4a rates).
- After each clash the weaker camp yields with chance 0.3 in the first season and 0.6 in the second. A camp with no backers left yields.
- Unresolved after 2 seasons: a schism (§4.8).

### 4.8 Schism
- The losing camp founds a breakaway: a new minor faction of the same type.
  - **Name:** a prefix (`Southern`, `Northern`, `Eastern`, `Western`, `True`, `New`), seeded, plus the old name. The first prefix not already used wins.
  - **Members:** the losing claimant leads it (rank 4). Their backers join it at their ranks, released from the old faction.
  - **Halls:** each branch hall whose keeper backed the losing camp goes with them. Its hall moves to the breakaway, and the new faction's seat is the first of them. With no branch hall, the seat is the losing claimant's home town.
  - **Stance:** −0.8 with the old faction. Both leaders gain an indelible grudge, which passes to kin as 3a grudges do.
  - **Record:** it is a `schism` event with a fact, weight 3.0, and the breakaway's data has `parent`.
- **Caps:**
  - At most 2 breakaways descend from any one faction; a third schism exiles the losers instead (released, wanderers).
  - A breakaway counts as a minor faction toward the per-region cap. Over the cap, the losers are exiled.
- A breakaway is an ordinary minor faction: the 4a clock runs it, and it can be destroyed when weak.

### 4.9 Aftermath
- The winner is promoted to leader (rank 4, role `leader`) and holds the token if found.
- Losers who stay are demoted to rank 2 if they were elders who refused a trial result. Each loser keeps a grudge memory of the winner.
- The chief disciple post empties if its holder won. Otherwise the new leader names one at the next year's naming.
- The faction's `history` gains one line: season, claimants, how it was won, schism.
- `faction.crisis` is cleared.

## 5. Knowledge vs truth

- The public facts are:
  - `crisis`: that it began, who claims, and the trial and outcome; heralded at the mourning, contest and aftermath stages;
  - `schism`, `transmitted`, `named_chief`;
  - `will_read` and `will_burned` (witnessed only).
- The player sees a camp as its claimant and the backers the player has heard of or seen declare. Undecided voters are shown as undecided only if the player has talked to them this crisis.
- Who holds a hidden will, or a lost token, is known only to its holder until someone learns it by seeing it or by rumour.
- `check_people` accepts claimants named in crisis facts the player believes.
- Every crisis fact has a claimant, faction, stage or outcome in its variant, so briefs can narrate it from the variant alone.

## 6. The player's part

### 6.1 Hearing of it
Heralds and rumours carry crisis facts. The sky page lists crises the player has heard of, by stage. The standing page gains a Succession block for each faction the player belongs to that is in crisis (§7).

### 6.2 In a sect they belong to (at the seat, while its crisis is live)
- **Declare for X:** join a camp. Before the contest, the player may change camps once, which gives a grudge memory to the claimant left.
- **Sway a voter** (talk menu; once per voter per stage):

| Way | Lean | Rule |
|---|---|---|
| Speak for X | +0.15 | Chance: 0.4 + 0.5 × the voter's attitude toward the player (bounds 0.1 to 0.9). |
| A gift | +0.2 | Costs 20 × the voter's rank in silver. A `loyal` righteous voter refuses and takes offence (−0.1 attitude memory). A `greedy` voter or one of a dark path counts it double. |
| A threat | +0.25 | Only against a voter of lower realm. The voter gains a grudge memory of the player. |
| Do them a favour | +0.3 | The voter gives an errand from the 3b duties. The sway is spent when it is done, within the stage. |

- **Champion:** accept to fight a camp's trial.
- **Search the chambers:** §4.4.
- **Claim the seat:** during mourning, if the player is rank 2 or more or the named heir. The player becomes a claimant of kind `player`. They lean to themself, and their proofs count like anyone's.
  - If they win, they lead the faction: rank 4, role `leader`, the top stipend, all its arts and its library. They name its chief disciple, and 4a's clock runs the rest.
  - The 3c tools stay with sects the player founded.
  - The `promotion_block` message for rank 3 becomes "Only a crisis opens the leader's seat."

### 6.3 Anywhere
The token (§4.5) can be bought, won or picked up by anyone, member or not, and handed to a claimant at the seat.

### 6.4 A sect the player leads
This is a sect they founded (3c) or an NPC seat they won (§6.2). Three triggers:
1. **Death.**
   - The 4b succession hands the player's posts to the heir. For a sect the player leads, the 4b handover is kept only if the seat is not in doubt. The seat is in doubt if the heir is not a member, an elder is within one realm of the heir or above, or the heir is under 16.
   - With doubt, a crisis starts with the heir as a claimant of kind `player`, and play continues as the heir.
   - If the heir loses and a schism follows, the heir leads the breakaway.
   - In a 3c sect, the voters are its elders.
2. **Absence.**
   - Sealed in a realm, or away from the seat for 8 seasons in a row: an ambitious elder declares a regency (§6.5). It is a `regency` event with a fact.
   - After 8 more seasons, the regent usurps: they are promoted to leader, the player is demoted to elder, and it is a `usurped` fact.
   - The player returning during the regency: the regent hands back the seat, unless ambitious, in which case a crisis starts with the player and the regent as claimants.
   - Returning after the usurpation: the player may claim, which starts a crisis.
3. **Stepping down.**
   - A new action at the seat for a sect's leader: "Step down and name a successor" (a member of rank 2 or more).
   - If the successor's camp would hold a majority (§4.3), it is a clean handover. Otherwise a crisis starts with the successor and the others as claimants.
   - Either way the player becomes a `retired` elder: rank 3, role `retired`, never a claimant in this crisis. They may back and sway.

### 6.5 Regents
- A regent holds the leader's post with role `regent` and data `regent_for`.
- When the heir turns 16, the regent hands it over, unless ambitious (chance 0.5), in which case a new crisis starts with cause `regency`.
- A regent is the leader for everything else (4a power, wars, tournaments).

## 7. Screens

- **The Succession block** (standing page, F-key as today), for each faction the player belongs to that is in crisis:
  - its stage and days left;
  - each claimant with their kind and known proofs;
  - camps as known (§5), the player's declared camp, sways spent this stage, and the will and token as known.
- **The sky page:** a line per crisis heard of: the faction, the stage, and the claimants known.
- **The sheet:** "Chief disciple of X", "Leader of X", "Regent of X for Y", "Retired master of X".
- **Choices at the seat** during a live crisis:
  - Declare for…, Claim the seat, Search the late master's chambers, Champion…;
  - the sways in the talk menu;
  - Buy / Challenge for / Hand over the token.
- **Help:** a line for crises; commands `declare`, `claim`, `step down`, `search chambers`.

## 8. Debug rules (in `check_world`)

`check_crises`:
- At most one live crisis per faction.
- `faction.crisis` names a live `succession_crisis` whose `faction` is that faction.
- A faction with a live crisis has no leader, unless a regent sits.
- The token is in exactly one place: owned by one person, or `located_in` one place.
- At most 2 factions have any given faction as `parent`.
- A player claimant was eligible when they claimed (rank 2 or more, or the named heir, or 4b's heir).
- Every claimant is alive, or the crisis records that they fell.

## 9. Testing

- **Unit tests** per module:
  - `doubt`, each cause;
  - the chief disciple naming;
  - transmission;
  - claimant order and the cap;
  - the Grand Elder;
  - leanings and each proof;
  - will states and search;
  - token places, buying, duels and handing over;
  - the contest (a majority, the trial, refusal);
  - strife and yielding;
  - schism: naming, members, halls, stance, the caps;
  - the aftermath;
  - settling far away;
  - regency, usurpation and return;
  - stepping down;
  - death with an heir in doubt.
- **The player:**
  - declaring, each sway, championing, searching, claiming and winning an NPC seat;
  - `promotion_block`'s new message;
  - the Succession block and the sheet lines.
- **Knowledge:** the player never sees an undiscovered will holder, or camps they have not heard of.
- **Briefs:** a brief narrates each crisis fact from its variant.
- **Fuzz:** `test_a_sect_heir`, a random player in a sect with crises forced, who claims, sways, champions and trades tokens; `crash_count == 0` and no violations.
- **Performance** (with `gc.collect()` first, `process_time`):
  - a faction season with a live crisis costs at most 5 ms more than without one;
  - a turn at a seat during a crisis, at most 2 ms more than a turn elsewhere;
  - the Succession block, under 30 ms;
  - the 500-year soak stays inside its current limit, and nothing is stored per season beyond one history line per crisis.

## 10. Out of scope for 4g

- The murdered leader and the investigation, puppets and cult spies, arbitration and an outsider heir, marriage for legitimacy, forging a will (4h).
- The supreme art and the founder's test (4h).
- The framed heir's return (4h).
- Managing an NPC sect with the 3c tools (the clock runs it).
