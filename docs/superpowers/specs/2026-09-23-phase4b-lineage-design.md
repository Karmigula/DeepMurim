# DeepMurim Phase 4b: Lineage

Date: 2026-09-23
Status: Draft, awaiting user review
Parent spec: `2026-09-22-deepmurim-design.md` (§5.8 lineage and death; §8 item 4)
Builds on: phase 4a (merged at `2ff9cac`): the world clock, families, agendas.

## 1. Goal

Your character can die: of age, by an enemy's hand, of qi deviation, or at the executioner's block. Death is not the end of the story. You pick an heir from the people you bound to yourself (children, disciples, sworn siblings, sworn followers), who takes up your wealth, your arts, your name and your enemies. Or you begin again as a newcomer in the same remembering world, or in a new world. The old you stays in the world, buried and remembered.

Every system:
- reports to the narrator in `Brief` facts plain enough for Haiku;
- adds rules to `debug/invariants.py`;
- is covered by the fuzz test.

### Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Death | All four causes: old age, killed in a fight, qi deviation, execution. |
| Heirs | All four kinds: children (with player marriage added), disciples, sworn siblings, sworn followers. |
| Inheritance | All four parts: wealth and land, arts (partial), name and reputation, enemies and debts. |
| After death | **The player chooses**: continue as an heir, a newcomer in the same world, or a new world. |

## 2. Architecture

- **The player is a person like any other.** Succession moves world meta `player_id` to the heir's existing person and sets `is_player` on them. The old player entity stays: `dead`, buried, with its full history.
- **No save-format version change.** New keys:
  - player data: `age` (float), `lived_to`, `ancestors` (list of ids, oldest first), `named_heir`, `spouse_refused` (`{person: season}`), `dying` (the pending death, while the death screen is open);
  - kin roles `sworn_sibling` (its own inverse), `spouse` (4a), and `master`/`disciple` (3a);
  - fact `heir_of` (subject = heir, object = ancestor).

### 2.1 New modules

| Module | Role |
|---|---|
| `systems/mortality.py` | Player aging and the death roll; kill verdicts; lethal deviation; capital trials; the `player_died` event. |
| `systems/bonds.py` | Proposing marriage, taking a disciple, swearing siblinghood, naming an heir; the heir-candidate list. |
| `systems/succession.py` | The inheritance table, the switch of player, `heir_of`, the newcomer start. |
| `systems/lineage.py` | Half-strength inheritance of reputation, attitude, faction standing, avengers and bounties: `inherited(world, knower, heir) -> list[(ancestor, factor)]`. |
| `engine/lineage.py` | `LineageMixin`: bond verbs in conversation, the death screen (a gated state), the F8 lineage page. |
| `narrate/lineage_text.py`, `narrate/grammar/lineage.toml` | Outcome lines, journal summaries and grammar for every new event kind. |

## 3. Death

### 3.1 Old age

- The player ages 0.25 per season. The player's `lived_to` follows the 4a clock: the seasons run each time the world clock runs, in the engine's `_after_commit`.
- Lifespan and death chance use 4a `lives.LIFESPAN` and `lives.death_chance(age, realm)`, where realm is the player's body realm. Rolls are seeded by `life:player:{id}:{n}`.
- **Warnings.** Once within 10 years of the lifespan, the first season logs "Your hair has gone white." The status line shows "(lifespan near)" after the age.

### 3.2 Killed in a fight

`duel.npc_verdict` gains `kill`. When the player loses a duel or an encounter (not by yielding):

| Opponent | Kill chance |
|---|---|
| Holds a grudge (3a `hateful`) | 0.5 |
| Is a sect hunter or bounty hunter hunting the player | 0.3 |
| Is ruthless (bandit, or cunning and greedy) | 0.1 |
| Anyone else | 0 |

Only the highest row that applies counts. A kill verdict commits `player_died` with the opponent as killer.

### 3.3 Qi deviation

When a deviation event brings deviation to its limit (100), the player dies with chance 0.5 (`cause: "deviation"`). Otherwise the existing 2a outcome stands (a damaged meridian).

### 3.4 Execution

- A town bounty of `CAPITAL = 150` or more makes an arrest capital. The arrest then offers only: *Stand trial*, *Fight your way free*, *Try to flee*. Paying and serving time are not offered.
- **Stand trial:** executed with chance 0.5, seeded by `trial:{player}:{time}`. Otherwise the player is imprisoned for 2 years: time advances 8 seasons, both clocks run, and the town's crimes are atoned.
- **Losing** the arrest fight on a capital charge means execution (`cause: "executed"`, killer = the constable).

### 3.5 The moment of death

- `player_died` (actors: killer or the player, then the player; data `cause`, `age`) records the death.
  - Its effect marks the player `dead` and buries them at the place.
  - Its listener writes the fact `died` or `killed` (weight 3.0; the player is notable), so kin grieve and rumours spread through 3a.
- The player's `dying` data holds `{cause, killer, place, time}` until a choice is made. The engine enters the **death screen**.

## 4. Heirs

### 4.1 Bonds

| Bond | Verb (in conversation) | Requires | Result |
|---|---|---|---|
| Marriage | *Propose marriage* | adult 18–50, unmarried, not kin, attitude ≥ 0.5, not refused this season | accepted with chance = attitude; `married` (4a) |
| Personal disciple | *Take them as your disciple* | age 12–30, attitude ≥ 0.3, no living master | `took_disciple`; kin `master`/`disciple` |
| Sworn sibling | *Swear brotherhood* or *sisterhood* | adult, attitude ≥ 0.7, not already sworn | `sworn_siblings`; kin `sworn_sibling` both ways |
| Named heir | *Name them your heir* | a valid candidate (§4.2) | player data `named_heir` |

