"""The seam between the engine and whoever writes the prose.

A narrator gets a finished Brief and returns lines. It never reads the world:
everything it may say is already in the brief.
"""

from typing import Protocol, runtime_checkable

Line = tuple[str, str]  # (text, palette key)


@runtime_checkable
class Narrator(Protocol):
    def narrate(self, brief) -> list[Line]: ...
