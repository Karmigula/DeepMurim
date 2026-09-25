"""What the player is told about secret realms (phase 4f)."""

from narrate.outcomes import cap  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who


def _delved_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} went into {variant.get('realm_name') or 'a secret realm'} "
               f"and came out alive.")


def _took_story(world, variant, viewer) -> str:
    what = {"manual": "a martial manual", "pill": "a precious pill", "herb": "a spirit herb",
            "star_iron": "star iron"}.get(variant.get("prize"), "a treasure")
    return cap(f"{who(world, variant.get('actor'), viewer)} came out of {variant.get('realm_name') or 'a secret realm'} "
               f"with {what}.")


def _inherited_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} won the inheritance of {variant.get('master') or 'an ancient master'} "
               f"in {variant.get('realm_name') or 'a secret realm'}.")


def _sealed_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} did not come out of {variant.get('realm_name') or 'a secret realm'} "
               f"before the gate closed.")


SPECIAL_PHRASES.update({"delved": _delved_story, "took": _took_story, "inherited": _inherited_story,
                        "sealed": _sealed_story})
