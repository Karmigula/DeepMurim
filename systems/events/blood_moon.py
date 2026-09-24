"""The blood moon (phase 4d spec 4.3): demonic arts grow strong, the roads grow dangerous, righteous sects patrol.

Its modifiers live in the TOML; this module adds the patrols (plan ruling 9): righteous
fighters in a town where you are known as ruthless call you out, like avengers do.
"""

import systems.encounters as encounters
import systems.world_events as W
from systems import factions as F
from systems.beliefs import apparent_to
from systems.reputation import reputation
from world.gen.materialize import people_at

RIGHTEOUS = frozenset({"orthodox_sect", "school"})


def patrols(world, player: int) -> list[int]:
    """Righteous fighters here who call out someone known here as ruthless, while the blood moon is up."""
    here = world.targets(player, "located_in")
    if not here or W.factor(world, here[0], "patrol") <= 1.0:
        return []
    town = here[0]
    if reputation(world, town, apparent_to(world, town, player)).path != "ruthless":
        return []
    return [p.id for p in people_at(world, town, exclude=player)
            if any(world.entity(f).data.get("type") in RIGHTEOUS and d.get("status", "member") == "member"
                   for f, _, d in F.memberships(world, p.id))]


encounters.HUNTER_HOOKS.append(patrols)
