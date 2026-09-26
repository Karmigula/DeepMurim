"""Stilling phase 4h's intrigue in tests of what came before it (4g's crises): no murders, puppets, spies,
forgeries, frames, founder's tests, weddings, arbiters or outsiders unless a test asks for one."""

import importlib

KNOBS = (("systems.murder", ("MURDER_CHANCE",)), ("systems.puppets", ("PUPPET_CHANCE", "SPY_CHANCE")),
         ("systems.frames", ("FORGE_CHANCE", "FRAME_CHANCE")),
         ("systems.legitimacy", ("NPC_TRY", "MARRY_CHANCE", "ARBITER_CHANCE", "OUTSIDER_CHANCE")))


def still(monkeypatch) -> None:
    for name, knobs in KNOBS:
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError:
            continue  # a later task's module, not written yet
        for knob in knobs:
            if hasattr(module, knob):
                monkeypatch.setattr(module, knob, 0.0)
