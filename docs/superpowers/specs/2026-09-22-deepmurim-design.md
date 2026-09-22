# DeepMurim — Design Spec

Date: 2026-09-22
Status: Draft, awaiting user review

## 1. Purpose

A Murim (wuxia martial world) text RPG built to fix two problems:

1. **RPGs run out of depth.** Handwritten content ends.
2. **AI roleplay forgets and drifts.** An LLM's memory is its context window, and it contradicts itself.

DeepMurim answers both:
- **Deterministic simulation.** It owns every fact and stores it in a database, so nothing is forgotten.
- **Seeded lazy generation.** The world never ends, yet the same place is always the same place.
- **Optional Claude layer.** Claude writes richer prose and proposes new content. It reads facts from the database through tools, and the engine validates everything it proposes. Claude never becomes the source of truth.

### Success criteria
- An NPC you wronged 200 in-game years ago is remembered correctly by their grandchildren's sect.
- Travelling in any direction always finds new towns, sects, and people. Revisiting them shows exactly what you left.
- The game is fully playable offline with AI off.
- With AI on, Claude never states something that contradicts the database, because proposals that contradict state are rejected.
- The art frame docks left or right with one key.

## 2. Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Narration | Hybrid: procedural text always works; AI enrichment is optional |
| AI backend | Claude Code CLI (`claude -p`), Haiku by default; an optional small DeepMurim MCP server for proposals |
| Tracking bar | State is tracked and pre-digested well enough that Haiku writes adequate prose from a `Brief` alone (§6.0) |
| Input | Numbered context choices plus a typed command line |
| Presentation | Same as AsciiCrawler: Python 3.14, pygame-ce character-grid window, IBM Plex Mono |
| Depth systems | Cultivation & body, social web & grudges, living world, martial arts creation, factions (join/found), lineage & death, knowledge vs truth, heart & karma, items & crafts with history |

## 3. Architecture

### 3.1 Layers

```
 ┌──────────────── presentation (render/) ───────────────┐
 │ status bar | art frame (L/R) | narrative log | choices │
 └───────────────▲───────────────────────────┬───────────┘
          prose + art        │  Action
 ┌───────────────┴──────┐    ┌───────────────▼───────────┐
 │ narrate/             │◄───│ engine (systems/, world/) │
 │  procedural (always) │ Ev │  validate → apply → Events │
 │  bridge (claude -p)  │    └───────────────┬───────────┘
 └──────────┬───────────┘                    │
            │ MCP tools (read + propose)      ▼
     ┌──────▼───────────┐          ┌──────────────────┐
     │ mcp_server/      │─────────►│ SQLite .world    │
     └──────────────────┘  read    └──────────────────┘
```

- **The engine is the only writer.** Everything else reads, or submits *proposals* to the engine.
- **Every state change is an `Event`.** Events are appended to the `chronicle` table and applied to the state tables in one transaction.
- **Systems are pure** in the sense that each is `handle(db_view, action_or_event) -> list[Event]`. They are tested against a temporary database without pygame.

### 3.2 Directory layout

```
deepmurim/
  main.py, config.py, paths.py, settings_store.py
  render/   screen.py layout.py art.py hud.py menu.py
  world/    db.py events.py seed.py lod.py gen/{region,town,npc,sect,item,names}.py
  systems/  time.py travel.py talk.py cultivation.py body.py techniques.py combat.py
            social.py knowledge.py factions.py economy.py items.py crafts.py
            karma.py lineage.py
  narrate/  procedural.py grammar/*.toml bridge.py proposals.py
  mcp_server/server.py
  assets/   fonts/ art/*.art
  tests/
```

## 4. World model

### 4.1 Storage
- One SQLite file per world: `saves/<name>.world`, in WAL mode.
- Autosave happens implicitly, because every turn commits a transaction.
- Schema version lives in `meta`. Migrations are numbered SQL files.

Core tables (phase 1). Later phases add tables; none reshape these.

| Table | Key columns | Purpose |
|---|---|---|
| `meta` | key, value | world_seed, schema_version, current_time, player_id |
| `entities` | id, kind, name, seed_path, created_at, data JSON | NPCs, places, sects, items, techniques: anything with identity |
| `relations` | a, b, kind, value, since, data | parent_of, disciple_of, member_of, located_in, owns, sworn_sibling… |
| `chronicle` | id, time, kind, actors JSON, place, data JSON, weight | Append-only event log; the world's history book |
| `memories` | owner, event_id, feeling, intensity, decays | Which events an entity remembers and how they feel about them |
| `facts` | id, subject, predicate, object, time, source_event | Ground truth ("X killed Y", "Manual Z is forged") |
| `beliefs` | knower, fact_id, variant JSON, source, confidence, learned_at | What each entity *thinks* is true (may be wrong) |
| `materialized` | seed_path, entity_id | Which seeded places/people exist as records |

