"""A troubled heart, played at random (phase 5e): a fighter who kills and spares, swears and breaks oaths, meets
their demons at the gate, and carries a hungry blade; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing

WORDS = ["heart", "swear to kill no one", "swear vengeance", "face", "bury", "turn back", "respects", "breakthrough",
         "cultivate", "meditate", "look", "rest", "journal", "challenge", "kill", "spare"]


@pytest.mark.parametrize("seed", [9, 31])
def test_a_troubled_heart(tmp_path, seed):
    import systems.demons as D
    import systems.gear as gear
    import systems.heart as HT
    from systems.bodies import load_body, save_body
    from world.events import commit
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Heart{seed}", world_seed=seed)
    world = app.game.world
    me = world.get_meta("player_id")
    here = next(iter(world.targets(me, "located_in")))
    body = load_body(world, me)
    body.realm, body.bottleneck, body.energy_years = 1, True, 5.0
    body.flags.append("sensed_qi")
    body.meridians["Governing"].state = "open"
    save_body(world, me, body)
    HT.write(world, me, steady=25.0, lean=-50.0, daos={"sword": 0.4})
    for kind, weight in (("fear", 2), ("guilt", 1)):
        D.add_demon(world, me, kind, None, weight)
    blade = gear.make_item(world, "weapon", "sword", 2, me, "bought")
    world.update_data(blade, spirit={"nature": "bloodthirsty", "bond": 0.0, "master": me, "known_by": [me]})
    commit(world, gear.wield_events(world, me, blade, here))
    app.submit("look")
    happened = set()
    for step in range(260):
        game = app.game
        if game is None:
            break
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.55 and app.choices:
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
    done = happened & {"heart_trial", "oath_sworn", "oath_kept", "oath_broken", "epiphany", "demon_stirred",
                       "blade_whispered", "spirit_felt"}
    assert len(done) >= 2, done
    app.shutdown()
