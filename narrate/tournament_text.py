"""What the player is told about tournaments (phase 4e)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

KIND_NAMES = {"grand_assembly": "the Grand Martial Assembly", "dragon_phoenix": "the Dragon-Phoenix Meet",
              "sect_contest": "the sect contest", "lei_tai": "the lei tai"}
PLACES = {2: "second", 3: "among the last four"}


def _bested_story(world, variant, viewer) -> str:
    winner, loser = who(world, variant.get("actor"), viewer), who(world, variant.get("target"), viewer)
    event = KIND_NAMES.get(variant.get("kind"), "a tournament")
    return cap(f"{winner} bested {loser} at {event} in {variant.get('place') or 'a crowded city'}.")


def _won_story(world, variant, viewer) -> str:
    winner = who(world, variant.get("actor"), viewer)
    event = KIND_NAMES.get(variant.get("kind"), "a tournament")
    return cap(f"{winner} won {event} in {variant.get('place') or 'a crowded city'}.")


def _placed_story(world, variant, viewer) -> str:
    person = who(world, variant.get("actor"), viewer)
    event = KIND_NAMES.get(variant.get("kind"), "a tournament")
    return cap(f"{person} finished {PLACES.get(variant.get('place'), 'well')} at {event}.")


SPECIAL_PHRASES.update({"bested": _bested_story, "won_tournament": _won_story, "placed": _placed_story})



def _lei_tai_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} held the lei tai in {variant.get('place') or 'a market town'} "
               "until dusk and took the purse.")


SPECIAL_PHRASES["held_lei_tai"] = _lei_tai_story
