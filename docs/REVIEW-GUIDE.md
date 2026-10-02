# DeepMurim: a guide for the whole-project review

DeepMurim is a single-player wuxia text game in Python 3.14 and pygame: a seeded world that runs for centuries, where every person remembers, rumours spread, and the player's deeds are judged. Since phase 6, an AI layer can narrate it and answer typed actions and talk. The code is about 41,000 lines, with 30,000 lines of tests. It was built in phases 1-6, each from a spec and a plan in `docs/superpowers/`.

**Run:**
- the game: `python main.py`;
- the tests: `python -m pytest -q -p no:cacheprovider` (about 1,740 tests, 6 minutes);
- the soak: `-m slow` (a 500-year history and a 200-year speed test);
- live AI round trips: `DEEPMURIM_LIVE=1 ... -m live`.

## Where things are

| Layer | Files | What it does |
|---|---|---|
| The world | `world/db.py`, `world/events.py`, `world/gen/` | SQLite, event-sourced. `commit(world, events)` records each event in the chronicle and gives witnesses memories; `@effect` and `@listen` handlers change state. `World` keeps an entity cache. |
| The rules | `systems/*.py`, `systems/data/*.toml` | One module per subsystem: talk, beliefs and rumours, factions, duels, cultivation, alchemy, forging, the dao heart, karma, tribulations, the world clock. |
| The game | `engine/game.py` and its mixins | `Game.perform(Action) -> Turn`, built from about 35 mixins (one per feature); `_gate`, `_choices`, `_commit`, `_after_turn`. |
| The words | `narrate/` (grammar TOML, briefs, outcomes) | The procedural narrator. `Brief` is what a model is told of an event. |
| The screen | `app.py`, `main.py`, `render/` | The App's state machine and keys; the pygame loop at 30 fps; ASCII art and the text grid. |
| The AI layer | `ai/`, `mcp_server/` | Backends (Claude Code through the Agent SDK; OpenCode); prose narration; typed actions and talk; a proposal validator; a read-only MCP server. See section 16-18 of `docs/world-events.md`. |
| Debugging | `debug/` | `check_world` and `check_turn` (invariants run every turn), the session log, bug reports. |

## Rules that must hold (worth checking hardest)

1. **Only events change the world.** State changes go through `commit`, so a save replays the same way. `world.entity()` returns shared, cached snapshots: never edit `.data` in place; use `update_data`. `check_world` flags drift.
2. **The player sees only what they know.** Pages, briefs, the state pack and the MCP tools answer as the player knows the world, through beliefs and memories, never the world's truth. No ids reach a model.
3. **The AI never writes the world.** Everything a model returns goes through `ai/validate.py`'s `accept`, then `commit`, as events marked `ai: true`, held to their limits by `check_ai`. Prose is display only. Every failure leaves the engine's own words.
4. **Determinism.** The world is seeded (`world.seed.rng_for(seed, path)`). The same seed and the same actions give the same world. AI-made people are seeded from the turn.
5. **The MCP server never writes,** and reads the save anew on each request (`World.open_readonly`).
6. **The player's plan, never the API.** Claude Code runs on the user's own login: `ANTHROPIC_API_KEY` is set empty in its environment. OpenCode runs its own free models only.

## Performance (a priority of the project)

The world is meant to live for centuries, so costs that grow with its age matter most. Budgets the tests hold:
- the 500-year soak: a season under 0.2 s; the whole-world check under 0.3 s;
- a typed action's prompt under 20 ms (about 2 ms now);
- the state pack under 15 ms; an MCP tool under 30 ms;
- `check_ai` under 5 ms on a long history.

Known optimisations to keep honest:
- the entity cache;
- incremental `chronicle_about`;
- the grammar read once a process;
- the partial index `chronicle_ai`, and `check_ai`'s high-water mark;
- WAL with `synchronous=NORMAL`.

A finding that a cost grows with history, or that work is done every frame or every turn without need, is wanted.

## Threads

- The game's thread owns the SQLite connection.
- AI calls run in daemon threads that only call `backend.call(job, prompt)`; the prompt is built on the game's thread first.
- The Claude Code backend runs an asyncio loop in its own thread, with one client per job and a lock per client.
- The MCP server is uvicorn in a thread, with its own read-only connection per request.

## Already known, or decided on purpose

Read these before reporting them:
- `PROGRESS.md`, "Deferred and known issues" (a few open items);
- each plan's "Plan-time rulings", in `docs/superpowers/plans/`, with their cost if wrong;
- the specs' "Out of scope" sections, in `docs/superpowers/specs/`.

Notable choices:
- **OpenCode** runs `opencode.exe` directly, never the npm shim. It runs from `logs/`, never under Temp. Its free tier answers only OpenCode's own agent.
- **The waiting animation** uses `· • o O o •`, because the font has no `∘ ○ ◎`.
- **Proposals are not retried.**
- **Deeds and feelings from the AI** count once a day.

## Less worth the time

- `docs/superpowers/` (specs and plans, about 90,000 lines; they are records, not code);
- `narrate/grammar/*.toml` and `systems/data/*.toml` content (prose and tuning data);
- `tests/` style.

The tests are welcome to be reviewed for what they fail to cover.
