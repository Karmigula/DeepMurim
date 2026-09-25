"""An opening of a secret realm (phase 4f spec 2.4): heralded, then the gate stands open for eight days.

`realm_opening` comes round on each realm's own period (`every = 1`, with `places` naming the gates
due this season); `realm_awakening` is a newborn realm's first opening, started by its treasure light.
"""

import systems.secret_realms as SR


def places(world, n: int, rng) -> list[int]:
    return sorted({world.entity(r).data["gate"] for r in SR.due(world, n)})


def start_data(world, gate: int, n: int, rng) -> dict | None:
    realms = [r for r in SR.due(world, n) if world.entity(r).data["gate"] == gate]
    return SR.opening_data(realms[0]) if realms else None


def on_stage(world, occurrence, stage: str) -> list:
    return SR.on_stage(world, occurrence, stage)


def on_observe(world, occurrence) -> list:
    return SR.on_observe(world, occurrence)
