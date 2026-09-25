"""What the player is told of succession crises (phase 4g spec 5): the tales, the kinds of claim, how seats were won."""

from narrate.outcomes import cap  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

KIND_WORDS = {"chief": "the chief disciple", "blood": "the late master's blood", "elder": "an elder",
              "grand_elder": "the Grand Elder, down from seclusion", "regent": "a regent", "player": "a claimant"}
HOW_WORDS = {"backing": "with the elders behind them", "trial": "by trial of arms", "unopposed": "unopposed",
             "chosen": "chosen by the elders", "far": "after a bitter contest", "strife": "by force of arms",
             "stepped_down": "named by the old master", "regency": "as regent"}


def names(world, people, viewer: int) -> str:
    said = [who(world, p, viewer) for p in people]
    return said[0] if len(said) == 1 else ", ".join(said[:-1]) + " and " + said[-1] if said else "no one"


def _faction(world, variant) -> str:
    faction = world.entity(variant.get("target")) if variant.get("target") is not None else None
    return f"the {faction.name}" if faction is not None else "a sect"


def _crisis_story(world, variant, viewer) -> str:
    sect = _faction(world, variant)
    if variant.get("stage") == "settled":
        how = HOW_WORDS.get(variant.get("how"), "")
        return cap(f"{who(world, variant.get('actor'), viewer)} now leads {sect}{', ' + how if how else ''}.")
    return cap(f"{sect} is without a master: {names(world, variant.get('people') or [variant.get('actor')], viewer)} "
               f"each claim the seat.")


def _named_chief_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} was named chief disciple of {_faction(world, variant)}.")


def _transmitted_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)}, dying, poured their inner strength into "
               f"{who(world, variant.get('target'), viewer)}.")



SPECIAL_PHRASES.update({"crisis": _crisis_story, "named_chief": _named_chief_story,
                        "transmitted": _transmitted_story})


def claim_words(kind: str) -> str:
    return KIND_WORDS.get(kind, "a claimant")
