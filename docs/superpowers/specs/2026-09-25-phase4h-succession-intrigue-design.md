# DeepMurim Phase 4h: Succession Intrigue

**Status:** design approved in brainstorming (2026-09-25). Builds on 4g (succession crises) on master at b5932dc, and on 3b (framing, spies, law), 4b (marriage), 4e (secret facts, exposure) and 3c (sworn followers).

## 1. Goal

4g's crises gain a hidden layer: truths the world does not yet know, which the player can uncover, expose, exploit or bury.

- A master may have been poisoned.
- A claimant may be a rival sect's puppet, a disciple a cult's spy, a will a forgery.
- A rightful heir may have been framed and cast out, only to return years later.
- New ways to the seat: the sect's supreme art, the founder's test, marriage into the master's line, an arbiter's verdict, an outsider named heir.
- The player plots too, and lives with the risk of being found out.

### Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Uncovering a murder | Both: clues the player gathers, and a truth that can leak on its own or be buried by the killer. |
| Who plots | An ambitious claimant, a rival sect, demonic cult spies, and the player. |
| Legitimacy's weight | Mixed: the founder's test settles the seat; the supreme art +0.6; marriage +0.3; an arbiter's verdict binds unless defied. |
| The framed heir | World and player: NPC heirs framed and returning, and the player framed, returning, helping or framing. |
| Approach | A lasting `plot` entity per hidden truth, with its clues and secret fact; crises and people point at it. |

## 2. Architecture

### 2.1 New modules
- `systems/plots.py`: the plot entity, the open-plots index, the secret fact, clues, leaks, burial, exposure and accusation.
- `systems/murder.py`: the poisoned master, and the murder's clues.
- `systems/puppets.py`: puppets and cult spies.
- `systems/legitimacy.py`: the supreme art, the founder's test, marriage, arbitration, an outsider named heir.
- `systems/frames.py`: the forged will, framing, exile and the return.
- `systems/scheming.py`: the player's plots.
- `engine/intrigue.py`: `IntrigueMixin` (choices, talk extras, handlers).
- `narrate/intrigue_text.py` and `narrate/grammar/intrigue.toml`.

### 2.2 The plot entity
- `kind = "plot"`, name like "the poisoning of X". Its data:
  - `type`: `murder`, `puppet`, `spy`, `frame` or `forgery`;
  - `plotter` (a person), `patron` (a person or faction behind them, or none), `target` (the victim, the framed, the sect spied on), `faction` (the sect it concerns), `serves` (the claimant it helps, or none);
  - `made_at`, `clues` (a list of `{kind, points_to, found_by}`), `known_by` (people who know the truth);
  - `state`: `open`, `exposed`, `buried` (every clue lost), `cold` (a trail gone cold), or `void` (the plotter died, or nothing is left to find);
  - `fact`: the secret fact of the truth (recorded with `spread = False`, as 4e's fixes).
- The meta row `open_plots` lists the ids of open plots. Seasonal hooks read only it.
- A crisis's data gains `plots` (the ids of plots bearing on it).

### 2.3 The seasonal hooks (faction clock)
Over open plots only:
- **Leak:** 0.1 a season: the truth reaches someone at the faction's seat, who believes it, and it spreads as rumour from there.
- **Burial:** 0.15 a season, if the plotter is alive and free: one unfound witness clue's witness goes missing (vanished, as 4e's). The loss of a witness is itself a clue ("a witness gone missing") pointing at the plotter.
- **A spy's year:** once a year, a spy steals one of the sect's arts for their cult with chance 0.1 (the cult gains the art in its `arts`).
- **The trail goes cold:** a murder or forgery plot open 40 seasons turns `cold`.
- **Returns:** a framed heir's `returns_at` season (§6.3).

## 3. Clues, accusation, exposure (the common rules)

