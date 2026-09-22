"""Prose from grammar files, filled only from a Brief. Deterministic per brief.salt."""

import random
import re
import tomllib
from pathlib import Path

from narrate.base import Line
from narrate.brief import Brief
from paths import bundled
from world.seed import rng_for

SYMBOL = re.compile(r"#(\w+)#")


class _KeepMissing(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class Grammar:
    def __init__(self, tables: dict) -> None:
        self.tables = tables

    @classmethod
    def load(cls, directory: Path | None = None) -> "Grammar":
        directory = directory or bundled("narrate", "grammar")
        tables: dict = {}
        for path in sorted(directory.glob("*.toml")):
            with open(path, "rb") as handle:
                for key, value in tomllib.load(handle).items():
                    if key == "symbols":
                        tables.setdefault("symbols", {}).update(value)
                    else:
                        tables[key] = value
        return cls(tables)

    def expand(self, key: str, rng: random.Random, context: dict) -> str:
        text = rng.choice(self.tables[key]["lines"])
        symbols = self.tables.get("symbols", {})
        for _ in range(10):
            expanded = SYMBOL.sub(lambda m: rng.choice(symbols[m.group(1)]) if m.group(1) in symbols else m.group(0), text)
            if expanded == text:
                break
            text = expanded
        return text.format_map(_KeepMissing(context))


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
    def __init__(self, grammar: Grammar | None = None) -> None:
        self.grammar = grammar or Grammar.load()

    def narrate(self, brief: Brief) -> list[Line]:
        if brief.kind == "scene":
            key = f"scene.{brief.place.terrain}"
        elif brief.kind == "asked":
            key = f"asked.{brief.details.get('topic', '')}"
        else:
            key = brief.kind
        if key not in self.grammar.tables:
            return [(f"[{brief.kind}]", "dim")]
        rng = rng_for(brief.seed, brief.salt)
        colour = self.grammar.tables[key].get("colour", "default")
        return [(self.grammar.expand(key, rng, context_of(brief)), colour)]