`data JSON` holds system-specific fields, so new systems don't need schema churn. When a system needs to query something often, it gets a proper table.

### 4.2 Seeded lazy generation
- `seed_for(world_seed, path) = blake2b(f"{world_seed}/{path}")`. Example paths: `region:3,-2`, `region:3,-2/town:1`, `region:3,-2/town:1/npc:7`.
- The world is a grid of regions. Each region deterministically has terrain, towns, sects, and wandering figures.
- **Unmaterialized.** A place or person exists only as a function of its seed. Generating it twice gives an identical result, which is covered by a test.
- **Materialized.** A record is written the first time the player observes or affects something, or when the world sim needs it. From then on the database wins over the seed.
- This is what makes the world infinite and stable at the same time.

### 4.3 Time and level of detail (phase 4)
- Time is kept in *days*. Actions cost time: travel costs days, secluded cultivation costs months, and time skips can run years.
- **Near zone** is the player's region plus its neighbours, simulated in full.
  - Every materialized NPC there runs daily or weekly agendas: cultivate, trade, feud, travel.
- **Far zone** is every materialized entity outside the near zone.
  - It runs coarse seasonal statistics: sect power drifts, NPCs age and gain realms by expectation, wars roll outcomes.
  - The results are written as summarized chronicle events.
- **Unmaterialized** places are never simulated. When one materializes, generation takes the current date into account, so it has plausible history.

## 5. Depth systems

Each system: what it tracks, and how it touches others.

### 5.1 Cultivation & body (phase 2)
- **Tracked:**
  - Dantian: capacity, purity, and qi attributes (yin/yang plus the five elements).
  - 12 regular and 8 extraordinary meridians, each open, blocked, damaged, or scarred.
  - Realm and sub-stage, bottlenecks, comprehension insights, and constitution (special bodies).
  - Injuries: location, severity, whether permanent, and effects.
  - Qi deviation risk.
- **Rules:**
  - Breakthroughs need qi, insight, and a condition specific to the bottleneck (a trial, a resource, or a heart state).
  - Failure injures meridians.
  - Permanent injuries are never healed, only worked around.

### 5.2 Martial arts creation (phase 2)
- A **technique** is an entity made of parts:
  - A stance or footwork.
  - A qi route: an ordered list of meridians.
  - A form: palm, sword, saber, finger, and so on.
  - An element or intent.
  - Tiers of mastery.
- **Compatibility** = the technique's route compared with your open meridians, your qi attributes, and your constitution. Incompatible practice builds deviation risk.
- **Create:** combine insights with parts you know. **Merge:** fuse two techniques and pay a cost. **Teach:** pass it to a disciple, as a relation plus a copy. **Steal or observe:** partial knowledge from watching.
- **Manuals** are items that carry a copy of a technique, which may be *incomplete* or *altered*. This links to knowledge vs truth.

### 5.3 Combat (phase 2)
- Turn-based exchanges in text.
- Choices: technique, stance, feint, qi output, and yield or flee.
- Outcomes feed injuries, reputation, memories, and karma.
- Duels have witnesses; witnesses create beliefs and rumors.

### 5.4 Social web & grudges (phase 3)
- **Memories:** an NPC gains one whenever it witnesses or hears of an event about something it cares about.
  - Intensity decays over time, except for events flagged `indelible` (killings, betrayals, saved lives).
- **Attitudes are computed, not stored:** a sum over memories, relations, faction stance, and personality.
- **Grudges and debts are inherited.** When an NPC dies, their indelible memories pass to kin and disciples, who hold them as `inherited` memories with a feeling attached.
- **Blood feuds** are therefore emergent, not scripted.

### 5.5 Knowledge vs truth (phase 3)
- `facts` hold ground truth; `beliefs` hold what someone thinks.
- **Rumor spread:** each season, beliefs travel along social edges and through towns.
  - Each hop may *mutate* the belief: exaggerate, misattribute, or drop details, with lower confidence.
- **Hidden identities, masks, and disguises:** a masked figure is a separate *apparent* entity linked by a hidden fact.
- **Hard rule:** the UI, procedural narration, and the MCP server see only the player's beliefs.
  - Ground truth is shown only when the player learns it. Tests enforce this.

