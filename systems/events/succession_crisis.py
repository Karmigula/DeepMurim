"""A succession crisis (phase 4g spec 2.2): started by the faction clock, never on a calendar."""

import systems.succession_crisis as SC


def on_stage(world, occurrence, stage: str) -> list:
    return SC.on_stage(world, occurrence, stage)
