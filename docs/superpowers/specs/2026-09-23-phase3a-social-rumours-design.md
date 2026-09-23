# DeepMurim Phase 3a: Social Memory, Rumours, Reputation, Masks

Date: 2026-09-23
Status: Draft, awaiting user review
Parent spec: `2026-09-22-deepmurim-design.md` (§4.1, §5.4, §5.5, §6.0, §8 item 3)
Builds on: phase 2b (merged at `ae3aa53`)

## 1. Goal

The world should *talk about you*. What you do becomes facts. Facts travel as rumours that change as they are retold. Towns build their own picture of who you are. People who never met you treat you according to what they have heard. Killing someone makes their family your enemy. You can lie, and lies can be traced back to you. You can hide behind a mask until someone recognises your fighting style.

Every system also:
- reports its state to the narrator as `Brief` facts plain enough for Haiku (parent §6.0);
- adds rules to `debug/invariants.py`;
- is covered by the fuzz test.

### Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Split | **3a** is social memory, facts and beliefs, rumours, reputation, kin, killing and masks. **3b** is factions: joining, ranks, duties and founding. 3b uses reputation from 3a. |
| Player verbs | Hear rumours, have a reputation, spread or invent rumours, wear masks. |
| Killing | A **Kill** verdict after winning a real fight. NPCs get lazily generated kin and teachers who inherit grudges. The player still cannot die before phase 4: killers leave the player for dead. |
| Rumour spread | Several channels, each driven by tracked data: witnesses, town gossip, kin and teachers, distance over time, and deliberate telling. |

## 2. Architecture

The phase 1–2 patterns continue:
- Pure systems produce `Event`s, `commit` applies them via `@effect`s, briefs feed the narrator, and invariants check the result.
- New engine behaviour arrives as `GameHooks` mixins.

**The chronicle stays ground truth.** Event actors are always the *true* ids, even when masked. Anything the player or an NPC *knows* goes through the knowledge layer (§4, §9). Nothing on screen reads ground truth directly.

### 2.1 Save format version 2

`SCHEMA_VERSION` becomes 2. `World.open` migrates a version 1 save in place, inside one transaction, and then sets `schema_version = 2`. A test opens a version 1 file made by the phase 2b code, as a fixture, and plays a turn.

| Table | Change |
|---|---|
| `facts` | Add `place integer`, `weight real not null default 1`, `true integer not null default 1`, `data text not null default '{}'`. Add indexes on `(subject)`, `(time)` and `(place)`. |
| `beliefs` | Rebuilt: `knower, fact_id, variant_key text, variant text, source integer, confidence real, learned_at integer, hops integer not null default 0, channel text not null`, with primary key `(knower, fact_id, variant_key)`. Add indexes on `(fact_id)` and `(knower)`. |
| `memories` | Add `inherited_from integer`, which is null unless the memory was inherited. |

- `variant_key` is a stable short hash of the canonical JSON of `variant`. It lets one knower hold several versions of the same fact.
- A **town** entity can be a knower. Its beliefs are that town's gossip pool.

### 2.2 New modules

| File | Responsibility |
|---|---|
| `systems/facts.py` | Which events create facts, the predicate list, weights, and `fact_about(world, fact_id)` read helpers. Registers effects that write facts. |
| `systems/memory.py` | `effective_intensity(memory, now)` and the `INDELIBLE` feelings. |
| `systems/beliefs.py` | Storing and reading beliefs: `believe`, `beliefs_of`, `knowledge_of(npc)` (their own beliefs plus their town pool), and confidence words. |
| `systems/rumours.py` | Channels, `catch_up(world, town, now)`, seeded `mutate`, and `pick_news`. |
| `systems/attitude.py` | `attitude(world, npc, subject) -> Attitude(score, word, reason)`. |
| `systems/reputation.py` | `reputation(world, town, subject) -> Reputation(renown, word, path, epithet)`. |
| `systems/kin.py` | `kin_of`, `ensure_kin`, the `died` effect with inheritance, and `avengers_for`. |
| `systems/masks.py` | Personas, `seen_as`, recognition rolls, and wearing and removing the mask. |
| `engine/gossip.py` | The mixin for *Ask about news*, `ask about <name>`, the *Tell…* menu and the Rumours page. |
| `engine/masks.py` | The mixin for wearing and removing a mask, and the status bar marker. |
| `narrate/gossip_text.py`, `narrate/grammar/gossip.toml` | Outcome builders, summaries and grammar for the new events. |

