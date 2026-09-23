import random

import pytest

from systems.techniques import (
    FORMS, alignment, compat_words, compatibility, create_technique, generate, heart_method, known_arts,
    martial_arts, mastery_stage, practise_gain, set_mastery, teach, usable,
)
from world.body import REGULAR, roll_body
from world.db import World


def neutral_body():
    b = roll_body(random.Random(1))
    b.physique = {"strength": 10, "agility": 10, "endurance": 10, "comprehension": 10}
    return b


def art_data(**kw):
    data = {"category": "martial", "form": "sword", "route": ["Lung", "Heart"], "element": "neutral", "grade": 1}
    data.update(kw)
    return data


def test_generate_is_deterministic_and_well_formed():
    a = generate(random.Random(3), "martial", form="palm", grade=2)
    assert a == generate(random.Random(3), "martial", form="palm", grade=2)
    name, data = a
    assert "Palm" in name and data["form"] == "palm" and data["grade"] == 2
    assert 2 <= len(data["route"]) <= 6 and set(data["route"]) <= set(REGULAR)
    assert data["stance"]["favours"] in ("strike", "feint", "guard", "probe")
    _, heart = generate(random.Random(3), "heart_method")
    assert heart["form"] == "inner" and heart["category"] == "heart_method"
    assert {generate(random.Random(s), "martial")[1]["form"] for s in range(40)} <= set(FORMS)


def test_compatibility_route_nature_and_body():
    b = neutral_body()
    assert compatibility(b, art_data()) == pytest.approx(1.0)
    b.meridians["Heart"].state = "scarred"
    assert compatibility(b, art_data()) == pytest.approx(0.8)
    b.meridians["Heart"].state = "damaged"
    assert compatibility(b, art_data()) == pytest.approx(0.5)
    b.meridians["Heart"].state = "severed"
    assert compatibility(b, art_data()) == 0 and not usable(b, art_data())
    b = neutral_body()
    b.physique["agility"] = 20
    assert compatibility(b, art_data()) == pytest.approx(1.2)
    b = neutral_body()
    b.nature.update(yin=0.9, yang=0.1)
    assert compatibility(b, art_data(element="yin")) > 1.0 > compatibility(b, art_data(element="yang"))


def test_alignment_bounds():
    nature = {"yin": 0.5, "yang": 0.5, "metal": 0.6, "wood": 0.1, "water": 0.1, "fire": 0.1, "earth": 0.1}
    assert alignment("neutral", nature) == 0 and alignment("yin", nature) == 0
    assert alignment("metal", nature) == 1.0 and alignment("wood", nature) == pytest.approx(-0.5)


def test_words_and_stages():
    assert [compat_words(c) for c in (0.3, 0.6, 0.9, 1.1)] == ["fights your body", "sits awkwardly", "suits you", "made for you"]
    assert [mastery_stage(m) for m in (0.0, 0.4, 0.8, 1.0)] == ["Initial", "Minor Success", "Major Success", "Great Completion"]
    assert practise_gain(7, 10, 1.0, 1) == pytest.approx(0.028)
    assert practise_gain(7, 10, 1.0, 2) == pytest.approx(0.028 / 1.5)


def test_knowing_arts(tmp_path):
    world = World.create(tmp_path / "w.world", 1)
    pid = world.add_entity("person", "Hero")
    heart = create_technique(world, "Still Water Heart Method", art_data(category="heart_method", form="inner"))
    palm = create_technique(world, "Pale Crane Palm", art_data(form="palm"))
    teach(world, pid, heart, source="origin")
    teach(world, pid, palm, completeness=0.6, known_completeness=1.0, source="manual")
    assert [a.name for a in known_arts(world, pid)] == ["Still Water Heart Method", "Pale Crane Palm"]
    assert heart_method(world, pid).name == "Still Water Heart Method"
    assert [a.name for a in martial_arts(world, pid)] == ["Pale Crane Palm"]
    set_mastery(world, pid, palm, 0.5)
    known = martial_arts(world, pid)[0]
    assert known.mastery == 0.5 and known.completeness == 0.6 and known.known_completeness == 1.0
    world.close()
