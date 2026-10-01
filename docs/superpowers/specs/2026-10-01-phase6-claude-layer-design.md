# DeepMurim Phase 6: The Claude Layer

**Status:** design approved in brainstorming (2026-10-01); amended after 6a (§13). Phase 6 is three sub-phases, each with its own plan and merge:
- **6a** the foundation and narration: the bridge, the state pack, the MCP server, the AI narrator and its modes (done);
- **6b** the infrastructure, per §13: two backends (Claude Code through the Agent SDK, and OpenCode), the AI menu, the Connect screen, one long-lived MCP server, prefetch, and a paragraph of prose;
- **6c** free intents, free dialogue and validated proposals (§7, §9).

Builds on master at 40776b6 (phases 1-5 done):
- phase 1's seams: `narrate/base.py` (`Narrator`), `narrate/brief.py` (`Brief.to_prompt`), `narrate/proposals.py` (`Proposal`, `Verdict`, `Validator`, `RejectAll`);
- the event-sourced world (`commit`, facts, beliefs, memories) and its knowledge rules;
- `debug/invariants.py` (`check_turn`, `check_people`), the debug overlay and bug reports.

## 1. Goal

Claude writes the game's prose, voices its people, and turns what the player types into deeds, while the engine keeps every fact.
- The procedural world stays the memory and the truth. Claude never writes state: it proposes, the engine validates, and only accepted proposals are committed as ordinary events.
- The game always runs without Claude. Procedural text is the fallback for every failure.
- A setting can hide procedural text entirely, so that only Claude's prose is read. In the long run the player plays by typing intent; the numbered choices remain, secondary.
- Claude stays realistic for the player's current state: their realm, their silver, what they own, where they are, and what they know.

### Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Roles | Prose narration; free NPC dialogue; free-text intents; content proposals. |
| AI-only setting | Yes: procedural text hidden, only Claude's prose shown (falling back on failure). |
| Free intents with no engine action | Validated proposals from a fixed vocabulary of engine events. |
| Backend | The Claude Code CLI, `claude -p` (the user's subscription; no API key). |
| Models | Split by job: Haiku 4.5 for prose; Sonnet 5 for intents and dialogue; each settable. |
| State to Claude | Push and pull: a compact state pack on every call; read-only MCP tools for deep lookups (Sonnet jobs only). |
| Size | Two sub-phases: 6a, then 6b. |

## 2. Architecture

| Module | Responsibility | Sub-phase |
|---|---|---|
| `ai/bridge.py` | Runs `claude -p` in a worker thread: model, system prompt, JSON schema, MCP config, timeout; the CLI check, the circuit breaker, the cache. | 6a |
| `ai/fake.py` | `FakeClaude`: scripted replies for tests, the same interface as the bridge. | 6a |
| `ai/pack.py` | The state pack: what the player knows of themselves and their surroundings, id-free. | 6a |
| `mcp_server/server.py`, `mcp_server/tools.py` | A stdio MCP server, read-only over the save; every tool answers as a viewer knows. | 6a |
| `ai/narrate.py` | `AINarrator`: the `Narrator` protocol over Haiku; the modes; the prose guard. | 6a |
| `ai/guard.py` | The prose guard: no unknown people, no unsupported outcomes. | 6a |
| `ai/router.py` | Typed input: the command parser first, then dialogue, then intent. | 6b |
| `ai/intent.py`, `ai/dialogue.py` | The two Sonnet jobs: prose and proposals back. | 6b |
| `ai/validate.py` | The `Validator`: each proposal checked against rules and state, turned into events. | 6b |

**The bridge's call** (each job):

```
claude -p --model <model> --output-format json --json-schema <schema> --system-prompt <job prompt>
       --no-session-persistence --tools "" [--strict-mcp-config --mcp-config <deepmurim.json>
       --allowedTools "mcp__deepmurim__*"]
```
- The prompt goes on stdin; the reply's `structured_output` (or `result`) is parsed against the job's schema.
- The MCP options are passed only to the Sonnet jobs; Haiku's prose call has no tools.
- The MCP config names the save's path and the viewer; the server opens the save read-only (SQLite `mode=ro`, WAL).

**Nothing from Claude reaches the database except through `ai/validate.py`, then `commit`.**

## 3. Settings and modes

- **AI mode:** `off` (default), `assist`, `ai_only`.
  - **off:** no thread, no pack, no cost.
  - **assist:** procedural lines show at once; Claude's prose replaces them in the log when it arrives, in a soft colour.
  - **ai_only:** procedural lines are hidden; the log shows "…" until the prose arrives; after the timeout the procedural text is shown.
- **F3** cycles the mode (F2 already docks the art frame); the mode is saved in settings.
- **Per job:** the model (`narrate`: `claude-haiku-4-5`; `intent`, `dialogue`: `claude-sonnet-5`) and the timeout (8 s for prose, 30 s for the Sonnet jobs).
- **Unavailable:** the CLI is checked once at startup (`claude --version`). If it is missing, the AI modes are greyed out in settings with the reason.

## 4. The state pack (6a)

The engine-built context of every call, plain text, id-free, under 2,500 characters, built in under 15 ms:
- **you:** name, age, realm and progress, body as known (injuries, poisons, residue, constitution), silver, what you carry and wield, sect and rank, Guild rank, karma as known, bonds (bound, sworn);
- **here:** the place, the time and weather, the people present (name, role, attitude word), buildings and what is for sale;
- **limits:** what you cannot do now, in words ("a mortal cannot fly or walk on water"; "you carry 12 silver");
- **lately:** the last 6 journal lines.

The pack never names a person the player has not heard of (the rule of `check_people`), never shows a hidden truth (an unknown poison's grade, a mask's face), and never carries an entity id.

## 5. The MCP server (6a)

`mcp_server/server.py` runs over stdio (the `mcp` Python SDK, added to `requirements.txt`). Every tool takes no viewer argument: the viewer is fixed when the server starts (the player), and every answer is filtered by what that viewer knows.

| Tool | Returns |
|---|---|
| `sheet()` | The player's sheet as text (as the sheet page shows it). |
| `known_people()` | People heard of or met: name, role, where last seen, attitude word. |
| `person(name)` | One person as known: role, traits seen, realm as known, sect, rank, what is said of them. |
| `memories_of(name)` | That person's memories of the player, as text (what they feel and why). |
| `beliefs_of(name, topic)` | What that person holds on a topic, each with an opaque handle (for 6b's `tell`). |
| `rumours(topic)` | What the player has heard on a topic. |
| `chronicle(query, limit)` | The player's own past events, as journal lines. |
| `factions()` | The player's standing with factions as known, and their ranks. |
| `place()` | Here: people, buildings, goods for sale. |

- **Names, not ids:** a tool takes a person's name as the player knows it; an unknown or ambiguous name is an error ("no one you know by that name").
- **Read-only:** the server never writes; a test opens the save after a session and finds it unchanged.
- **Speed:** each tool under 30 ms on a 200-year world.

## 6. Narration (6a)

- **The job:** Haiku gets `brief.to_prompt()`, the pack, and the last 3 prose lines shown; it returns `{"prose": "..."}`, 1-4 sentences.
- **The system prompt:** write in second person, in the wuxia register; add no facts, people, items or outcomes beyond the brief; never contradict the outcome lines.
- **The guard** (`ai/guard.py`): the prose is refused, and the procedural text stands, when it:
  - names a person the player has not heard of (`check_people`'s rule);
  - states a number of silver, a count or an item name that the brief's outcome lines do not carry.
- **Async in the log:** each turn's request runs in a worker thread; its reply replaces that turn's procedural lines (assist) or its "…" (ai_only). A new action cancels a pending reply.
- **Cache:** replies are cached by the brief's seed and salt for the session, so a re-shown turn costs nothing.

## 7. Free intents, dialogue and proposals (6b)

### 7.1 The router
Typed text goes, in order, to: the existing command parser (an exact command: the engine acts, no AI); in a free talk, to dialogue; otherwise to intent interpretation.

### 7.2 Free dialogue
- "Talk freely with X" in a conversation opens a free talk; typed text is said to X; `/back` ends it.
- Sonnet gets the pack, X as known (`person`), the last 8 lines of this talk, and the tools.
- It returns `{"reply": "...", "summary": "...", "proposals": [...]}`.
- Each exchange is committed as a `talked` event (actors: the player, X) carrying the summary (checked by the guard), so X remembers it: later briefs and dialogue draw on it.

### 7.3 Typed intents
- Sonnet gets the pack, the intent, this turn's valid choices (as words), and the tools.
- It returns `{"prose": "...", "proposals": [...]}`, where an `action` proposal maps the intent to an engine choice.

### 7.4 The proposal vocabulary

| Kind | Fields | Accepted only if |
|---|---|---|
| `action` | `verb`, `target` | it is one of this turn's valid choices or typed commands; it then runs as if chosen. |
| `pay` | `to`, `amount` | they are here; `0 < amount ≤` the player's silver. |
| `give` | `to`, `item` | the player owns the item and it may be given (not wielded, not a sect's under 5a's rules). |
| `feeling` | `who`, `feeling`, `strength` | they are here; feeling in {grateful, amused, respect, annoyed, contempt, fear}; `strength ≤ 0.5`; one per person per turn. |
| `deed` | `text`, `tone` | `text ≤ 120` characters naming only people the player knows; tone in {kind, cruel, neutral, bold}. It becomes a fact (`deed`) that spreads and is judged by its tone. |
| `tell` | `who`, `handle` | the handle is a belief that person really holds (from `beliefs_of`); the player learns it as a rumour. |
| `minor_npc` | `occupation`, `traits`, `realm` | occupation and traits from the world's lists; realm mortal or third-rate; at most 2 a visit and 6 a town; seeded from the turn. |
| `hurt` | `location`, `kind`, `severity` | the player only; `severity ≤ 2`. |
| `time` | `watches` | `1 ≤ watches ≤ 8`, through the existing time advance. |

- **Accepted** proposals become ordinary events, through `commit`, carrying `ai: true` and the proposal.
- **Rejected** proposals are dropped; their reasons go back to Claude for one retry a turn. After that the prose is replaced by a short procedural line saying the attempt fails.
- **The prose guard** (§6) applies to every Sonnet reply too, against the accepted proposals.

## 8. Failure and determinism

- Any failure (no CLI, logged out, offline, rate-limited, a timeout, bad JSON, a schema mismatch) returns nothing: the procedural text stands.
- **The circuit breaker:** three failures in a row pause the AI for 5 minutes, with one line in the log.
- AI prose is display only. Accepted proposals are ordinary events, so saves, reloads and the soak behave alike with or without AI.
- Bug reports include the session's AI exchanges (the prompt's pack, the raw reply, each proposal's verdict).

## 9. Debug rules

- `check_ai` (6b): every event with `ai: true` carries an accepted proposal of the vocabulary, within its limits.
- `check_people` and `check_turn` also apply to AI prose shown.

## 10. Speed

- With the AI off, a turn costs nothing more.
- The pack is built in under 15 ms; each MCP tool answers in under 30 ms.
- Prose is cached per brief.

## 11. Testing

- **`FakeClaude`:** scripted replies drive every test without a network: routing, validation, the guard, retries, timeouts, the circuit breaker, the cache, the modes.
- **The MCP tools:** tested directly and over stdio; none reveals what the viewer does not know; the save is unchanged after a session.
- **The pack:** id-free, under its size, only known people.
- **Fuzz** (6b): random intents and dialogue through `FakeClaude` returning random proposals, valid and invalid: no crash, no rule broken, no unvalidated state.
- **Live** (optional): one round trip through the real `claude -p`, marked `live` and deselected by default.
- **The fork guide:** section 13, how to add a proposal kind and an MCP tool.

## 12. Out of scope

- Voice, images.
- Claude creating new item kinds, systems or factions (the "generative world" option, declined).
- Multiplayer.
- Streaming partial prose (`claude -p` returns whole replies; streaming would need the API).

## 13. Amendment after 6a (2026-10-01): backends, the AI menu, the Connect screen, speed

Measured in 6a and its probes:
- a prose call through `claude -p` takes about 4 s;
- a Sonnet intent with the MCP tools takes 15-30 s: most of it is the reply's length and each tool round trip; the lookups themselves take under 20 ms; each call also starts the CLI and a fresh MCP server (1-2 s);
- OpenCode (`opencode run --pure --format json`) answers too, but sends about 100,000 tokens of its own prompt and tools a call unless given a lean agent.

### 13.1 Two backends (`ai/backends.py`)
Every job (prose; 6c's intent and dialogue) goes through one interface: `call(job, prompt) -> dict | None`, with 6a's failure rules (any failure returns None; three in a row pause the backend five minutes).
- **Claude Code** through the **Claude Agent SDK** (`claude-agent-sdk`), which runs Claude Code on the user's own login (their Pro/Max subscription).
  - One session is kept open for the game (no start-up per call); prose may arrive streamed, word by word.
  - `ANTHROPIC_API_KEY` is removed from the SDK's environment (it would switch Claude Code to API billing); the Connect screen warns if it is set.
  - DeepMurim never takes a subscription login itself, nor reuses Claude Code's stored token: the login is Claude Code's.
- **OpenCode** through `opencode run --pure --format json -m <provider/model>`, with a lean agent of no built-in tools (an `opencode.json` DeepMurim writes beside the session). OpenCode has no schema flag: the prompt asks for the job's JSON and the game parses the last text part, then checks it with 6a's `conforms`.

### 13.2 The AI menu (F1)
F1 opens a menu (it no longer cycles):
- the **mode**: off, assist, AI only (6a's);
- the **backend**: Claude Code or OpenCode;
- the **model** for prose, and the model for intents and dialogue (6c):
  - Claude Code: Haiku 4.5, Sonnet 5, Opus 5.5;
  - OpenCode: **only free models**, those `opencode models --verbose` reports at an input and output cost of 0 (read once, cached for the session).
- Settings are saved (`ai_mode`, `ai_backend`, `ai_models`).

### 13.3 The Connect screen (in the AI menu)
- whether each backend is installed and logged in (Claude Code; OpenCode), and why not;
- a warning when `ANTHROPIC_API_KEY` is set;
- the running MCP server's address;
- copy-paste setup for connecting it by hand: Claude Code (`claude mcp add --transport http deepmurim <url>`) and OpenCode (its `opencode.json` `mcp` entry, `{"type": "remote", "url": <url>}`).

### 13.4 One long-lived MCP server
While the AI is on, the game runs the DeepMurim MCP server once, over streamable HTTP on `127.0.0.1` at a free port, reading the save read-only; both backends (and the user's own sessions) connect to it. It answers as the player knows the world, re-reading the save on every request (the player may change at a succession). It stops when the game closes or the AI is turned off.

### 13.5 Prefetch
Before a 6c intent or dialogue call, the engine runs the likely lookups itself (each under 20 ms) and puts them in the prompt: the people here, their memories of the player, and their beliefs touching the words typed. The tools stay for anything else.

### 13.6 A paragraph of prose
Every job writes a paragraph (about 3-6 sentences), narration included. The guard (§6) is unchanged.

### 13.7 Testing (6b)
- `FakeClaude` stands in for either backend; the OpenCode backend's parsing is tested on recorded `--format json` output; the Agent SDK backend is tested with a fake client.
- The long-lived server: started, answers over HTTP, re-reads the save, stops; never writes.
- The menu, the Connect screen, the free-model filter (on recorded `--verbose` output), the API-key warning.
- Live tests (marked `live`, `DEEPMURIM_LIVE=1`): one Agent SDK round trip; one OpenCode round trip on a free model.
