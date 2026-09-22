import subprocess
import sys

import pytest

from world.gen.npc import npc_spec
from world.gen.region import TERRAINS, region_spec
from world.gen.town import town_path, town_spec
from world.seed import seed_for


def test_seed_is_stable_and_distinct():
    assert seed_for(1, "a") == seed_for(1, "a")
    assert seed_for(1, "a") != seed_for(1, "b")
    assert seed_for(1, "a") != seed_for(2, "a")


def test_region_is_deterministic_at_extreme_coordinates():
    assert region_spec(7, -1_000_000, 1_000_000_000) == region_spec(7, -1_000_000, 1_000_000_000)


def test_regions_vary():
    terrains = {region_spec(3, x, 0).terrain for x in range(60)}
    assert len(terrains) > 2 and terrains <= set(TERRAINS)


def test_town_index_out_of_range():
    count = region_spec(5, 0, 0).town_count
    with pytest.raises(ValueError):
        town_spec(5, 0, 0, count)


def test_npc_same_in_another_process():
    here = repr(npc_spec(99, town_path(0, 0, 0), 2))
    code = (
        "from world.gen.npc import npc_spec; from world.gen.town import town_path;"
        "print(repr(npc_spec(99, town_path(0, 0, 0), 2)))"
    )
    there = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert here == there


def test_npc_has_full_portrait():
    spec = npc_spec(1, town_path(0, 0, 0), 0)
    assert dict(spec.portrait).keys() == {"hair", "face", "robe"}
    assert spec.name == f"{spec.surname} {spec.given}"
