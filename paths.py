"""Where things are, whether running from source or frozen into one exe.

Bundled files ship inside the game (fonts, art, grammar). Beside files belong
to the player (saves, settings) and live next to the game so they survive
upgrades.
"""

import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
_SOURCE = Path(__file__).resolve().parent


def bundled(*parts) -> Path:
    """A read-only file shipped with the game."""
    root = Path(getattr(sys, "_MEIPASS", _SOURCE)) if FROZEN else _SOURCE
    return root.joinpath(*parts)


def beside(*parts) -> Path:
    """A file the player owns, next to the game rather than inside it."""
    root = Path(sys.executable).resolve().parent if FROZEN else _SOURCE
    return root.joinpath(*parts)
