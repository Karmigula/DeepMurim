"""A heavy karma, played at random (phase 5f): a fighter who kills and spares, gives alms, breaks through into
heaven's waves and meets their threads on the road; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing

WORDS = ["endure", "shelter", "face", "bury", "breakthrough", "temple", "alms", "incense", "fortune", "look", "rest",
         "journal", "challenge", "kill", "spare", "rob", "meditate", "heart"]


@pytest.mark.parametrize("seed", [9, 31])
def test_a_heavy_karma(tmp_path, seed):
    import systems.karma as K
    import systems.threads as TH
    import systems.tribulations as TR
    from systems.bodies import load_body, save_body
    from world.events import commit
    from world.gen.materialize import people_at
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Karma{seed}", world_seed=seed)
    world = app.game.world
    me = world.get_meta("player_id")
    here = next(iter(world.targets(me, "located_in")))
    world.update_data(me, silver=3000)
    body = load_body(world, me)
    body.realm, body.bottleneck, body.energy_years = 2, True, 20.0
    body.flags.append("sensed_qi")
    save_body(world, me, body)
    K.write(world, me, sin=260.0, merit=20.0)
    for person in people_at(world, here, exclude=me)[:4]:
        TH.add_thread(world, me, person.id, rng.choice(["spared", "robbed", "crippled", "healed"]))
    commit(world, TR.gather_events(world, me, here, 3, False, "breakthrough"))
    app.submit("look")
    happened = set()
    for step in range(260):
        game = app.game
        if game is None:
            break
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.55 and app.choices:
            app.submit(str(rng.randrange(1, len(app.choices) + 1)))
        else:
            app.submit(rng.choice(WORDS))
        if rng.random() < 0.05:
            app.handle_key("f4", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    done = happened & {"tribulation_wave", "tribulation_passed", "alms_given", "fortune_read", "fated_repaid",
                       "misfortune", "incense_burned", "encounter"}
    assert len(done) >= 2, done
    app.shutdown()