The Kill verdict extends the existing `systems/duel.py`, `engine/fight.py` and `narrate/combat_text.py`.

## 3. Memory and attitudes

### 3.1 Fading
- `effective_intensity(m, now) = m.intensity * 0.5 ** ((now - m.event.time) / HALF_LIFE)`, where `HALF_LIFE = 360` watches, which is 90 days or one season.
- Indelible memories never fade.
- `INDELIBLE = {"hatred", "grief", "saved", "betrayed"}`. `commit` forces `indelible=True` for any witness whose feeling is in `INDELIBLE`.
- Memories are never deleted. The existing `talk` behaviour, such as "met before" and patience, keeps using raw memories, so a faded memory still means "we have met".

### 3.2 Attitude
`attitude(world, npc, subject)` adds up four terms. Each term carries a short reason string.

1. **Memories about the subject** (`seen_as`-filtered, §8): `FEELING_VALUE[feeling] * effective_intensity`.

   | feeling | value | feeling | value |
   |---|---|---|---|
   | grateful, saved | +1.0 | annoyed | −0.4 |
   | respect | +0.6 | contempt | −0.3 |
   | amused | +0.3 | humiliated | −0.8 |
   | sparred, conversed, met | +0.1 | hatred | −1.5 |
   | witnessed_duel | 0 | grief | −1.5 (about the killer) |

2. **Beliefs about the subject**, from `knowledge_of(npc)`: for each believed fact where the subject is the actor, add `JUDGEMENT[predicate] * confidence * weight`. The NPC's traits change the judgement:
   - `kind` and `honest` NPCs judge `killed`, `crippled` and `robbed` twice as harshly.
   - `greedy` and `cunning` NPCs judge them at half.
   - `proud` NPCs add +0.2 for `defeated` a stronger opponent. They respect strength.
3. **Harm to kin.** Harm done to the NPC's kin or teacher counts through the inherited memories and grief the NPC holds (§6), so nothing is counted twice.
4. **Traits:** `kind` +0.2, `hot-tempered` −0.1, and −0.2 if the subject is masked and unrecognised ("hides their face").

`JUDGEMENT` values: killed −1.0 (+0.5 if the victim was a bandit, +0.2 if a beast), crippled −0.7, robbed −0.5 (+0.2 if the victim was a bandit), defeated 0, spared +0.4, fled_from −0.2, lied_about −0.6, owns_manual 0.

**Result bands:**

| score | word |
|---|---|
| ≥ 1.0 | warm |
| ≥ 0.3 | friendly |
| > −0.3 | neutral |
| > −1.0 | wary |
| > −2.0 | hostile |
| otherwise | hateful |

The **reason** is the term with the largest absolute value, turned into a short phrase:
- "heard you crippled a man in Rivermouth"
- "you spared them"
- "you killed their brother"

Neutral with no memories and no beliefs gives no reason.

**Fear** is a separate check. `afraid(world, npc, subject)` is true when the NPC's realm is lower than the subject's *believed* realm and the NPC believes the subject has `killed` or `crippled` someone. The believed realm is the highest realm mentioned in the NPC's beliefs about the subject, or the realm the NPC saw in a duel.

**Uses:**
- Conversation shows the attitude word and reason. The word is a brief fact.
- Greeting grammar is keyed by the band.
- Patience is +1 when warm and −1 when hostile.
- Afraid NPCs refuse challenges and spars (a new refusal reason, `afraid`).
- Hostile NPCs refuse to teach or sell.
- Hateful and hot-tempered or proud NPCs issue grudge challenges. `hatred` is already in `GRUDGE_FEELINGS`; `grief` is added.

## 4. Facts and beliefs

### 4.1 Which events make facts
Facts are written by an effect registered in `systems/facts.py`, chained after the event's existing effect. The existing `EFFECTS` registry holds one function per kind, so `facts.py` wraps the existing function rather than replacing it.

