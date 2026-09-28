"""A wandering smith, played at random (phase 5d): buys iron, butchers, forges, refines, names, studies, lays
arrays and fights in them, commissions and enters the Meet; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing

WORDS = ["crafts", "anvil", "forge", "clear anvil", "meet", "study", "smith", "look", "rest", "journal", "challenge",
         "lay confusion", "lay killing", "lay binding", "lay seclusion", "lay concealment"]


@pytest.mark.parametrize("seed", [9, 31])
def test_a_wandering_smith(tmp_path, seed):
    import systems.formations as FM
    import systems.materials as M
    import systems.meet as MT
    from world.events import commit
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Smith{seed}", world_seed=seed)
    world = app.game.world
    me = world.get_meta("player_id")
    world.update_data(me, silver=5000)
    for name in ("iron ingot", "iron ingot", "black steel", "black steel", "spirit iron", "beast bone", "beast core"):
        M.make_material(world, name, me)
    for key in ("confusion", "killing", "binding", "seclusion", "concealment"):
        FM.learn(world, me, key)
    FM.add_flags(world, me, 40)
    commit(world, MT.open_events(world, 0))
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
            app.submit(rng.choice(WORDS))
        if rng.random() < 0.05:
            app.handle_key("f4", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    done = happened & {"forged", "gear_refined", "material_bought", "formation_laid", "formation_studied",
                       "flags_bought", "forge_bought", "masterwork_named", "meet_entered"}
    assert len(done) >= 3, done
    app.shutdown()
