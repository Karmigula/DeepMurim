"""What the player is told about the living world (phase 4a spec 7)."""

from narrate.gossip_text import EXTRA_PHRASES

WORLD_PHRASES = {
    "died": "{actor} died.",
    "broke_through": "{actor} broke through to a higher realm.",
}
EXTRA_PHRASES.update(WORLD_PHRASES)
