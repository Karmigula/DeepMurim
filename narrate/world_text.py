"""What the player is told about the living world (phase 4a spec 7)."""

from narrate.gossip_text import EXTRA_PHRASES

WORLD_PHRASES = {
    "died": "{actor} died.",
    "broke_through": "{actor} broke through to a higher realm.",
    "married": "{actor} married {target}.",
    "born": "{actor} had a child, {target}.",
    "moved": "{actor} moved to {target}.",
    "apprenticed": "{actor} took {target} as a disciple.",
    "clashed_with": "The {actor} beat the {target} in a clash.",
    "lost_hall": "The {actor} lost a hall to the {target}.",
    "faction_destroyed": "The {actor} was destroyed.",
    "faction_founded": "The {actor} was founded.",
}
EXTRA_PHRASES.update(WORLD_PHRASES)
