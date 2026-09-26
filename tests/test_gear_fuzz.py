"""An armed wanderer, played at random (phase 5a): buys, draws, takes, wields, sells and fights for famous
blades; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing


@pytest.mark.parametrize("seed", [3, 29])
def test_an_armed_wanderer(tmp_path, seed, monkeypatch):
    import systems.famous as FW
    import systems.provenance as provenance
    from systems import factions as F
    from systems import halls
    monkeypatch.setattr(provenance, "COVET_CHANCE", 0.5)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Blade{seed}", world_seed=seed)
    world = app.game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    halls.staff_at(world, sect, seat)
    me = world.get_meta("player_id")
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    world.update_data(me, silver=5000)
    FW.ensure_famous(world)
    for item in FW.famous_weapons(world):  # the player has heard every tale: every blade is known on sight
        for fact in world.facts(predicate="blade_legend", subject=item):
            from systems.beliefs import believe
            believe(world, me, fact.id, fact.data["variant"], None, 1.0, 1, "gossip")
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
            app.submit(rng.choice(["gear", "smith", "unwield", "look", "rest", "journal", "sky", "standing",
                                   "wield " + rng.choice(("sword", "saber", "spear", "staff", "robe", "mail")),
                                   "inspect " + rng.choice(("sword", "saber", "spear", "staff")), "challenge"]))
        if rng.random() < 0.05:
            app.handle_key("f4", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    assert happened & {"gear_bought", "armoury_drawn", "gear_taken_up", "gear_passed"}, happened
    app.shutdown()
