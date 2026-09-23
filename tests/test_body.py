import random

import pytest

from world.body import (
    EXTRAORDINARY, MERIDIANS, REGULAR, add_injury, body_of, clone, from_dict, max_qi, roll_body, settle,
    to_dict, unhealed,
)
from world.db import World


def body(seed=1, **kw):
    return roll_body(random.Random(seed), **kw)


def test_roll_is_deterministic_and_in_range():
    a, b = body(5), body(5)
    assert to_dict(a) == to_dict(b)
    assert set(a.meridians) == set(MERIDIANS)
    assert all(a.meridians[m].state == "open" and 0.4 <= a.meridians[m].flow <= 0.9 for m in REGULAR)
    assert all(a.meridians[m].state == "blocked" for m in EXTRAORDINARY)
    assert all(1 <= v <= 20 for v in a.physique.values())
    assert abs(a.nature["yin"] + a.nature["yang"] - 1) < 0.02
    assert abs(sum(a.nature[e] for e in ("metal", "wood", "water", "fire", "earth")) - 1) < 0.02
    assert 0.3 <= a.purity <= 1.0 and a.qi == max_qi(a)


def test_bias_and_overrides():
    scarred = body(3, bias={"scarred": 1, "strength": 5})
    assert sum(m.state == "scarred" for m in scarred.meridians.values()) == 1
    fixed = body(3, physique={"strength": 16, "agility": 8, "endurance": 8, "comprehension": 12}, flow_bonus=0.2)
    assert fixed.physique == {"strength": 16, "agility": 8, "endurance": 8, "comprehension": 12}
    assert all(fixed.meridians[m].flow >= 0.6 for m in REGULAR)


def test_roundtrip_through_json_dict():
    b = body(7)
    add_injury(b, "left arm", "cut", 2, now=0, cause="a test")
    assert to_dict(from_dict(to_dict(b))) == to_dict(b)
    assert to_dict(clone(b)) == to_dict(b) and clone(b) is not b


def test_injuries_heal_with_time_but_permanent_ones_never():
    b = body(2)
    b.physique["endurance"], b.constitution = 10, None
    cut = add_injury(b, "left arm", "cut", 2, now=0, cause="x")  # 20 days = 80 watches
    add_injury(b, "right leg", "fracture", 5, now=0, cause="y", permanent=True)
    assert cut.heals_at == 80
    assert {i.location for i in unhealed(settle(b, 79), 79)} == {"left arm", "right leg"}
    assert {i.location for i in settle(b, 80).injuries} == {"right leg"}


def test_meridian_injuries_damage_scar_and_sever():
    b = body(4)
    b.meridians["Lung"].flow, b.meridians["Heart"].flow = 0.7, 0.3
    add_injury(b, "Lung", "meridian", 2, now=0, cause="x")
    add_injury(b, "Heart", "meridian", 2, now=0, cause="x")
    add_injury(b, "Liver", "meridian", 5, now=0, cause="x")
    assert b.meridians["Lung"].state == "damaged" and b.meridians["Liver"].state == "severed"
    later = settle(b, 10_000)
    assert later.meridians["Lung"].state == "open"      # strong flow recovers
    assert later.meridians["Heart"].state == "scarred"  # weak flow scars
    assert later.meridians["Liver"].state == "severed"


def test_invalid_location_is_rejected():
    with pytest.raises(ValueError):
        add_injury(body(), "tail", "cut", 1, now=0, cause="x")


def test_deviation_fades_and_qi_returns():
    b = body(6)
    b.deviation, b.qi = 30, 0
    later = settle(b, 4 * 10)  # ten days
    assert later.deviation == pytest.approx(25)
    assert later.qi == pytest.approx(max_qi(b))


def test_settle_is_path_independent():
    b = body(8)
    b.deviation, b.qi = 80, 1
    add_injury(b, "torso", "internal", 3, now=0, cause="x")
    assert to_dict(settle(b, 200)) == to_dict(settle(settle(settle(b, 50), 120), 200))


def test_body_of_and_relations_from(tmp_path):
    world = World.create(tmp_path / "w.world", 1)
    pid = world.add_entity("person", "Hero", {"body": to_dict(body(1))})
    assert to_dict(body_of(world.entity(pid))) == to_dict(body(1))
    tech = world.add_entity("technique", "Palm", {})
    world.relate(pid, tech, "knows", value=0.25, data={"completeness": 0.8})
    assert world.relations_from(pid, "knows") == [(tech, 0.25, {"completeness": 0.8})]
    assert body_of(world.entity(world.add_entity("person", "Ghost"))) is None
    world.close()
