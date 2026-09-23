# Debugging DeepMurim

## While playing

| Key | What it does |
|---|---|
| **F9** | Saves a bug report folder to `logs/report-<time>/`. Type a note on the command line first (for example "npc repeats itself") and it goes into the report. |
| **F12** | Opens the debug overlay: place and time, the exact fact sheet the narrator got this turn (what Haiku would see), and recent rule violations. |

- **A crash no longer closes the game.** You get a red line in the log, and a report is written to `logs/crash-<time>.txt`.
- **A red `debug:` line** means one of the rule checks below just caught something. The game keeps going.

## What gets recorded

- **`logs/session-<time>.jsonl`:** every command you entered and every turn the game showed you, one JSON line each. There is one file per session: each new game or Continue starts a new one.
- **`logs/session-<time>.start.world`:** for a continued game, a copy of the save as it was when you continued, so the session can be replayed.
- **`logs/report-<time>/`** holds:
  - `summary.txt`: your note, the game state, and the rule violations;
  - `session.jsonl`;
  - `save.world`: a copy of the save at the moment you pressed F9.

## Reproducing a bug

```
.venv\Scripts\python.exe main.py --replay logs\report-<time>\session.jsonl
```

This rebuilds the starting world and re-enters every command. It either prints `identical`, or lists the first turns that came out differently. To hand a bug to Claude, give it the report folder.

## Rules checked after every turn (`debug/invariants.py`)

- **Where people are:** every person is in exactly one place, and that place exists. The player exists.
- **Time:** the chronicle never goes back in time.
- **Prose:** has no leftover template slots (`{npc}`, `#greeting#`), no "no grammar" fallbacks, and doesn't repeat a line shown in the last 4 lines of prose.
- **Choices:** at most 9 are shown, and each one has a handler.
- **Narrator fact sheets:** at most 6 facts, and at most 1,200 characters. They never contain an undiscovered constitution or a completeness value, and prose never starts a sentence in lowercase.
- **Bodies:** qi is between 0 and max; energy is within the realm's bounds, with the bottleneck set at the cap; deviation is between 0 and 100; every meridian state and injury is valid; the realm label matches the body; silver is at least 0.
- **Arts:** every known art is a technique, and mastery never exceeds completeness. No breakthrough skips a realm. Belief never falls below truth (`known_completeness >= completeness`).
- **Items:** every manual has exactly one owner and a real technique, and never claims less than it holds.
- **Fights:** a live duel has real participants, harm between 0 and 100, and a valid stage. An encounter has a real person. Fragment lists are well-formed and hold at most 12.
- **The dead:** are buried (no location, one grave). They are never a conversation partner, a challenger or a road encounter.
- **Knowledge (phase 3a):** every belief points at a real fact, with confidence 0-1 and a first-hand witness at 0 retellings. A retelling never credits a deed to a different person (so a mask can't leak the face behind it). Every lie names its liar and the telling that started it. Inherited memories come only from the dead. Every persona is the player's.
- **Factions (phase 3b):** stances are symmetric and in -1..1; the player openly belongs to at most one martial faction, holds rank 0-3 and never negative merit; every open duty has a living holder whose duty it is, and a target that exists. Faction names on screen are ones the player knows (a membership, a hall here, a rumour, or staff they have met).
- **Your sect (phase 3c):** a live sect has one leader (its founder) and a seat the founder owns; at most 12 disciples and 3 elders, each at the seat or away on duty; its seasons never run ahead of the clock and its treasury never goes negative; a dissolved sect has no members; a town has at most one owner.
- **Names on screen:** no person or persona is named in a turn unless the player has met them, heard of them, or they are standing here.

## The standing bug-catcher

`tests/test_fuzz.py` plays 250 random turns in each of 4 worlds, mixing number presses, typed commands, junk, hotkeys and save/continue. It fails on any crash or rule violation. When new systems arrive (phase 2 and later), they are exercised here automatically. Add new rules to `debug/invariants.py` as the game grows.
