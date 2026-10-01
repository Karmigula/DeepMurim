# Progress

Last updated 2026-10-01. `master` is at the merge of `phase-6b`.

## Where things stand

Phases 1 to 5, 6a and 6b are done and merged. The suite has 1678 tests, plus two slow ones (`pytest -m slow`: the 500-year soak and a 200-year speed test) and three live tests (`-m live`: `claude -p`, the Agent SDK, OpenCode on a free model); all of them pass.

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation: a seeded world, NPC memory, prose and ASCII art | Done |
| 2a, 2b | Body and cultivation; duels, encounters and sources of arts | Done |
| 3a, 3b, 3c | Rumours and reputation; factions; founding a sect | Done |
| 4a to 4h | World clock, lineage, trade, world events, tournaments, secret realms, succession crises and intrigue | Done |
| 5a | Items with history | Done |
| 5b | Alchemy, medicine and poison | Done |
| 5c | The alchemy world | Done |
| 5d | Forging and formations | Done |
| 5e | The dao heart | Done |
| 5f | Karma and tribulations, and the close of phase 5 | Done |
| 6a | The Claude layer's foundation: the bridge, the state pack, the MCP server, Claude's prose | Done |
| 6b | Two backends (Claude Code via the Agent SDK, OpenCode free models), the AI menu, the Connect page, one MCP server, prefetch | Done |
| 6c | Free intents, free dialogue and validated proposals (draft on branch `wip-6c-deeds`) | Next |

See `CHANGELOG.md` for what each phase added.

## How a phase is built

1. **Design.** A brainstorm settles the open choices, then a spec is written in `docs/superpowers/specs/`.
2. **Build.** Each task is built in a scratch worktree: tests, new modules, and one patch script of anchored edits to existing files.
3. **Dry run.** Every task is replayed in order on clean `master`: the red run, the patch, the green run, then the full suite, with the soak at the end.
4. **Plan.** The plan in `docs/superpowers/plans/` is generated from the dry run's own files, so its code and expected results are verbatim.
5. **Commit.** One feature commit per task on the working branch.
6. **Review round.** A headless play-through; bugs are fixed with tests in `tests/test_*_review.py`.
7. **Minors round.** Small cleanups.
8. **Merge.** Full suite and soak, then a merge into `master` as "Merge phase-N".

## Deferred and known issues

- **6b, open:**
  - Not yet confirmed live: whether the Agent SDK's per-call `session_id` keeps history from growing.

- **Left for later** (from the phase 5 specs):
  - A pill as a fated repayment.
  - Flags forged from spirit iron.
  - Sword intent as a visible technique, and demonic arts that feed on the heart.
  - Formations on the roads, and sieges between sects.
  - Reincarnation, ascension and heavenly immortals.

## Running it

- Play: `run.bat` on Windows (it makes `.venv` and installs `requirements.txt`), or `python main.py`.
- Tests: `python -m pytest -q -p no:cacheprovider` (about 6 minutes).
- Live Claude test: `DEEPMURIM_LIVE=1 python -m pytest -q -p no:cacheprovider -m live` (needs Claude Code installed and logged in, and OpenCode for its test).
- Soak: `python -m pytest -q -p no:cacheprovider -m slow` (about 2 minutes).
- The fork guide for adding world events, crafts and systems: `docs/world-events.md`.