### 5.6 Factions (phase 3)
- Sects, clans, beggars' guild, merchant guilds, government, demonic cults, and orthodox alliance.
- **Each faction tracks:**
  - Power, wealth, and territory.
  - Doctrine: allowed techniques and taboos.
  - Hierarchy of ranks and seats.
  - Relations with other factions.
  - Treasury and signature techniques.
- **Joining:** entry trials fitted to the faction, then ranks and duties, with internal politics between factions inside the sect.
- **Founding:** requires reputation, land (claim, buy, or seize), resources, and at least N disciples. The sect then becomes a full faction in the world sim.

### 5.7 Living world & economy (phase 4)
- Prices are set per town from supply (the region's resources), demand, and events such as wars and famines.
- **Scheduled world events:** Murim tournaments on a cycle, secret-realm openings, sect succession crises, and heavenly phenomena.
- NPCs pursue agendas: goals drawn from personality plus circumstance.

### 5.8 Lineage & death (phase 4)
- Death is recorded as a chronicle event.
- The player then picks an heir from their children, disciples, or sworn siblings (the relations graph).
- The heir inherits some items and techniques, and inherits memories *about* the old character; the world inherits everything.
- If no heir exists, the player starts a new character in the same world, and the old character's legend lives on in rumors.

### 5.9 Items & crafts with history (phase 5)
- Notable items are entities with provenance: the chain of creator and owners, events they took part in, and a grade.
- **Crafts:** alchemy (pills with toxicity), forging, medicine, and formations. Each is a skill with recipes that can be discovered and improved.
- A famous weapon's legend travels as beliefs, so people recognize it.

### 5.10 Heart & karma (phase 5)
- **Dao heart:** stability, plus obsessions (tags such as `vengeance:X` or `pursuit:strongest`) and heart demons that grow from unresolved obsessions and traumas.
- **Karma:** threads linking you to entities you have strongly affected. Threads raise the odds that the world sim routes events toward you, such as meeting a victim's son.
- Tribulations at major realms draw on your heart state and karma.

## 6. Narration

### 6.0 Briefs: the engine thinks, the writer only writes
**Requirement:** tracking has to be good enough that a small model (Claude Haiku) can write adequate short prose from it. So every narrator receives a finished **`Brief`** and never touches the database. Nothing is left to infer.

- The engine builds one `Brief` per event and per scene description (`narrate/brief.py`). It contains:
  - `kind`, `when` (a readable date), and `place`: name, kind, region, terrain, season, watch.
  - `player` and `other`, each a `PersonBrief`:
    - name, role, traits, realm;
    - `toward_player`: one word or phrase such as "stranger", "acquaintance", or "familiar face". Phase 3 widens this to the full attitude scale.
  - `details`: pre-rendered strings the prose may use, such as `topic`, `dest`, `days`, `times_ordinal`, `first_met_season`.
  - `facts`: **at most 6** plain-English sentences, ranked by salience, all written from what the player knows. Example: "You first met Li Wei in the spring of year 1."
- **Rules for briefs:**
  - No entity ids, no JSON blobs, and no ground truth the player hasn't learned. Briefs are the knowledge-isolation choke point.
  - Every fact is self-contained and true according to the database.
  - `Brief.to_prompt()` renders a labelled plain-text block of at most 1,200 characters.
- **Salience ranking** (grows by phase):
  - indelible memories (killings, betrayals, debts of life);
  - active grudges and obligations;
  - first meeting;
  - recent events;
  - count of encounters;
  - the other person's traits.
- **Why:** the hard work (memory, recall, relevance) happens in deterministic code that can be tested. The model only has to phrase given facts, which any model can do, and which a bigger model does more beautifully.

### 6.1 Procedural (always on)
- A grammar in TOML files (Tracery-lite: `#symbol#` expansion and `{field}` slots) keyed by event kind.
- Slots are filled only from `Brief` fields and `details`.
- It produces prose for every event and scene, deterministic per `brief.salt`, so reloading shows the same text.

### 6.2 ASCII art
- `.art` files are plain text. Inline colour markup `{jade}…{/}` uses palette keys, lines starting with `;` are comments, and spaces are transparent.
- **Layered scene composition:** sky (by time of day) → terrain → settlement, bottom-aligned. Season and weather layers come later.
- **NPC portraits** are composed from part libraries (hair or headwear, face, robe), chosen by NPC seed. Faction colours come in phase 3.
- The art frame is fixed at 40 columns by the frame height. Art is clipped or centred to fit.

### 6.3 Claude layer (phase 6)
- **Runner:** `narrate/bridge.py` runs, on a background thread:
  ```
  claude -p "<instructions + brief.to_prompt()>" --model <setting, default haiku> --output-format json
  ```
  - The prose task needs **no tools**: the brief is complete.
  - Instructions: write 1–3 sentences, use only the facts given, never invent names or events, and keep to wuxia tone.
- **Model:** a setting, **Haiku by default** for speed and cost. Sonnet or Opus are optional for richer prose.
- **Optional MCP tools** (`mcp_server/`), for bigger models and non-prose tasks only (content proposals, free-text interpretation):
  - Read tools, all filtered through the player's knowledge: `get_entity`, `get_memories`, `chronicle_search`, `get_relations`.
  - Propose tools: `propose_dialogue`, `propose_npc`, `propose_rumor`, `propose_action`.
- **Proposals** go to a `proposals` table.
  - The engine validates each one: entities exist, nothing contradicts facts, power levels are plausible, and the schema is valid.
  - Proposals that pass become Events; rejects are logged.
- **Output check** on prose: a reply that names a person or place not in the brief is discarded, and the procedural text stays. This is cheap, and it catches small-model invention.
- **Fallback:** procedural text shows immediately, and Claude's prose replaces it when it arrives.
  - On timeout (8 s by default), an error, a failed output check, or AI toggled off, the procedural text stays.
- **Free-text commands:** when AI is off, the keyword parser handles them. When on, Claude maps the text to one of the current numbered choices, or to a `propose_action`.
- **Interfaces fixed in phase 1:** `Brief`, the `Narrator` protocol (`narrate(brief) -> lines`), and the proposal dataclasses.

## 7. Presentation

- **Rendering:** a pygame-ce grid window adapted from AsciiCrawler `render/screen.py` (20px cells, IBM Plex Mono, resizable, F11 fullscreen).
- **Layout** (`render/layout.py`, pure and testable):
  ```
  ┌──────────────────── status: name · realm · date · place ────────────────────┐
  │ ART FRAME (≈40 cols)        │ NARRATIVE LOG (scrollback, word-wrapped)      │
  │                             │                                               │
  ├─────────────────────────────┴───────────────────────────────────────────────┤
  │ 1) Enter the teahouse  2) Ask about the Blood Lotus Sect  3) Leave town     │
  │ > _                                                                         │
  └─────────────────────────────────────────────────────────────────────────────┘
  ```
- **Keys:**
  - F2 swaps the art frame to the other side; the setting persists in `settings.json`.
  - F3 hides the art frame.
  - PgUp/PgDn scroll the log.
  - Digits pick a choice. Typing goes to the command line and Enter submits.
- **Overlay screens:** character sheet (`c`), chronicle/journal (`j`), relations (`r`), and techniques (`t`). They open from the command line or hotkeys when the line is empty.

## 8. Phases

Each phase gets its own implementation plan and is playable at its end.

1. **Foundation:**
   - Window, layout, and the dockable art frame; choices plus command line.
   - SQLite database, chronicle, and seeded generation (regions, towns, NPCs, names).
   - Travel, look, and basic talk; the NPC remembers meeting you.
   - Procedural narration, the art loader with a few scenes and portraits, and save/load/new world.
   - The `Narrator` and proposal interfaces.
2. Cultivation, body, techniques, combat.
3. Social memory, knowledge and rumors, factions (join and found).
4. Time and level of detail, economy, world events, lineage and death.
5. Items with history, crafts, heart and karma.
6. Claude layer: MCP server, bridge, validation, free-text interpretation.

## 9. Testing

- `pytest`. Systems are tested headless against a temporary `.world` database.
- **Generation stability:** the same seed and path give an identical entity, across runs and processes.
- **Knowledge isolation:** property tests confirm that no UI, narration, or MCP output contains a fact the player doesn't believe.
- **Brief quality:**
  - Every brief's facts are true according to the database.
  - Briefs contain no entity ids, `to_prompt()` stays within 1,200 characters, and there are at most 6 facts.
  - Phase 6 adds a small golden set: fixed briefs run through Haiku, and the output check must pass on each.
- **Persistence:** save, reload, and state is identical (hash of all tables).
- **Soak** (phase 4 on): 500 in-game years headless. No exceptions, database growth stays bounded (the far-zone summary compacts old detail), and factions still exist.
- **Render:** layout and text builders are tested without pygame, following the AsciiCrawler pattern.

## 10. Out of scope (for now)

- Multiplayer, mobile, and the web version (AsciiCrawler's web layer could be ported later).
- Voice or sound.
- Sprite packs (the grid supports them later through AsciiCrawler `render/packs.py`).