| Event | Fact (subject → object) | Weight |
|---|---|---|
| `duel_ended`, verdict `kill` by the winner | winner `killed` loser | 3.0 (0.5 if the loser is a beast) |
| `duel_ended`, verdict `cripple` | winner `crippled` loser | 2.0 |
| `duel_ended`, verdict `rob` | winner `robbed` loser | 1.0 |
| `duel_ended`, verdict `spare` | winner `spared` loser | 0.5 |
| `duel_ended` in `duel` or `encounter` mode, won | winner `defeated` loser, with data `{loser_realm}` | 0.5 + 0.75 × max(0, realm gap) |
| `duel_ended`, `fled` | player `fled_from` opponent | 0.5 |
| `encounter_resolved`, how `paid` | player `paid_off` bandit | 0.3 (JUDGEMENT −0.1) |
| `recognised` (§8) | persona `is` person | 2.0 |
| `lie_exposed` (§7) | player `lied_about` target | 1.5 |
| `told`, invented (§7) | the invented fact, stored with `true = 0` | the predicate's normal weight |

- NPC-on-player outcomes are facts too. For example "Bandit Ma robbed Hero" comes from a lost fight in which the NPC chose `rob`.
- Spars and tests make no facts.
- A beast is never the subject of a fact.
- `owns_manual` facts are written when a manual changes hands in a fight or purchase. They have weight 0.5, subject = the new owner, and `data.technique_name`.

Fact data holds what the story needs: `{place_name, count: 1, realm, technique_name, mask: persona_id|null}`.

### 4.2 Beliefs
- `believe(world, knower, fact_id, variant, source, confidence, hops, channel)` upserts a belief. If the key already exists, it keeps the higher confidence.
- `knowledge_of(world, npc)` returns the NPC's own beliefs plus the pool of the town they are in. The town pool entries come with `hops + 1`.
- **Confidence** is `CONF_DECAY ** hops * trust`, where `CONF_DECAY = 0.85`:
  - `trust` is 1.0, 0.9 for a `cunning` teller, and 0.7 for a teller the listener rates `wary` or worse.
  - A witness has `hops = 0` and confidence 1.0.
- **Words:**

  | condition | word |
  |---|---|
  | hops = 0 | "you saw it yourself" |
  | confidence ≥ 0.75 | "from a witness" |
  | confidence ≥ 0.45 | "hearsay" |
  | otherwise | "doubtful" |

## 5. Rumours

### 5.1 Channels
All channels write beliefs. None of them touch facts.

1. **Witness.** When a fact is written, every witness of the source event, meaning every owner of a memory row on that event, gets a belief with `hops 0`, `channel "witness"` and the true variant.
2. **Town gossip.** The fact's `place` town gets the fact in its pool with `hops 1`, `channel "gossip"`, straight away.
3. **Kin and teachers.** When a fact's subject or object has kin (§6) who are already materialized, each of them gets a belief straight away, regardless of distance, with `hops 1` and `channel "kin"`. A `killed` fact first materializes the victim's kin (§6), so they always hear.
4. **Distance.** `catch_up(world, town, now)` runs when the player arrives in a town and before any news is picked there. For every fact the town doesn't yet hold:
   - `d` is the Chebyshev region distance between the fact's town region and this town's region;
   - `reach = floor(weight * 1.5)` regions;
   - the fact arrives if `d ≤ reach` and `now ≥ fact.time + d * HOP_WATCHES`, where `HOP_WATCHES = 8`, which is 2 days per region;
   - then the town gets the belief with `hops = d + 1` and `channel "distance"`, with a variant mutated `d + 1` times.

   Facts from the same town are already covered by gossip.
5. **Telling.** The *Tell…* menu (§7), or an NPC telling the player, gives `hops = teller's hops + 1` and `channel "told"`.

**Performance.** `catch_up` queries facts with `time ≤ now - HOP_WATCHES` that the town doesn't hold, in one SQL query using `not exists`. It filters by region distance in Python. The limit is 50 ms with 500 facts, and a test measures it.

### 5.2 Mutation
`mutate(variant, rng, teller_traits) -> variant` is pure. Its rng is `rng_for(world_seed, f"rumour:{fact_id}:{knower}:{hops}")`, so the same world always tells the same story.

- The base chance per retelling is `0.25`, multiplied by 1.5 for `cheerful` or `cunning` tellers and by 0.5 for `honest` or `secretive` tellers. A town pool retelling uses the base chance.
- One mutation is chosen from:

  | mutation | effect |
  |---|---|
  | `exaggerate` | `count` goes 1 → 2–3 ("several"), or `realm` rises one step |
  | `blur_place` | drops `place_name` ("somewhere to the east") |
  | `blur_art` | drops `technique_name` |
  | `misattribute` | at hops ≥ 2 and only for facts with a masked subject: the actor is described only as "a masked fighter" |
  | `soften` | `killed` becomes "nearly killed", but only in the retold variant text |

