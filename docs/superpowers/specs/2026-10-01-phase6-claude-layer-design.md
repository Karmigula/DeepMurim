# DeepMurim Phase 6: The Claude Layer

**Status:** design approved in brainstorming (2026-10-01); amended after 6a (§13) and after 6b (§14). Phase 6 is three sub-phases, each with its own plan and merge:
- **6a** the foundation and narration: the bridge, the state pack, the MCP server, the AI narrator and its modes (done);
- **6b** the infrastructure, per §13: two backends (Claude Code through the Agent SDK, and OpenCode), the AI menu, the Connect screen, one long-lived MCP server, prefetch, and a paragraph of prose (done);
- **6c** free intents, free dialogue and validated proposals (§7, §9, as amended by §14).

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
- OpenCode (`opencode run --format json`) answers too, with about 100,000 tokens of its own prompt a call; its free models answer only to its own agent.

### 13.1 Two backends (`ai/backends.py`)
Every job (prose; 6c's intent and dialogue) goes through one interface: `call(job, prompt) -> dict | None`, with 6a's failure rules (any failure returns None; three in a row pause the backend five minutes).
- **Claude Code** through the **Claude Agent SDK** (`claude-agent-sdk`), which runs Claude Code on the user's own login (their Pro/Max subscription).
  - One session is kept open for the game (no start-up per call); prose may arrive streamed, word by word.
  - `ANTHROPIC_API_KEY` is removed from the SDK's environment (it would switch Claude Code to API billing); the Connect screen warns if it is set.
  - DeepMurim never takes a subscription login itself, nor reuses Claude Code's stored token: the login is Claude Code's.
- **OpenCode** through `opencode run --attach <a warm server> --format json -m <provider/model>`.
  - While the AI is on, DeepMurim keeps a hidden `opencode serve` running on localhost and attaches every call to it: measured, a free model's paragraph takes about 8 s once warm (15 s cold, 18 s with no server).
  - OpenCode's own agent is used: its free tier refuses any other agent ("OpenCode's free tier can only be used from within OpenCode"), so the lean agent first proposed is out, and each call carries OpenCode's own prompt.
  - `opencode.exe` is run directly, never the npm `.cmd` shim: `cmd.exe` reads `<` and `>` in the prompt as redirections, and a timeout could not end the process tree.
  - OpenCode has no schema flag: the prompt asks for the job's JSON and the game parses the last text part, then checks it with 6a's `conforms`.

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

## 14. Amendment after 6b (2026-10-01): 6c, typed actions and free talk

Where this section differs from §7-§11, this section stands. Calls go through 6b's backends (§13.1), never `claude -p`.

Measured before writing it: a typed action with the pack and the prefetch, about 2,200 characters, asking for a paragraph and proposals.

| Backend | Time a call | Answered |
|---|---|---|
| Claude Code, Sonnet 5 | 9.3 s with the connect, then 5.4 s and 6.9 s | 3 of 3 |
| OpenCode, a free model | 61 s (timed out, with the server's cold start), 55 s, 13 s | 2 of 3 |

Unasked, the model proposed too much: a `minor_npc` in every Claude Code reply, and both `pay` and `give` for one cup of tea.

### 14.1 The router
Typed text goes, in order:
1. An exact command: the engine acts, and no AI is asked (as today).
2. In a conversation: a line said to that person (the dialogue job, §14.4).
3. Otherwise: a typed action (the intent job, §14.3).
4. With the AI off, or its backend unavailable: today's "unknown command" line, and nothing is asked.

### 14.2 Waiting
A typed action changes the world, so the turn waits for its answer.
- **Input pauses.** Under the typed line, an animated line shows "…" and the backend's name: a qi swirl, `· ∘ ○ ◎ ○ ∘`, at about 8 frames a second. It is drawn from the clock in the 30 fps redraw that already runs, so it costs no more work.
- **Esc cancels.** Nothing happens, the typed line is struck through, and input returns. A reply that comes after is dropped.
- **Timeouts:** 30 s on Claude Code; 90 s on OpenCode (its free tier measured 13-60 s).
- **A timeout or any failure:** the world is unchanged, and the log says "You hesitate; nothing comes of it."

### 14.3 Typed actions (the intent job)
- **The model:** the menu's "Typed actions and talk" model (Sonnet 5 by default), on either backend.
- **The prompt:**
  1. the state pack (6a);
  2. the prefetch (§13.5);
  3. the last 3 paragraphs shown;
  4. this turn's valid choices, as words;
  5. the typed line.
- **The tools:** the MCP tools are attached, and the prompt says to use one only for what the prompt lacks.
- **The reply:** `{"prose": "...", "proposals": [...]}`.
  - The prose is one paragraph (§13.6).
  - At most 4 proposals.
  - The prompt says: "propose only what the typed action itself causes; most actions cause one change or none."

### 14.4 Free talk (the dialogue job)
In a conversation, any typed line that is not a command is said to that person; there is no free-talk mode, and §7.2's "Talk freely" choice and `/back` are dropped.
- **Ending it:** the numbered choices stay, and farewell ends the conversation as before.
- **The prompt:** as §14.3, plus that person as known (`person`) and the last 8 lines of this conversation.
- **The reply:** `{"reply": "...", "summary": "...", "proposals": [...]}`.
  - The reply is the person's answer, in a paragraph.
  - The summary is one line, checked by the guard.
- **Memory:** each exchange is committed as a `talked` event (actors: the player and that person) carrying the summary, so they remember it. Later briefs, talk and gossip draw on it.
- **Proposals:** every kind except `action` and `minor_npc`.

### 14.5 Proposals: no retry
The vocabulary and its limits are §7.4's, with these changes:
- **No retry.** Accepted proposals are committed. Rejected ones are dropped, and their reasons go to the F12 overlay and the bug report.
- **Tighter limits:**
  - `minor_npc`: at most 1 a typed line, 2 a visit and 6 a town;
  - `feeling`: at most 1 per person a line.
- **An `action` proposal** runs the engine's choice as if chosen. Its own engine lines follow §14.6, and no second narration call is made for them.
- **A `deed`** is judged by its tone through the existing rules: reputation, the dao heart (5e), karma (5f).
- The guard (§6) checks every paragraph and summary against the accepted proposals only.

### 14.6 What is shown
- **The AI's paragraph** is the turn's text.
- **Each accepted change** is also shown as a short engine line, such as "Tang Jin: -2 silver to you" or "Jin Yunhyun is grateful":
  - in **assist**, they are shown;
  - in **AI only**, they are hidden, and only the paragraph is read.
- **A refused paragraph:** if the guard refuses it (for instance, it tells of a payment that was rejected), the engine lines of what really happened are shown instead, followed by "You try, but it does not go as you meant."

### 14.7 Debug rules
- **`check_ai`:** every `ai: true` event carries an accepted proposal of the vocabulary, within its limits.
- **The F12 overlay** shows the last typed line, its job, each proposal's verdict, and the time taken.

### 14.8 Speed
- With the AI off, a typed line costs nothing more.
- The prompt (the pack and the prefetch) is built in under 20 ms; the validator runs in under 5 ms.
- The animation is drawn from the clock and adds no work.

### 14.9 Testing (6c)
- **`FakeClaude` drives all of these:**
  - the router;
  - the wait, Esc and the timeout;
  - each proposal kind, accepted and rejected at its limits;
  - the guard against the accepted proposals;
  - assist and AI only;
  - a `talked` event remembered in a later brief;
  - `check_ai`.
- **Fuzz:** random typed lines with random proposals, valid and invalid. There is no crash, no broken invariant, and no state that was not validated.
- **Live** (marked `live`, `DEEPMURIM_LIVE=1`): one typed action and one talk line, on Claude Code and on OpenCode.
- **The fork guide:** how to add a proposal kind.
- **The draft** on the branch `wip-6c-deeds` (`ai/validate.py`, `ai/deeds.py`, `narrate/ai_text.py`) is the starting point of the first task.