- A clue is found by a specific action (each plot type names its clues below). The finder believes the plot's secret fact at 0.5 confidence (a suspicion) and learns the name the clue points to.
- **Suspicion:** the player holds a suspicion of a person when at least one found clue points at them. **Accusation** needs two found clues pointing at one person.
- **Accusing** is an action at the faction's seat, before the elders, during a live crisis of that faction or (for spies and frames) at any time:
  - **true** (the accused is the plot's plotter): the plot is exposed (§3.1);
  - **false:** the player's merit with the sect drops by 30, the accused gains an indelible grudge memory of the player, and a `proud` or `hot-tempered` accused challenges them to a duel.
- **Exposure** (`plot_exposed`):
  - the plot's state becomes `exposed`, and its secret fact is published (recorded again with `spread = True`, weight 2.5);
  - the plotter is struck from any claim they hold in a live crisis of that faction;
  - each type's own consequence (§4-6) follows;
  - whoever exposed it gains standing with the sect (a `grateful` memory of them for its elders, intensity 0.5).
- An NPC who knows a plot's truth and is a claimant or voter in a live crisis of that faction exposes it at the contest with chance 0.5 (plots known by more than one NPC: 0.8).

## 4. The poisoned master (`murder`)

- When a staffed faction's leader dies of `age` or `illness`, a seeded roll (0.25) makes it a poisoning, if anyone has a motive: an ambitious elder or keeper, a faction at war with this one (stance −0.8 or worse), or a cult spy in its halls (§5.2).
- The plotter is drawn from those with a motive, the patron being their faction (for a rival sect's agent) or none.
- The world sees a natural death. 4g's `doubt` gains a cause, `suspicion`: a murdered leader's seat is always in doubt.
- **Clues** (all point at the plotter):

| Clue | Where | Found by |
|---|---|---|
| `body` | The late master's body lies in state at the seat during the mourning. | "Examine the late master's body", once per player per crisis. Chance 0.6 + 0.1 per realm above the first; the poison names its kind (the Tang clan's black lotus, a cult's blood-venom) and so the plotter's faction or kind. |
| `witness` | A seeded person at the seat (a disciple or servant) saw the plotter at the master's door. | Asking that person "about the night the master died" (talk menu), when the player knows of the murder (holds any clue or suspicion) or has heard the whispers of poison. |
| `motive` | The plotter's quarters at the seat. | "Search {name}'s quarters", once a season, when the player suspects them. Chance 0.5. |

- **Exposed:** the murderer, a claimant, is struck from the claims; if a member, expelled (`expelled`); a `murdered` fact (weight 3.0) names them; a rival sect's hand sets both sects' stance to −1.0; the victim's kin inherit a grudge.

## 5. Puppets and spies

### 5.1 Puppets (`puppet`)
- When a crisis begins, a faction hostile to the one in crisis (stance −0.5 or worse) within 3 regions of its seat backs one claimant with chance 0.3 (the claimant it has the best attitude to, else the weakest).
- **Silver:** the puppet's camp gives one gift-sway (4g's gift rules) to each voter of rank 2 or more at the mourning's end.
- **Fighters:** the patron lends its strongest elder as the puppet's champion for a trial, and one more backer's strength in strife.
- **If the puppet wins:** the faction's stance toward the patron rises to +0.3 (set, not added), and while the puppet leads, the faction clock does not start clashes between them.
- **Clues:** `silver` (asking a voter who took the gift, via the talk menu, when the player suspects a puppet or knows of one), `envoy` (the patron's agent, a seeded member of the patron sect placed at the seat during the crisis, questioned via the talk menu).
- **Exposed:** every voter's lean toward the puppet drops by 0.5 (a foreign creature), and the patron's stance with the faction falls by 0.3.

### 5.2 Cult spies (`spy`)
- Once a year (the first season), for each pair of a materialized demonic cult and a materialized orthodox sect at stance −0.5 or worse, the cult plants a spy with chance 0.02: an existing keeper or disciple (seeded) becomes secretly the cult's (`spy_of` on the person).
- **In peacetime:** a spy's year (§2.3) may steal an art.
- **In a crisis:** a spy is a murder motive (§4), and backs a cult puppet if there is one.
- **Clues:** `night` (a witness saw them outside the walls at night; asking that witness), `mark` (the cult's mark among their things; "Search {name}'s quarters").
- **Exposed:** the spy is expelled (`spy_exposed`, as 3b), the sect's stance toward the cult falls by 0.2, a `spy_exposed` fact (weight 2.5).
- A spy's plot lasts across crises until exposed or the spy dies (`void`).

## 6. Forgery, framing and the return

### 6.1 The forged will (`forgery`)
- When no true will was read (4g's will state `none`, `hidden` or `held` by someone else), a `cunning` claimant forges one naming themself with chance 0.3 at the mourning's end. The crisis's will becomes `{state: "read", names: forger, forged: plot}`, and counts as the will's proof.
- **Clues:** `seal` ("Examine the will", at the seat while a will is read: chance 0.3 + 0.1 per point of comprehension over 5), `scribe` (a seeded calligrapher in the seat's town who wrote it; asking them about the will).
- **Exposed:** the will becomes `{state: "forged"}` (no proof for anyone), and the forger is struck from the claims.

### 6.2 Framing (`frame`)
- In a crisis, a `cunning` claimant may frame another claimant (chance 0.15, once per crisis, at the canvass's start): a false crime (`stole the sect's art` or `killed a disciple`) is recorded as a fact the sect believes. The framed claimant is expelled, struck from the claims, and leaves for a town 3-6 regions away.
- **Clues:** `planted` (the planted evidence, found by searching the framed person's quarters before they leave, or by the framed heir), `false_witness` (the seeded witness who swore to the crime; asking them).
- The framed person's data: `framed = {plot, faction, returns_at}`, with `returns_at` a seeded season 12-40 after.

### 6.3 The return
- At `returns_at`, if the framed person is alive and not sealed: they travel back to the seat, and a new 4g crisis starts (cause `return`), claimants the returned heir (kind `returned`) and the current holder.
- Their proof: `the truth` (+0.5) if the frame was exposed while they were away; otherwise they carry the `planted` clue themselves (found by them), and may expose the frame at the contest with the 4g NPC rule (§3).
- **The player framed:** a crisis the player claims in may frame them (the rule above, with the player as the framed claimant): cast out as an NPC would be. The player may clear their name by exposing the frame (its clues), and may return to demand the seat by an action at the seat any time after 4 seasons: a crisis (cause `return`) with the player and the holder.

## 7. The new ways to legitimacy

- **The supreme art:** each great staffed faction has one, a top-grade technique made lazily and seeded at `world:{faction}:supreme_art`.
  - The leader knows it whole; a chief disciple named 4 seasons or more knows it at 0.5 completeness (taught at the yearly naming).
  - At a leader's death, a manual of it lies in the late master's chambers with chance 0.5; 4g's chamber search may find it (instead of the will, if both are there, the first search finds the will).
  - A claimant who knows it at 0.5 or more carries the proof `supreme_art`: +0.6 lean. Far summaries count it as a proof.
- **The founder's test:** at each great faction's seat.
  - During the mourning or canvass, any claimant may attempt it once: NPC claimants who are ambitious try with chance 0.3 at each stage's change; the player tries by an action at the seat.
  - Passing: chance `0.02 + 0.08 × (realm − 2) + 0.02 × (comprehension − 5)`, bounded 0.02 to 0.5.
  - Passing settles the seat at once (the crisis is settled, how `founder`).
  - Failing: the claimant is struck from the claims, and dies with chance 0.3 (cause `founder_test`), else is injured (a player gains a severe injury; an NPC's realm drops by one).
- **Marriage:** a claimant married (4b `married` bond) to the late master's child carries `married_line`: +0.3 lean.
  - During the mourning, an unmarried NPC claimant marries an unmarried adult child of the late master with chance 0.2.
  - The player marries by 4b's proposal.
- **Arbitration:** when the contest has no majority, a righteous faction (the Murim Alliance, else the nearest orthodox sect) arbitrates with chance 0.3 before any trial.
  - The arbiter names the claimant with the highest lean, weighed as a voter with no attitude (proofs and realm only).
  - The verdict settles the seat (how `arbiter`), unless the named loser is `proud` and defies it (0.5): then force of arms (4g strife), and a `defied_arbiter` fact (weight 2.0) the righteous judge by.
- **An outsider named heir:** a dying leader with no chief disciple names a respected outsider with chance 0.1: the materialized martial wanderer of the seat's region with the best reputation, at the leader's realm or above.
  - The outsider claims as `outsider`, and the will (if any) names them.
  - The faction's own voters lean −0.2 against an outsider.

## 8. The player as plotter (`scheming`)

Each is an action with a `*_block` and `*_events`, making a plot like any other (clues left, leaks, exposure).

| Scheme | How | Effect |
|---|---|---|
| Poison | Buy a `poison` item (50 silver) from an unorthodox clan's keeper at their seat. In conversation with a staffed faction's leader, "Slip poison into their tea". | They die in the night of an `illness`: a murder plot, the player plotter. The crisis that follows is in doubt (`suspicion`). |
| Plant a spy | Send a sworn follower (3c) to join a sect in secret, 100 silver. | A `spy` plot, the player patron. Each season the spy reports one hidden truth of that sect's plots (the player comes to know it); in its crises the spy is a voter in the player's camp and sways for them once a stage. |
| Back a puppet | In another faction's crisis, fund a claimant: 10 × the faction's power in silver. | A `puppet` plot, the patron being the player's own sect if they lead one, else the player. Its effects as §5.1; if it wins, the stance toward the player's sect +0.3, and the new leader gains a `grateful` memory of the player. |
| Frame a rival | During the mourning or canvass, pay 100 silver for false evidence against a claimant. Succeeds with chance 0.4 + 0.1 per point of the player's comprehension over 5, bounded 0.1 to 0.8. | The rival is framed (§6.2), and may return years later. A failed attempt leaves a `planted` clue pointing at the player. |
| Forge the will | §6.1, 100 silver to a scribe. | A read will naming the player's choice. |

- **When the player's plot is exposed:** a fact of the deed (`poisoner`, `spymaster`, `framer`, `forger`, `puppet_master`), weight 3.0; the righteous judge it; the victim's kin inherit a grudge; if the player belongs to the faction, they are expelled; the seat's town sets a bounty (3b law, 100 silver).
- **NPCs investigate:** at each stage's change of a crisis bearing a player's plot, each camp that has found a clue of it rolls 0.15 to expose it (§3).

## 9. Knowledge vs truth

- A plot's truth is known only to the plotter, its patron, and those who found it out or heard it leak.
- A clue's words name the person it points to; finding it makes the player know that name (the clue's belief carries the name in its variant).
- The Succession block's "What you have found" and "Suspicions" show only the player's clues; the tales of exposures are ordinary facts.
- `check_people` accepts names in the player's clues.

## 10. Level of detail

- Plots are made near and far.
- Far crises (4g's summary): an exposed plotter cannot win; a puppet's patron counts as a proof (+1 weight); the supreme art and marriage are proofs; the founder's test is tried by ambitious claimants with its chance, and passing wins.
- Spies are planted only between materialized factions.
- Returns happen wherever the framed heir is; the crisis they start is near or far by 4g's rule.
- The leak, burial and spy hooks run over the `open_plots` index only.

## 11. Screens

- **The Succession block** gains, for crises bearing plots the player knows of: "What you have found" (each clue in words, with the name it points to) and "Suspicions" (people at least one clue points at).
- **"Your schemes"** (the standing page): the player's own open plots, and the clues each could be found by.
- **Choices at the seat:** examine the body, search someone's quarters, accuse, attempt the founder's test, examine the will; the schemes where they apply.
- **The talk menu:** ask about the night the master died, ask about the will, ask about the gift, buy a poison, slip poison into their tea.
- **Tales and briefs** for exposures, returns, the founder's test and arbitration; briefs carry the player's suspicions at the seat.

## 12. Debug rules (`check_plots` in `check_world`)

- `open_plots` lists exactly the plots whose state is `open`.
- Every plot's plotter, target and faction exist.
- A spy (`spy_of`) is a member (status member) of the faction they spy on until exposed or dead.
- An exposed plot's plotter is not a claimant of any live crisis of that faction.
- Every clue points at its plot's plotter, or at a missing witness's clue kind (`missing`).
- A framed person's `returns_at` is in the future while their plot is open.

## 13. Testing

- **Unit tests** per module: plot creation and the index; each clue's finding and chance; accusation true and false; exposure's consequences per type; leaks, burial, the trail going cold; murder at a leader's death and the `suspicion` doubt; puppets (silver, fighters, the pocket stance, exposure); spies (planting, theft, exposure); forgery (seal, scribe, void will); framing, exile and the return (NPC and player); the supreme art (knowledge, manual, proof); the founder's test (pass, fail, death); marriage; arbitration (verdict, defiance); the outsider; each player scheme and its exposure.
- **Knowledge:** clue words never name an unknown person; the Succession block's suspicions only from the player's clues.
- **Far:** a far crisis with an exposed plotter and a puppet.
- **Fuzz:** `test_a_plotting_heir`: a member who poisons, frames, forges, spies, funds, accuses and examines at random through forced crises; no crash, no rule broken.
- **Performance** (CPU time, `gc.collect()` first): the plot hooks with 50 open plots under 5 ms a season; a turn at a seat with plots at most +2 ms; the 500-year soak within its limits.

## 14. Out of scope

- Plots outside succession (assassinations for other reasons, spies in non-orthodox factions).
- The player being a spy for another faction beyond 3b's secret membership.
- Trials of the founder's test as a fought duel (it is a roll).
