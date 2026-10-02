"""Prose from grammar files, filled only from a Brief. Deterministic per brief.salt.

After the prose line, every `brief.outcome` line is shown dim: the grammar
colours the moment, the outcome says plainly what happened.
"""

import random
import re
import tomllib
from collections import deque
from pathlib import Path

from narrate.base import Line
from narrate.brief import Brief
from paths import bundled
from world.seed import rng_for

SYMBOL = re.compile(r"#(\w+)#")
SENTENCE_START = re.compile(r"(^|[.?!]\s+)([\"']?)([a-z])")


def sentence_case(text: str) -> str:
    """Capitalise the first letter of every sentence, including just inside a quote."""
    return SENTENCE_START.sub(lambda m: m.group(1) + m.group(2) + m.group(3).upper(), text)


class _KeepMissing(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


_LOADED: dict[str, dict] = {}  # directory -> its tables (Grammar.load)


class Grammar:
    def __init__(self, tables: dict) -> None:
        self.tables = tables

    @classmethod
    def load(cls, directory: Path | None = None) -> "Grammar":
        """The grammar of a directory, read once a process: it never changes while the game runs, and every Game
        (each MCP request's View makes one, phase 6c) would otherwise parse all of it again (12 ms)."""
        directory = Path(directory or bundled("narrate", "grammar"))
        key = str(directory.resolve())
        if key not in _LOADED:
            tables: dict = {}
            for path in sorted(directory.glob("*.toml")):
                with open(path, "rb") as handle:
                    for name, value in tomllib.load(handle).items():
                        if name == "symbols":
                            tables.setdefault("symbols", {}).update(value)
                        else:
                            tables[name] = value
            _LOADED[key] = tables
        return cls(_LOADED[key])

    def expand(self, key: str, rng: random.Random, context: dict) -> str:
        text = rng.choice(self.tables[key]["lines"])
        symbols = self.tables.get("symbols", {})
        for _ in range(10):
            expanded = SYMBOL.sub(lambda m: rng.choice(symbols[m.group(1)]) if m.group(1) in symbols else m.group(0), text)
            if expanded == text:
                break
            text = expanded
        return sentence_case(text.format_map(_KeepMissing(context)))


def context_of(brief: Brief) -> dict[str, str]:
    """Flatten a brief into grammar slots: the only data the grammar ever sees."""
    p = brief.place
    context = {
        "player": brief.player.name, "town": p.name, "kind": p.kind, "region": p.region,
        "terrain": p.terrain, "season": p.season, "watch": p.watch, "when": brief.when,
    }
    if brief.other is not None:
        o = brief.other
        context.update(
            npc=o.name, npc_full=o.name, occupation=o.role,
            trait=o.traits[0] if o.traits else "quiet", toward=o.toward_player,
        )
    context.update(brief.details)
    return context


class ProceduralNarrator:
    """Grammar prose with a short memory, so repeating an action doesn't repeat the text.

    The same salt always gives the same text (re-rendering a moment is stable).
    A new salt re-rolls away from the last RECENT texts of the same kind.
    """

    RECENT = 4
    REROLLS = 12

    def __init__(self, grammar: Grammar | None = None) -> None:
        self.grammar = grammar or Grammar.load()
        self._recent: dict[str, deque[str]] = {}
        self._last_salt: dict[str, tuple[str, str]] = {}
        self._shown: deque[str] = deque(maxlen=2 * self.RECENT)  # lines of any kind: last turn's and this one's

    def narrate(self, brief: Brief) -> list[Line]:
        outcome = [(line, "dim") for line in brief.outcome]
        key = self._key(brief)
        if key not in self.grammar.tables:
            return [(f"[{brief.kind}]", "dim")] + outcome
        colour = self.grammar.tables[key].get("colour", "default")
        salt, cached = self._last_salt.get(key, ("", ""))
        if salt == brief.salt:
            return [(cached, colour)] + outcome
        rng = rng_for(brief.seed, brief.salt)
        context = context_of(brief)
        recent = self._recent.setdefault(key, deque(maxlen=self.RECENT))
        text = self.grammar.expand(key, rng, context)
        fallback = None
        for _ in range(self.REROLLS):
            if text not in recent:
                if text not in self._shown:
                    break
                fallback = fallback or text  # new to its kind if not to the screen: the best a small grammar can do
            text = self.grammar.expand(key, rng, context)
        else:
            text = fallback or text
        recent.append(text)
        self._shown.append(text)
        self._last_salt[key] = (brief.salt, text)
        return [(text, colour)] + outcome

    def _key(self, brief: Brief) -> str:
        wanted = brief.details.get("grammar_key")
        if wanted and wanted in self.grammar.tables:
            return wanted
        if brief.kind == "scene":
            return f"scene.{brief.place.terrain}"
        if brief.kind == "breakthrough":
            return f"breakthrough.{'success' if brief.details.get('success') == 'yes' else 'failure'}"
        if brief.kind == "asked":
            topic = brief.details.get("topic", "")
            key = f"asked.{'about' if topic.startswith('about ') else topic}"
            if brief.details.get("asked_before") and f"{key}.again" in self.grammar.tables:
                return f"{key}.again"
            return key
        mood = {"hostile": "hostile", "hateful": "hostile", "warm": "warm"}.get(brief.details.get("attitude", ""))
        if brief.kind in ("met", "conversed") and mood and f"{brief.kind}.{mood}" in self.grammar.tables:
            return f"{brief.kind}.{mood}"
        if brief.kind == "conversed" and brief.details.get("annoyed_last_time") and "conversed.annoyed" in self.grammar.tables:
            return "conversed.annoyed"
        return brief.kind
