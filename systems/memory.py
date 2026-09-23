"""How memories fade (phase 3a spec §3.1). Nothing is deleted; strength is worked out when read."""

from world.events import INDELIBLE_FEELINGS

HALF_LIFE = 360  # watches: one season
INDELIBLE = INDELIBLE_FEELINGS


def effective_intensity(memory, now: int) -> float:
    """How strongly a memory is felt at `now`. Indelible memories never fade."""
    if memory.indelible:
        return memory.intensity
    age = max(0, now - memory.event.time)
    return memory.intensity * 0.5 ** (age / HALF_LIFE)