- A refused proposal sets `spouse_refused[person] = season`. Asking again in the same season is refused at once.
- **Children.** 4a `birth_events` runs from the NPC spouse when the couple includes the player (the NPC rolls, whatever the ids). Children are born in the spouse's town.
- **Sect disciples** (3c members, roles disciple and elder) count as disciples. **Sworn followers** are people with `sworn_to` = the player (3c).

### 4.2 Candidates

`candidates(world, player)` lists living people aged 14 or over, each at most once, in this order:
1. the named heir;
2. children, eldest first;
3. personal disciples, then sect disciples and elders, by loyalty then age;
4. sworn siblings;
5. sworn followers.

The death screen shows the first 8.

## 5. Succession

### 5.1 The inheritance table

| | Named heir or child | Disciple | Sworn sibling | Sworn follower |
|---|---|---|---|---|
| Silver | 100% | 75% | 50% | 50% |
| Items and manuals (owned relations) | all | all | all | all |
| Land (`owns_land`, town owner) | all | all | all | all |
| Your sect (3c) | leads it | leads it | leads it | leads it |
| Arts: completeness taught | 0.7 | 0.7 | 0.5 | 0.3 |

- Silver not inherited is lost. The old player keeps nothing: silver 0, no items, no land.
- **The sect.** The heir becomes its founder and leader (rank 4). If the heir was a member of it, their old membership is replaced. An heir openly in another martial faction is `released` from it.
- **Arts.** Each martial art the old player knew is taught with 2b `teach(..., source="inheritance")` at `min(1.0, known completeness × factor)`. An art the heir already knows keeps the higher completeness.

### 5.2 The switch

A `succession` event (actors: the old player, the heir) does the following:
- sets `is_player` off on the old player and on for the heir;
- sets world meta `player_id` to the heir;
- appends the old player to the heir's `ancestors`, after the old player's own ancestors;
- clears `dying` and `named_heir`;
- gives the heir `age` and `lived_to` if they have none;
- writes the fact `heir_of` (weight 2.0).

The engine then rebuilds its state around the new player: focus, submenu and fight state are cleared. It narrates the succession and shows the heir's town.

### 5.3 Newcomer and new world

- **Newcomer:** 1a character creation (name, origin, points), then a new player person in a random town within 3 regions of the place of death, seeded by `newcomer:{old player}`. No inheritance, no `heir_of`, no ancestors.
- **New world:** back to the title screen. The save stays on disk.

## 6. Half-strength inheritance

`lineage.inherited(world, knower, heir)` returns `[(ancestor, 0.5)]` for each ancestor of the heir that the knower believes the heir descends from. Belief means the knower, their town or their faction's towns hold `heir_of`. Otherwise it returns `[]`. It is used in five places:

| Place | Effect |
|---|---|
| 3a `reputation(world, town, heir)` | adds `0.5 ×` the ancestor's renown there. If the heir has no epithet of their own, they are called "heir of the {ancestor epithet or name}". |
| 3a `attitude(world, npc, heir)` | adds `0.5 ×` the attitude terms from the npc's memories about the ancestor. |
| 3b `standing(world, faction, heir)` | adds `0.5 ×` the faction's standing toward the ancestor. |
| 3a `avengers_for(world, heir)` | people grieving a killing by an ancestor hunt the heir, at half the usual chance. |
| 3b `law.bounty(world, town, heir)` | adds `0.5 ×` the ancestor's bounty in that town. |

`heir_of` spreads like any fact, and kin learn it at once through channel 3.

## 7. Screens

- **Status line:** `age N`, with "(lifespan near)" within 10 years of the lifespan.
- **F8 lineage page** (also typed `lineage`):
  - ancestors (name, epithet, cause of death, age at death);
  - spouse; children; disciples; sworn siblings; sworn followers (name, age, realm, town);
  - the named heir;
  - "If you died today:" and the first 3 candidates.
- **Death screen:** a gated state. Only its choices work: the heirs (up to 8), *A newcomer in this world*, *A new world*. Saving and loading keep it open (`dying` is in the save).
- **Journal:** summaries for `married` (with the player), `born` (to the player), `took_disciple`, `sworn_siblings`, `named_heir`, `player_died`, `succession`, `imprisoned`.
- **Briefs:** a person's brief gains the relation to the player ("your son", "your sworn sister", "your disciple"). The player's brief gains "heir of X" once they are an heir.

## 8. Debug rules

1. Exactly one living person has `is_player`, and it is `player_id`. While the death screen is open, the player is dead and has `dying`.
2. Every ancestor is dead and buried.
3. Spouse links that include the player are mutual; the player has at most one living spouse.
4. A `named_heir` is alive and a valid candidate. The engine clears it when that stops being true.
5. After a succession, the old player has 0 silver and owns no items or land. Every item and town has at most one owner.

## 9. Testing

- Unit tests for:
  - each death cause and its odds;
  - kill-verdict precedence;
  - capital arrests, trial and prison;
  - each bond verb and its refusals;
  - children with the player;
  - the candidate order;
  - every cell of the inheritance table;
  - arts completeness;
  - the five half-strength uses.
- The death screen: all three paths; save and load while it is open.
- Old saves: the player gets `age` from their data (18 if missing) and lives from the current season; no ancestors.
- **Fuzz:** a "short, dangerous life" run. Kill chances and aging are raised, so the fuzzer dies and succeeds many times; every debug rule is checked every turn.
- **Speed:** a succession takes under 100 ms; the lineage page with 30 relatives takes under 50 ms.

## 10. Out of scope for 4b

- Divorce, concubines, adoption.
- Playing as a child under 14.
- Heirs of NPCs (NPC succession is 4a's faction clock only).
- Resurrection, reincarnation and ghosts.
