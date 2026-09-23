# DeepMurim Phase 3c: Founding Your Own Sect

Date: 2026-09-23
Status: Draft, awaiting user review
Parent spec: `2026-09-22-deepmurim-design.md` (§5.6 founding, §8 item 3)
Builds on: phase 3b (merged at `3c20521`): factions, halls, standing, duties, politics, law.

## 1. Goal

You can found a sect of your own. You earn a name, get land, gather sworn followers, and register a charter. Then you run it: recruit and teach disciples, raise elders, build halls, and keep the treasury alive. While you roam, the sect lives on, and returning shows what happened: disciples grew or deserted, recruits arrived, rivals came to the gate. Other factions judge your sect by what its people do, just as they judged you.

Every system:
- reports to the narrator in `Brief` facts plain enough for Haiku;
- adds rules to `debug/invariants.py`;
- is covered by the fuzz test.

### Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Sect life | All four: recruit and teach, doctrine and rules, treasury and land, and the sect against the world. |
| Time | **Catch-up on return.** A deterministic seasonal catch-up runs for the player's sect only. Phase 4's world clock will reuse it. |

## 2. Architecture

The 3b patterns continue. There is **no save-format change**.

| Thing | Stored as |
|---|---|
| Your sect | Faction entity of type `player_sect`, tier `minor`. Data holds: `path` (chosen), `taboos` (list), `trial` (a 3b trial kind), `ranks` (a preset ladder), `treasury`, `power`, `buildings` (`{name: {done_at, built}}`), `last_tick`, `founder`, `dissolved`, `chronicle` (the last 12 season summaries). |
| Land | Relation `owns_land` from the player to a town. Each town has at most one owner, shown in the town's data as `owner`. |
| Disciples and elders | Persons with `member_of` the sect (role `disciple` or `elder`, rank 0–3). The sect-specific parts live in the person's data: `talent` (0.5–1.5), `loyalty` (0–100), `on_duty` (bool) and `sect_joined_at`. |
| Sworn followers | Persons whose data holds `sworn_to = player` (before founding). |
| Pacts | Fact `allied_with` (subject is your sect, object is the other faction) plus a `pact` relation in both directions. |

`player_sect` is added to 3b's tables:
- `MARTIAL`, so joining one sect still excludes others;
- `LADDERS`, as the chosen preset;
- `PATHS`, which is read from data for this type.

It is **not** in `STAFFED`, because its staff are the disciples you recruit, not seeded staff.

### 2.1 New modules

| File | Responsibility |
|---|---|
| `systems/land.py` | Land prices, buying, ruins, claiming (with a contest), seizing a minor faction's seat, and `owner_of(town)`. |
| `systems/founding.py` | Sworn followers, founding requirements, the charter, founding choices, and creating the sect. |
| `systems/sect.py` | Roster limits, recruiting, teaching, raising elders, buildings, the treasury, pacts, `sect_stance`, and dissolution. |
| `systems/sect_seasons.py` | `advance_sect(world, sect, now)`, the seasonal catch-up engine. |
| `engine/sect.py` | `SectMixin`: the founding menu, management choices, catch-up triggers and the ledger page (typed `ledger`, or F7). |
| `narrate/sect_text.py`, `narrate/grammar/sect.toml` | Outcomes, summaries and grammar. |

## 3. Land

| Town kind | Price |
|---|---|
| village | 150 silver |
| town | 400 silver |
| city | 900 silver |

- **Buying:** *Buy land here* is offered by the town's imperial keeper, the magistrate. It needs the town to have no owner and no great-faction seat. Buying commits `land_bought`, which pays the magistrate and sets `owns_land`.
- **Ruins:** each region that is not home to a great faction has a 0.3 seeded chance of an **old hall**. It sits in a seeded town of that region, and the town's data shows `ruin: true`. The scene line reads "An abandoned hall stands at the edge of town."
- **Claiming:** *Claim the old hall* is free when you are in a ruin town.
  - If the region has a minor faction, its leader contests the claim: a duel with `purpose={"claim": town}`. Winning claims the land.
  - With no minor faction, you claim at once.
