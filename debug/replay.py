"""Re-run a recorded session and check every turn comes out the same.

Turns a bug report into an exact reproduction: same seed and creation choice
(or the snapshot taken before a continued save was loaded), same commands,
compared line by line.
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from debug.session import load_session


@dataclass
class ReplayResult:
    commands: int = 0
    mismatches: list[str] = field(default_factory=list)


def _lines(turn) -> list[list[str]]:
    return [list(line) for line in turn.lines]


def replay(session_path, work_dir) -> ReplayResult:
    from app import App  # the app is what recorded the session, so it is what replays it
    from config import Config
    from systems.creation import CreationChoice

    entries = load_session(session_path)
    if not entries or entries[0].get("kind") != "session":
        return ReplayResult(0, [f"{session_path} is not a session log"])
    header = entries[0]
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    app = App(Config(), work / "saves", work / "settings.json", logs_dir=work / "logs")
    result = ReplayResult()
    try:
        if header["mode"] == "new":
            creation = CreationChoice.from_dict(header.get("creation") or {})
            app.start_new(header["player"], world_seed=header["seed"], creation=creation)
        elif header["mode"] == "newcomer":  # a newcomer walked into a dead player's world (phase 4b)
            copy = work / "saves" / "replay.world"
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(header["snapshot"], copy)
            app._newcomer_save = copy
            app.start_new(header["player"], creation=CreationChoice.from_dict(header.get("creation") or {}))
        else:
            copy = work / "saves" / "replay.world"
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(header["snapshot"], copy)
            if not app.open_save(copy):
                return ReplayResult(0, [f"could not open snapshot: {app.message}"])
        last_command = "(opening)"
        crashes_before = app.crash_count
        for entry in entries[1:]:
            kind = entry["kind"]
            if kind == "command":
                crashes_before = app.crash_count
                app.submit(entry["text"])
                result.commands += 1
                last_command = f"#{result.commands} {entry['text']!r}"
            elif kind == "turn":
                got = _lines(app.last_turn) if app.last_turn else []
                if got != entry["lines"]:
                    result.mismatches.append(f"after {last_command}: expected {entry['lines'][:3]} got {got[:3]}")
            elif kind == "crash" and app.crash_count == crashes_before:
                result.mismatches.append(f"after {last_command}: original crashed ({entry.get('error')}), replay did not")
    finally:
        app.shutdown()
    return result
