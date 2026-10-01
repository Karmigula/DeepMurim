# Progress

Last updated 2026-10-01. `master` is at the merge of `known-issues` (after phase 5f).

## Where things stand

Phases 1 to 5 are done and merged. The suite has 1571 tests plus the 500-year soak (`pytest -m slow`), and all of them pass.

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
| 6 | Not yet scoped | Next |

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

- **Left for later** (from the phase 5 specs):
  - A pill as a fated repayment.
  - Flags forged from spirit iron.
  - Sword intent as a visible technique, and demonic arts that feed on the heart.
  - Formations on the roads, and sieges between sects.
  - Reincarnation, ascension and heavenly immortals.

## Running it

- Play: `run.bat` on Windows (it makes `.venv` and installs `requirements.txt`), or `python main.py`.
- Tests: `python -m pytest -q -p no:cacheprovider` (about 6 minutes).
- Soak: `python -m pytest -q -p no:cacheprovider -m slow` (about 2 minutes).
- The fork guide for adding world events, crafts and systems: `docs/world-events.md`.