- **Sensible-ness rule:** a mutation never changes the predicate's family, meaning harm, mercy, flight or identity. It never swaps the victim and the actor, and it never makes a lie true or a truth false. A property-style test over many seeds checks this.

### 5.3 Picking news
`pick_news(world, npc, player)` returns the NPC's belief, from `knowledge_of`, that the player doesn't hold in the same variant:
- It prefers `weight * 0.5 ** ((now - fact.time) / 360)`, the heaviest and most recent.
- It skips facts whose object is the player unless nothing else is left. Being told about yourself is for `ask about <name>`.
- It returns `None` when there's nothing new.
- Hearing it commits a `heard` event, `(player, npc)`, with data `{fact_id, variant, confidence, hops}`, and its effect writes the player's belief.

## 6. Kin, killing, inheritance

### 6.1 Kin
- `kin_slots(world, npc)` is seeded by `f"{npc.seed_path or 'person:'+id}/kin"`. It gives 1–3 slots, each with a `role` from `sibling, parent, child, master, disciple`.
- `master` and `disciple` share no surname, and a `master` is at least one realm higher when possible.
- Each slot has a home. 70% of the time it's the NPC's own town. Otherwise it's a seeded town within 2 regions, and a roamer's kin live in the region's nearest town.
- `ensure_kin(world, npc)` materializes each slot once, through the existing NPC generator with the path `.../kin:{i}`. It shares the surname for blood kin and adds relations `kin_of` (value = role) in both directions.
- Kin are materialized only when needed: a death, `ask about <name>`, or when an NPC with already-materialized kin becomes the subject or object of a fact.

### 6.2 Kill
- After winning a fight in `duel` or `encounter` mode, the verdict menu gains **Kill**. Spars and tests never offer it.
- The fight ends with verdict `kill`, and the `duel_ended` data gets `killed: true`. Kill also takes silver and manuals, the same way `rob` does.
- A new `died` event, `(victim, killer)`, with data `{cause: "killed", place}`, has an effect that:
  1. sets the victim's `data.dead = true` and `died_at`, removes `located_in`, and relates `buried_at` to the place;
  2. writes the victim's own memory `grief`/`hatred` of the event (indelible) so it can be inherited;
  3. `ensure_kin`, then copies every indelible memory of the victim to each kin member, with `inherited_from = victim`, and adds a `grief` memory of the killing event (indelible, intensity 1.0).
- Killing a beast writes only the fact, with weight 0.5, and the beast is marked dead.

**NPC verdicts against the player.** When the NPC holds `hatred` or `grief` toward the player, it chooses `leave_for_dead`: the player is not killed. Extra harm is added up to the "broken" threshold, plus one serious wound, and the fact `left_for_dead` is written with weight 1.5.

### 6.3 Avengers
`avengers_for(world, player)` lists living NPCs who hold `grief` for a killing done by the player, or by a persona recognised as the player. Being recognised only applies to what *they* believe (§8).
- **Same town:** a grudge challenge fires on arrival *and* on look. This fixes the 2b deferred "grudge challenges only on look" for avengers. The chance is 0.6 per moment, and it ignores the trait requirement.
- **Elsewhere:** on each road, if an avenger's home region is within 3 regions of the road's region, an `avenger` encounter happens with chance 0.25, after the normal encounter roll fails.
  - The encounter kind is `avenger`, with no toll.
  - Talk fails unless the avenger is `kind`. Flee works as usual.
  - Winning lets you kill, spare and so on. Sparing an avenger turns their grief into a non-indelible `humiliated`. Grief itself stays, since memories are never deleted, but the avenger stops pursuing for one season.

## 7. The player's verbs

### 7.1 Hearing
- **Ask about news** is added to the conversation choices, as the topic `news`. It commits `heard` or shows "They have heard nothing new."
- It counts toward patience, like other topics.
- **`ask about <name>`**, typed, gives the most confident belief the NPC holds about that person, or about the persona with that name. The player gets the belief. If the NPC knows nothing, the reply is "never heard of them".
- Asking about yourself is how you learn your reputation.

### 7.2 The Rumours page
The journal gains a **Rumours** section, which can also be reached with the typed command `rumours`.
- It lists the player's beliefs grouped by subject, newest first, with the confidence word and the source name ("from Old Wu, innkeeper").
- Conflicting variants of the same fact appear together under one fact line.
- Seeing the event first-hand (`hops 0`), or hearing it from a witness, marks it settled.