- **Seizing:** *Seize this seat* appears when talking to the leader of a minor faction whose seat is this town.
  - It starts a duel with `purpose={"seize": faction}`.
  - Winning dissolves that faction (`dissolved = true`, every member's status becomes `expelled`), gives you the land, and writes the fact `seized` (weight 2.5). The scattered staff get `wronged` memories.
  - A righteous path counts `seized` as ruthless (reputation `PATH["seized"] = -0.8`).

## 4. Founding

### 4.1 Sworn followers
- *Ask them to follow you* is a conversation choice with any non-staff, non-member NPC whose attitude toward you is friendly or better.
- The chance is `0.2 + 0.1 × renown_band + 0.2 × path_match − 0.2 × (already sworn elsewhere)`, rolled with a seed:
  - `renown_band` is 0 for unknown, then 1 to 4 for little known through famous;
  - `path_match` is 1 when their traits suit your reputation path (kind or honest for righteous; cunning or hot-tempered for ruthless; any trait for neutral).
- Success commits `sworn` with a `grateful` memory and sets `sworn_to`. Followers stay where they live until you found the sect, then move to the seat.

### 4.2 Requirements
*Found a sect* is offered by a magistrate in the town where you own land. It is refused with the first failing reason:
1. You must own land here.
2. You must be renowned in this town (renown ≥ 6).
3. You must be at least Second-rate.
4. You must not be an open member of a martial faction.
5. You need 3 sworn followers who are alive.
6. You need 200 silver for the charter.

### 4.3 Choices
The founding runs as a **submenu sequence**, like 3a's *Invent*:

| Step | Options |
|---|---|
| Name | 3 seeded suggestions (built from the 3b name parts with "Sect", "Hall" or "Gate"), or a typed name, 3–30 characters |
| Path | righteous, neutral or ruthless |
| Taboos | choose 2 of 5: `never_kill_unarmed`, `never_teach_outsiders`, `never_spare_cultists`, `never_rob`, `never_desert_a_duel` |
| Trial | spar, errand, ears, fee or blood (the 3b kinds) |
| Ranks | one of 4 ladder presets (orthodox, clan, beggars, cult) |

Confirming commits `sect_founded`, which does all of the following:
- pays the charter;
- creates the faction, with `seat` = your land town, `founder` = player, `treasury = 0`, `power = 20` and `last_tick = now`;
- makes the player a member at rank 4 with role `leader`;
- turns the sworn followers into disciples (`member_of`, rank 0, loyalty 60, `talent` seeded) and moves them to the seat;
- adds the seat town to the town's `halls` and `seats`;
- sets stances toward every great faction from your path: righteous uses the orthodox sect's row, ruthless uses the demonic cult's row, and neutral is 0 everywhere;
- writes the fact `founded` (weight 3.0).

## 5. Running the sect

These choices are offered in the Faction matters… submenu at your seat, when talking to one of your disciples or elders.

**Recruiting.**
- *Invite them to your sect* works on any non-member, non-staff NPC anywhere whose attitude toward you is neutral or better. It succeeds with the §4.1 chance, using your sect's renown in *their* town. The trial chosen at founding is shown as the terms they accept; recruits are not put through a playable trial in 3c. On success, `joined` makes them a disciple with loyalty 50, and they move to the seat.
- **Roster limits:** 12 disciples and 3 elders.

**Teaching.**
- *Teach an art* passes one of your martial arts that the disciple doesn't know (existing `teach`). It commits `sect_taught_by_you`.
- The first 3 distinct arts you teach become the sect's `arts`, its signature arts.
- The sect's `never_teach_outsiders` taboo is about *your* disciples teaching. Only you teach in 3c.

**Elders.**
- *Raise to elder* needs a disciple at rank ≥ 2, or realm ≥ Third-rate, with loyalty ≥ 60. Elders are capped at 3.
- While you're away, elders teach disciples your sect arts (see §6), at one art per disciple per season, if you have a library.

**Duty assignment.**
- *Send on sect duties* and *Call back* toggle a disciple's `on_duty`. A disciple on duty is away and cannot be talked to.

**Expelling.** *Expel* writes `expelled` (the 3b left event) for that disciple. They get a `wronged` memory and leave the seat.

**Treasury and buildings.**
- The *Sect ledger* shows the page (§8).
- *Build <building>* starts construction if the treasury covers the cost. It is `done_at` one season later.
- *Deposit silver* moves 50 or 200 of your silver into the treasury. *Withdraw silver* takes 50 back out, from the treasury only.

| Building | Cost | Upkeep per season | Effect |
|---|---|---|---|
| training_yard | 150 | 10 | growth × 1.5 |
| library | 200 | 10 | elders teach sect arts while you are away; `library` at the seat also lends sect arts (3b) |
| infirmary | 150 | 10 | injury chance × 0.5; a disciple with an injury heals at the next season |
| guest_hall | 100 | 5 | +1 recruit roll per season; renown gain from the season summary +50% |
| walls | 300 | 15 | gate event chance × 0.5; gate fights get +1 fighter |

**Pacts.**
- *Propose an alliance* is offered to a great faction's recruiter when that faction's view of your sect (`sect_stance`) is ≥ 0.5.
- Success commits `allied_with`: a pact in both directions, a fact, and stance set to at least 0.6.
- Allies never send gate challengers. They send a gift of 30 silver each season.

**Dissolution.** Your sect dissolves (`sect_dissolved`: `dissolved = true`, fact weight 2.0) when either:
- you *Disband the sect* (a confirm-twice choice) or desert it (3b desert);
- the roster reaches 0 disciples and 0 elders at a season's end.

You keep the land.

## 6. The seasonal catch-up

`advance_sect(world, sect, now) -> list[Event]` processes each whole season (360 watches) from `last_tick` to `now`, at most **8 per call**; the rest wait for the next call. It is triggered by:
- arriving at the seat;
- look at the seat;
- opening the ledger;
- talking to an elder anywhere.

Each season `n` uses `rng = rng_for(world_seed, f"sect:{sect}:season:{n}")` and resolves in this order. The results are collected into one `sect_season` event, plus separate events for deaths (`died`), desertions (`expelled` status `deserter`), gate duels (`gate_fight`) and recruits (`joined`).

1. **Buildings:** anything with `done_at <= season end` is marked built.
2. **Money:**
   - income = land (village 20, town 40, city 80) + 20 × successful duties (step 6) + 30 × each ally + protection 10 if your sect's standing in the seat town is welcome or better;
   - upkeep = 5 × disciples + 10 × elders + building upkeep;
   - `treasury += income − upkeep`. If the treasury would go below 0, it stays at 0 and the season is **unpaid**.
3. **Growth:** for each member who is not on duty, energy years gained = `0.25 × talent × (1.5 if training_yard) × (1.2 if they know a sect art)`, applied with the existing `realms.add_energy(body, years)`.
   - A disciple who hits a bottleneck rolls a breakthrough at `breakthrough_chance(body, met=True)` with the 2a rules, and moves one realm up on success.
   - The body is saved through `save_body`, so the realm label stays consistent.
4. **Injuries:** each member is injured with chance 0.08, or 0.04 with an infirmary: a `bruise` or `cut` of severity 2 (`add_injury`). An infirmary heals existing injuries.
5. **Loyalty:**
   - +5 paid, −15 unpaid;
   - +5 path match, −10 path mismatch (§4.1 rule);
   - +5 if their attitude toward you is warm, −10 if wary or worse;
   - clamped to 0–100.
   - A member at loyalty < 25 deserts with chance 0.5.
6. **Duties:** each member on duty succeeds with chance `0.5 + 0.1 × realm_index`.
   - Success: `power += 2`, and its silver goes into step 2.
   - Failure: injury with chance 0.3, **death** with chance 0.05 (`died`, killer = none, `cause: "duty"`; their kin grieve under 3a).
7. **Recruits:** the roll count is `{unknown: 0, little known: 1, known: 1, renowned: 2, famous: 3}` by your sect's renown in the seat town, +1 with a guest hall.
   - Each roll recruits with chance 0.5, up to the roster limit.
   - A recruit is a seeded NPC generated at the seat (path `sect:{id}:recruit:{n}:{i}`) with loyalty 50 and seeded talent.
8. **Gate events:** the chance is `0.15 + 0.25 × (any faction with sect_stance ≤ −0.5)`, × 0.5 with walls. When one fires:
   - a challenger (a seat disciple of the most hostile faction, or else a seeded wanderer) duels your best member present, worked out with `duel_sim.simulate` on their fighters;
   - with walls, the best two members fight in turn;
   - a win gives `power += 5`, and the fact `defended_gate` names your sect;
   - a loss gives `power −= 5`, the loser is injured, there is a 0.1 chance of death, and the fact `gate_breached` is written.
   - If you are present at the seat when the event would fire, the challenger instead issues a normal 2b challenge to *you* on the next look.

Each season appends a one-line summary to the sect's `chronicle`, for example "Spring of year 3: +40 silver; Wang Li broke through to Third-rate; a recruit arrived; the Blood Lotus Cult's envoy was driven off." The `sect_season` outcome shows the lines for the seasons it processed (at most 4 shown, then "and N more seasons").

**Idempotence.** `last_tick` advances by exactly the seasons processed. Processing 8 seasons at once gives the same world as processing one season 8 times, because every roll is seeded by season number.

## 7. The sect in the world

`sect_stance(world, other_faction, sect) -> float` is **computed**:
- base: the stance set at founding from your path;
- plus 0.1 × (number of beliefs in the other faction's knowledge, from 3b `knowledge_about` over every member of your sect including you, where your people *harmed* its members), capped at −1;
- minus 0.05 × the same count for harm to its enemies, capped at +1;
- a pact sets the floor at 0.6.

The ledger shows it, gate events use it, and pacts check it.

Your sect's **reputation** (renown and path in a town) is 3a `reputation` summed over its members' identities. The sect's own facts (`founded`, `defended_gate`, `gate_breached`, `seized`) use the sect as their subject, so rumours carry the sect's name and the guest hall's bonus reads those facts.

## 8. Screens

- **Ledger** (typed `ledger`, or F7):
  - the sect's name, path, taboos and trial;
  - treasury, with last season's income and upkeep;
  - buildings, including ones still under construction;
  - the roster (name, rank title, realm, loyalty word — devoted, loyal, uneasy or disloyal — and on duty or injured);
  - relations (each great faction's `sect_stance` in words: allied, friendly, neutral, hostile or enemy);
  - the last 6 chronicle lines.
- **F6 standing page:** gains a line "Your sect: <name> at <seat>, N disciples, power P."
- **Scenes:** your seat town adds "Your sect, the <name>, keeps its hall here." and the gate art.
- **Briefs:** add one fact, "You lead the <name>, N disciples strong."

## 9. Debug rules

1. A non-dissolved player sect has exactly one leader (the player), and a seat the player `owns_land`.
2. The roster has at most 12 disciples and 3 elders. Every living member is located at the seat unless `on_duty`. Dead members have no `member_of` with status `member`.
3. `last_tick` ≤ `world.time`. The treasury is ≥ 0.
4. A town has at most one `owns_land` owner.
5. A dissolved sect has no member with status `member`.

## 10. Testing

- A unit test file for each module.
- **Land:** buy, claim with and without a contest, seize.
- **Founding:** each requirement fails in turn; founding succeeds; followers become disciples and move to the seat.
- **Management:** recruit, teach, raise an elder, build, deposit and withdraw, ally, expel, disband.
- **Seasons:** income and upkeep arithmetic, unpaid seasons, growth with and without a training yard, injuries and the infirmary, loyalty and desertion, duties and death, recruits, gate events with and without walls.
- **Determinism:** 8 seasons in one call match 8 one-season calls.
- **Fuzz:** a "sect founder" run where the player starts with land, renown, realm and followers set up, founds, then plays 300 random turns including long rests and travel, with every rule passing.
- **Speed:** catch-up over 8 seasons with 15 members takes under 200 ms.

## 11. Out of scope for 3c

- Your sect rising to great tier, succession, or elders splitting off (phase 4).
- NPC factions founding or losing sects on their own (phase 4).
- Territory beyond the seat, wars between sects, and sieges (phase 4).
- Custom art creation *for* the sect beyond the 2b inventing you already have.
