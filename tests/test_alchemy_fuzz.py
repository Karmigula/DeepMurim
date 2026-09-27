"""A wandering alchemist, played at random (phase 5b): gathers, buys, tastes, experiments, refines, swallows and
fights; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing


@pytest.mark.parametrize("seed", [6, 33])
def test_a_wandering_alchemist(tmp_path, seed):
    import systems.herbs as H
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Alchemist{seed}", world_seed=seed)
    world = app.game.world
    me = world.get_meta("player_id")
    world.update_data(me, silver=3000)
    for name in ("ginseng", "tiger bone vine", "frost lotus leaf", "frost lotus leaf", "black lotus", "corpse flower",
                 "willow bark", "willow bark", "golden sun peach", "golden sun peach", "golden sun peach"):
        H.make_herb(world, name, 0, me)
    app.submit("look")
    happened = set()
    for step in range(260):
        game = app.game
        if game is None:
            break
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.6 and app.choices:
            stay = [n for n, c in enumerate(app.choices, 1) if c.action.verb not in ("travel", "routes")]
            app.submit(str(rng.choice(stay or [1])))
        else:
            app.submit(rng.choice(["alchemy", "gather", "herbalist", "swallow", "seal", "force out", "look", "rest",
                                   "journal", "experiment", "empty furnace",
                                   "taste " + rng.choice(("ginseng", "lotus", "willow", "peach", "vine")),
                                   "add " + rng.choice(("ginseng", "lotus", "willow", "peach", "vine"))]))
        if rng.random() < 0.05:
            app.handle_key("f4", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    done = happened & {"herb_tasted", "herbs_gathered", "herb_bought", "experimented", "refined", "pill_taken"}
    assert len(done) >= 3, done
    app.shutdown()