### 7.3 Telling and lying
**Tell…** is a conversation submenu with at most 9 choices, with the rest folded into `Turn.extra`.
- **Pass on:** up to 7 of the player's beliefs that the listener doesn't hold.
- **Invent:** pick a predicate (`killed`, `robbed`, `fled_from`, `owns_manual`), then a subject from the people the player has met or believes something about, then an object where it is needed.
  - This commits `told` with `invented: true`, and creates a fact with `true = 0`, `source_event` = the told event and `data.liar = player`.
  - Only the player's variant exists at first.

**Acceptance**, rolled on a seeded rng `f"tell:{fact}:{listener}"`:

`p = 0.5 + 0.2 * clamp(attitude score, -1, 1) + (0.2 if honest else 0) - (0.3 if cunning else 0)`

- `p = 0` if the listener holds a first-hand (`hops 0`) belief contradicting it: same subject and object with a different predicate family, or the listener *is* the subject.
- If accepted, the listener's belief is written (`channel "told"`, source = player), and the town pool gets it with `hops + 1`.
- If rejected, the listener gains an `annoyed` memory ("doesn't believe you").

**Exposure.** A lie is exposed when it reaches someone who knows the truth first-hand: the *subject* of the lie, or a witness of a real event between the same subject and object. That can happen through telling, a town pool during `catch_up`, or kin. Exposure commits `lie_exposed`, `(player, subject)`, which:
- writes a `lied_about` fact (weight 1.5);
- gives the subject a `hatred` memory toward the player (intensity 0.9, not indelible);
- is spread through the normal channels.

Exposure checks run at the end of the `told` effect and during `catch_up`.

## 8. Masks

**Getting and wearing one.**
- Every merchant sells a **mask** for 5 silver. It is an item entity with `data.kind = "mask"`.
- *Wear mask* and *Remove mask* are shown when the player owns a mask. They also exist as the typed commands `wear mask` and `remove mask`.
- The status bar shows `(masked)`.

**The persona.**
- The first time a mask is worn, it creates a **persona**: an entity with kind `persona`, and `data.of = player` as ground truth, which the knowledge layer never reads. It gets a seeded name: `the <Colour>-Masked <Style>`, where Style comes from the form of the player's current art (Swordsman, Fist, Palm, Blade, Spear) or is "Stranger".
- The persona is stored on the mask item, so wearing the same mask always gives the same persona.
- While masked, events keep the true actors but carry `data.as = persona_id`.

