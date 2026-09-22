"""A per-session JSONL log of everything the player did and saw.

One line per entry, flushed immediately so a crash can't lose the tail. The
first entry is a header with what replay needs to rebuild the starting world.
"""

import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path


def stamp() -> str:
    """A sortable, unique-enough name fragment for log files."""
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 10**9:09d}"


class SessionLog:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.recent: deque[dict] = deque(maxlen=200)
        self._handle = open(path, "a", encoding="utf-8")

    def record(self, kind: str, **data) -> None:
        entry = {"kind": kind, "at": datetime.now().isoformat(timespec="seconds"), **data}
        self._handle.write(json.dumps(entry, ensure_ascii=False, default=repr) + "\n")
        self._handle.flush()
        self.recent.append(entry)

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()


def load_session(path) -> list[dict]:
    entries = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries
