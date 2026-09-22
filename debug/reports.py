"""Crash reports (automatic) and bug reports (F9). Both are plain files a human or Claude can read."""

import json
import shutil
import traceback
from pathlib import Path

from debug.session import stamp


def write_crash_report(logs_dir: Path, exc: BaseException, context: dict, recent: list[dict]) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"crash-{stamp()}.txt"
    parts = [
        "DeepMurim crash report",
        "",
        "".join(traceback.format_exception(exc)),
        "context:",
        json.dumps(context, indent=2, ensure_ascii=False, default=repr),
        "",
        "recent session entries (oldest first):",
        *(json.dumps(entry, ensure_ascii=False, default=repr) for entry in recent[-40:]),
    ]
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


def write_bug_report(logs_dir: Path, world, session, note: str, context: dict, violations: list[str]) -> Path:
    """A folder holding everything needed to see and reproduce a problem."""
    folder = logs_dir / f"report-{stamp()}"
    folder.mkdir(parents=True, exist_ok=True)
    world.backup_to(folder / "save.world")
    if session is not None and Path(session.path).is_file():
        shutil.copyfile(session.path, folder / "session.jsonl")
    summary = [
        "DeepMurim bug report",
        "",
        f"note: {note or '(none typed)'}",
        "",
        "context:",
        json.dumps(context, indent=2, ensure_ascii=False, default=repr),
        "",
        f"invariant violations this session ({len(violations)}):",
        *(f"  - {v}" for v in violations),
        "",
        "to reproduce: .venv\\Scripts\\python.exe main.py --replay session.jsonl  (run from the game folder)",
        "save.world is a copy of the save at the moment of the report.",
    ]
    (folder / "summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return folder
