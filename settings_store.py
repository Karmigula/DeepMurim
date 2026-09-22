"""A flat JSON file of preferences. Every failure is silent and gives defaults."""

import json
from pathlib import Path

from paths import beside

DEFAULT_PATH = beside("settings.json")


def load_values(path: Path | None = None) -> dict:
    target = DEFAULT_PATH if path is None else path
    try:
        with open(target, encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, ValueError):
        return {}
    return stored if isinstance(stored, dict) else {}


def save_values(values: dict, path: Path | None = None) -> bool:
    target = DEFAULT_PATH if path is None else path
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(values, handle, indent=2)
    except OSError:
        return False
    return True
