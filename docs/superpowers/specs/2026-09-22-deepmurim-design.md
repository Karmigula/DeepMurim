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
| AI backend | Claude Code CLI (`claude -p`) plus a small DeepMurim MCP server |
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

### 6.1 Procedural (always on)
- A grammar in TOML files (in the style of Tracery) keyed by event kind and context tags: season, weather, realm gap, attitude.
- It produces prose for every event and for scene descriptions.
- It is deterministic per event id, so reloading shows the same text.

### 6.2 ASCII art
- `.art` files: plain text with an inline colour markup such as `{c:jade}…{/}`, plus a header for size and anchor.
- **Layered scene composition:** sky → far mountains → structures → foreground. It depends on terrain, time of day, season, and weather.
- **NPC portraits** are composed from part libraries (face, hair, headwear, robe, weapon), chosen by NPC seed and faction colours.
- The art frame is fixed at about 40 columns by the frame height. Art is clipped or centred to fit.

### 6.3 Claude layer (phase 6)
- **Runner:** `narrate/bridge.py` runs, on a background thread:
  ```
  claude -p "<scene brief>" --output-format json --strict-mcp-config \
    --mcp-config deepmurim/mcp.json --allowedTools "mcp__deepmurim__*"
  ```
- **Scene brief:** a compact JSON of the current scene. Claude pulls anything further through tools.
- **MCP read tools:** `get_scene`, `get_entity`, `get_memories`, `player_beliefs`, `chronicle_search`, `get_relations`.
  - All of them are filtered through the player's knowledge, so Claude can't leak ground truth.
- **MCP propose tools:** `propose_prose`, `propose_dialogue`, `propose_npc`, `propose_rumor`, `propose_action` (for free text).
  - Proposals go into a `proposals` table.
  - The engine validates each one: entities exist, nothing contradicts facts, power levels are plausible, and the schema is valid.
  - Proposals that pass become Events; rejects are logged.
- **Fallback:** procedural text shows immediately, and Claude's prose replaces it when it arrives.
  - On timeout (8 s by default), an error, or AI toggled off, the procedural text stays.
- **Free-text commands:** when AI is off, a small keyword parser handles them. When on, Claude interprets them into a `propose_action`.
- **Interfaces fixed in phase 1:** the `Narrator` protocol and the proposal dataclasses, so phase 6 plugs in without reshaping anything.

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
- **Persistence:** save, reload, and state is identical (hash of all tables).
- **Soak** (phase 4 on): 500 in-game years headless. No exceptions, database growth stays bounded (the far-zone summary compacts old detail), and factions still exist.
- **Render:** layout and text builders are tested without pygame, following the AsciiCrawler pattern.

## 10. Out of scope (for now)

- Multiplayer, mobile, and the web version (AsciiCrawler's web layer could be ported later).
- Voice or sound.
- Sprite packs (the grid supports them later through AsciiCrawler `render/packs.py`).
