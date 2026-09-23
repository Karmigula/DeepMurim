import random

import pytest

from systems.combat_core import (
    DAMAGE_BASE, INTENTS, Fighter, affordable, condition_of, effects, flee_chance, power, resolve, wound,
)
from world.body import REGULAR


def fighter(**kw):
    base = dict(name="A", realm_mult=1.0, stage=0, technique="Palm", form="palm", grade_mult=1.0, mastery=0.5,
                compat=1.0, body_fit=1.0, limb_injuries=0, leg_injuries=0, agility=10, qi=30.0)
    base.update(kw)
    return Fighter(**base)


class Fixed:
    """An rng whose uniform() always returns 1.0, to test exact damage."""

    def uniform(self, a, b):
        return 1.0


def test_condition_bands():
    assert [condition_of(h) for h in (0, 15, 35, 60, 85, 120)] == ["fresh", "bruised", "hurt", "badly hurt", "broken", "broken"]


def test_power_parts():
    assert power(fighter(), "strike", "steady", 0, False) == pytest.approx(1.0)
    assert power(fighter(realm_mult=3.0), "strike", "steady", 0, False) == pytest.approx(3.0)
    assert power(fighter(technique=None, form="bare"), "strike", "steady", 0, False) == pytest.approx(0.5)
    assert power(fighter(), "strike", "steady", 0, True) == pytest.approx(1.2)
    assert power(fighter(stance_favours="strike"), "strike", "steady", 0, False) == pytest.approx(1.1)
    assert power(fighter(limb_injuries=2), "strike", "steady", 0, False) == pytest.approx(0.85 ** 2)
    assert power(fighter(), "strike", "all-in", 70, False) == pytest.approx(1.7 * 0.7)
    assert power(fighter(beast=True, technique=None, form="claws"), "strike", "steady", 0, False) == pytest.approx(0.8)


def test_qi_output_drops_to_what_you_can_pay():
    assert affordable("all-in", 30) == "all-in"
    assert affordable("all-in", 7) == "full"
    assert affordable("full", 2) == "restrained"
    assert affordable("steady", 0) == "restrained"


def test_every_pair_has_a_rule_and_mirrors():
    swap = {"a": "b", "b": "a"}
    for x in INTENTS:
        for y in INTENTS:
            forward = sorted(effects(x, y), key=repr)
            backward = sorted(((e[0], swap[e[1]], *e[2:]) for e in effects(y, x)), key=repr)
            assert forward == backward, (x, y)


def test_resolution_table():
    r = resolve("strike", "probe", 1.0, 1.0, Fixed())
    assert [(b.target, b.damage) for b in r.blows] == [("b", DAMAGE_BASE)]
    r = resolve("strike", "guard", 1.0, 1.0, Fixed())
    assert [(b.target, b.damage) for b in r.blows] == [("a", DAMAGE_BASE * 0.5)] and r.openings == ("b",)
    r = resolve("feint", "probe", 1.0, 1.0, Fixed())
    assert r.blows[0].target == "a" and r.reveals == ("b",)
    assert resolve("guard", "guard", 1.0, 1.0, Fixed()).recover == ("a", "b")
    assert resolve("strike", "probe", 3.0, 1.0, Fixed()).blows[0].damage == pytest.approx(DAMAGE_BASE * 3 ** 0.8, abs=0.01)
    assert resolve("strike", "probe", 1.0, 1.0, Fixed(), scale=0.5).blows[0].damage == pytest.approx(DAMAGE_BASE / 2)


def test_wounds():
    rng = random.Random(1)
    assert wound("sword", 7.9, rng) is None
    assert wound("sword", 30, rng)[1:] == ("cut", 3)
    assert wound("fist", 40, rng)[1] == "fracture"
    assert wound("finger", 20, rng)[0] in REGULAR
    assert wound("finger", 60, rng, spar=True)[1:] == ("bruise", 2)
    assert wound("palm", 20, rng)[0] == "torso"
    assert wound("claws", 20, rng)[1] == "cut"


def test_flee_chance():
    a = fighter(agility=10)
    assert flee_chance(a, fighter(agility=10), 0) == pytest.approx(0.5)
    assert flee_chance(fighter(agility=18), a, 0) > 0.85
    assert flee_chance(fighter(leg_injuries=2), a, 70) < 0.1
