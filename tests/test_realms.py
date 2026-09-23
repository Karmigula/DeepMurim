import random
from types import SimpleNamespace as NS

import pytest

from systems.realms import (
    MAX_REALM, REALMS, add_energy, breakthrough_chance, energy_words, realm_index, realm_title, requirement,
    stage_of,
)
from world.body import EXTRAORDINARY, roll_body


def fresh(realm=0, energy=0.0):
    b = roll_body(random.Random(1))
    b.realm, b.energy_years = realm, energy
    return b


def art(category="martial", mastery=0.0, source="origin"):
    return NS(category=category, mastery=mastery, source=source)


def test_ladder():
    assert [r.threshold for r in REALMS] == [0, 1, 5, 20, 40, 60, 120, 240]
    assert MAX_REALM == 7 and realm_index("second-rate") == 2 and realm_index("nonsense") == 0


def test_stages_follow_energy_within_realm():
    assert stage_of(fresh(1, 1.0)) == "early"
    assert stage_of(fresh(1, 2.0)) == "middle"
    assert stage_of(fresh(1, 3.5)) == "late"
    assert stage_of(fresh(1, 4.99)) == "peak"
    assert realm_title(fresh(0, 0.2)) == "Mortal"
    assert realm_title(fresh(1, 2.5)) == "Third-rate (middle stage)"


def test_energy_stops_at_the_bottleneck():
    b = fresh(0, 0.9)
    assert add_energy(b, 0.05) == pytest.approx(0.05) and not b.bottleneck
    assert add_energy(b, 5.0) == pytest.approx(0.05)
    assert b.energy_years == 1.0 and b.bottleneck


def test_requirements_by_target_realm():
    b = fresh(0, 1.0)
    assert requirement(b, [])[0] is False
    b.flags.append("sensed_qi")
    assert requirement(b, [])[0] is True
    b = fresh(1, 5.0)
    assert requirement(b, [])[0] is False
    b.meridians["Conception"].state = "open"
    assert requirement(b, [])[0] is True
    b = fresh(2, 20.0)
    b.meridians["Governing"].state = b.meridians["Conception"].state = "open"
    assert requirement(b, [art(mastery=0.5)])[0] is False
    assert requirement(b, [art(mastery=0.7)])[0] is True
    assert requirement(b, [art("heart_method", 0.9)])[0] is False  # heart methods don't count
    b = fresh(3, 40.0)
    assert requirement(b, [art(mastery=1.0)])[0] is False
    b.flags.append("life_and_death_insight")
    assert requirement(b, [art(mastery=1.0)])[0] is True
    b = fresh(4, 60.0)
    b.insight = 250
    for m in EXTRAORDINARY:
        b.meridians[m].state = "open"
    assert requirement(b, [])[0] is True
    b = fresh(5, 120.0)
    assert requirement(b, [art(mastery=1.0, source="created")])[0] is True
    met, text = requirement(fresh(7, 240.0), [])
    assert not met and "not yet open" in text


def test_breakthrough_chance():
    b = fresh(0, 1.0)
    b.physique["comprehension"], b.purity, b.insight = 10, 0.5, 0
    assert breakthrough_chance(b, True) == pytest.approx(0.40)
    assert breakthrough_chance(b, False) == pytest.approx(0.04)
    b.physique["comprehension"] = 30
    assert breakthrough_chance(b, True) == 0.95


def test_energy_words():
    assert energy_words(0.0) == "barely a trace of internal energy"
    assert energy_words(0.5) == "less than a year of internal energy"
    assert energy_words(1.2) == "about one year of internal energy"
    assert energy_words(3.9) == "about three years of internal energy"
    assert energy_words(42) == "about 42 years of internal energy"
