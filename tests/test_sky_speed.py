import time

import systems.sky as sky
import systems.world_events as W
from pathlib import Path
from world.db import World
from world.gen.materialize import ensure_town


def test_the_season_hook_is_quick_with_fifty_regions(tmp_path):
    world = World.create(tmp_path / "w.world", 7)
    for i in range(50):
        ensure_town(world, i % 10, i // 10, 0)
    n = 6
    world.set_time(n * W.SEASON)
    sky.season_events(world, n)
    start = time.process_time()
    sky.season_events(world, n + 1)
    assert time.process_time() - start < 0.02


def test_the_fork_guide_names_every_hook_and_knob():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("eligible", "start_data", "on_stage", "cultivation", "breakthrough", "practice", "encounter",
                 "beasts", "clash", "demonic", "patrol", "prices"):
        assert word in guide, word
