"""What the player is told about the sky and the Murim's great events (phase 4d)."""

from narrate.gossip_text import SPECIAL_PHRASES
from narrate.outcomes import cap

NAMES = {"qi_tide": "a qi tide"}
STAGE_WORDS = {"foretold": "is foretold over", "announced": "gathers over", "active": "hangs over",
               "aftermath": "has passed over"}


def phenomenon_name(kind: str) -> str:
    return NAMES.get(kind, "a " + kind.replace("_", " "))


def _phenomenon_story(world, variant, viewer) -> str:
    where = variant.get("place") or "the land"
    text = f"{cap(phenomenon_name(variant.get('kind', 'omen')))} {STAGE_WORDS.get(variant.get('stage'), 'was seen over')} {where}."
    if variant.get("reading"):
        text += f" People say it means {variant['reading']}."
    return text


SPECIAL_PHRASES["phenomenon"] = _phenomenon_story
