"""Every event the player is told of has a grammar entry, or the screen shows a bare "[kind]" (known issue)."""
import tomllib
from pathlib import Path

import engine.game  # noqa: F401  (every system and its narration registers on import)
from narrate.outcomes import OUTCOME_BUILDERS


def test_every_outcome_has_its_grammar():
    tables: set = set()
    for path in Path("narrate/grammar").glob("*.toml"):
        with path.open("rb") as f:
            tables |= {k for k in tomllib.load(f) if k != "symbols"}
    covered = tables | {key.split(".")[0] for key in tables}  # some speak by sub-key: encounter.beast, duel_ended.won
    assert sorted(kind for kind in OUTCOME_BUILDERS if kind not in covered) == []  # else the screen shows "[kind]"