**`seen_as(world, observer, event) -> int`** returns the persona id for an event with `data.as`, unless the observer holds a belief of the `is` fact for that persona. Everything that reads memories *for knowledge purposes* goes through it:
- attitude;
- the "met before" greeting;
- reputation (for towns, through the town's beliefs);
- facts, whose subject is the persona when `as` is set;
- briefs about NPC reactions.

When the player is masked, an NPC greets a stranger unless they have recognised the persona.

**Recognition.** Recognition is rolled once per witness per event, seeded with `f"recognise:{event_id}:{witness}"`:
- **Art:** if the witness has a memory of an `exchange` or `duel_ended` involving the unmasked player in which the player used the same technique now used, the chance is 0.5.
- **Voice:** the witness has at least 3 unmasked conversation memories (`met`, `conversed`, `asked`) with the player, and the event is conversation (`met`, `asked`, `heard`, `told`). The chance is 0.3.
- **Changing in public:** wearing or removing the mask in a town. Each NPC present who has a memory of the identity being hidden has a chance of 0.5.
  - The menu label warns with that count: "Wear mask (3 here know your face)".

A success commits `recognised`, `(witness, persona)`, which writes the `is` fact with the witness as a `hops 0` believer. It then spreads like any other fact. Towns that hold the `is` fact count the persona's deeds toward the player's reputation.

## 9. Reputation

`reputation(world, town, subject)` reads **only** the town pool's beliefs whose subject is the given subject, or a persona the town believes *is* the subject.

- **Renown** = Σ `weight * confidence`.

  | renown | word |
  |---|---|
  | 0 | unknown |
  | < 2 | "a few have heard of you" |
  | < 6 | "known" |
  | < 15 | "renowned" |
  | otherwise | "famous" |

- **Path** = Σ `PATH[predicate] * weight * confidence` / renown. It is "righteous" at ≥ 0.3, "ruthless" at ≤ −0.3, and "hard to read" otherwise.
  - `PATH`: killed bandit +1, killed other −1, killed beast +0.3, crippled −0.7, robbed bandit +0.2, robbed other −0.6, spared +0.5, defeated 0, fled_from −0.2, lied_about −0.5, paid_off −0.1, left_for_dead −0.8.
- **Epithet**, once the subject is renowned or better: `<Adjective> <Noun> of <Place>`, seeded by `f"epithet:{subject}:{town}"`.
  - Adjective comes from the path. Righteous: Jade, Azure, White, Upright. Ruthless: Crimson, Blood, Black, Iron. Hard to read: Wandering, Grey, Silent.
  - Noun comes from the form of the art in the subject's heaviest fact (Fist, Palm, Sword, Blade, Spear, Hand), defaulting to "Hand".
  - Place is the place of the heaviest fact.
  - Different towns can therefore use different epithets.

**Effects.**
- Reputation is a brief fact in town scenes and conversations: "people here know you as the Crimson Palm of Rivermouth".
- `afraid` (§3.2) uses the believed realm.
- Bandits with realm < the player's believed realm, whose home town rates the player renowned or better, **back off**. This is a new `encounter_resolved` result with how `backed_off`. It needs no fight and writes no fact.
- **Rivals:** proud NPCs at least one realm higher issue challenges to a player who is renowned in their town, with chance 0.2 per look or arrival. This uses the existing challenge flow, reason `rival`.
- Teachers who are `kind` or `honest` refuse a player whose path here is ruthless.

**F4 sheet.** A **Reputation** block shows this town's renown word, path and epithet. It also lists personas the player wears, with what this town believes about each.

## 10. Narration

- New outcome builders cover `heard`, `told`, `died`, `recognised`, `lie_exposed`, `mask_on`/`mask_off` and `backed_off`.
- The `duel_ended` builder gains kill and left-for-dead lines.
- Rumour text is built from the variant only. The builders get the variant, never the fact row. Examples:
  - "They say a masked fighter killed several men near Rivermouth."
  - "Old Wu heard that you crippled Bandit Ma. (hearsay)"
- Summaries cover the journal. Grammar lives in `gossip.toml`.
- Brief facts include the attitude word with its reason, and the reputation line. The Haiku limits stay: at most 6 facts, at most 1,200 characters, no ids.

## 11. Debug rules (added to `debug/invariants.py`)

1. `check_knowledge`: every person or persona name in a turn's text belongs to someone the player has met, is present, or appears in one of the player's beliefs. A persona's true identity never appears next to the persona's name unless the player holds the `is` belief. The player always knows their own personas.
2. Every belief points to an existing fact. Every `true = 0` fact has `data.liar` and a `source_event`.
3. Dead NPCs have no `located_in`. They are never the partner of a conversation, a challenger or an encounter opponent, and they never appear in `people_at`.
4. Every memory with `inherited_from` set points to a dead entity.
5. No belief has confidence outside 0–1 or negative hops. A witness belief has hops 0.
6. Every persona's `data.of` is the player. No outcome line of an event with `data.as` names the player to anyone who hasn't recognised the persona. This is checked through `seen_as` for every witness.

## 12. Testing

- A unit test file for each new module.
- **Migration:** a version 1 fixture save opens, migrates to version 2, and plays a turn.
- **Determinism:** the same seed and the same actions give identical rumour variants after a save, reload and replay.
- **Mutation sensible-ness:** a property test over 2,000 seeded mutations.
- **Performance:** `catch_up` over 500 facts takes under 50 ms.
- **Knowledge isolation:** a scripted test with a masked kill in town A. Travel to town B and check that the brief, journal, rumours and F4 never name the player as the killer until an `is` belief exists.
- **Gossip fuzz:** 300 random turns weighted toward killing, lying, masking and travelling, with every invariant passing.
- The existing tests stay green. Tests that assumed the 2b verdict set are updated as rulings.

## 13. Out of scope for 3a
- NPCs travelling on their own and background world ticks that spread rumours between towns without the player (phase 4). `catch_up` is written so phase 4 can call it from a tick.
- Factions, sect reputation and entry trials (3b).
- Player death (phase 4).
- The Claude layer (phase 6), which will read beliefs through the same knowledge layer.
