"""A wandering physician, played at random (phase 5c): joins the Guild, draws from a hall, steals by night, heals,
is bound and freed; nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing

WORDS = ["pill hall", "guild", "clinic", "doctors", "night", "nightfall", "bound", "read", "remedies", "alchemy",
         "look", "rest", "journal", "swallow", "treat", "steal", "draw", "harvest"]


@pytest.mark.parametrize("seed", [5, 29])
def test_a_wandering_physician(tmp_path, seed):
    import systems.alchemy as A
    import systems.control as C
    from systems import factions as F
    from systems import halls
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Physician{seed}", world_seed=seed)
    world = app.game.world
    me = world.get_meta("player_id")
    world.update_data(me, silver=5000, guild_rank=1)
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.relate(me, sect, "member_of", 2, {"role": "disciple", "hall": 0, "merit": 2000, "status": "member",
                                            "secret": False})
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, A.recipe_entity(world, "calming"), "knows_recipe", 0.5)
    for key, grade in (("wood_healing", 2), ("wood_healing", 2), ("metal_antidote", 5), ("control", 4)):
        A.make_pill(world, me, A.recipe_entity(world, key), grade, 0.8)
    master = halls.staff_at(world, sect, seat, roles=("disciple",))[0]
    C.bind(world, me, master)  # bound from the start: the worms, the service and the antidote all come into play
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
    done = happened & {"pill_drawn", "garden_harvested", "secret_scroll_given", "physician_treated", "asked_doctor",
                       "waited_for_night", "hall_surveyed", "hall_theft", "healed", "scroll_read", "pill_taken",
                       "servant_fed", "service_rendered"}
    assert len(done) >= 3, done
    app.shutdown()
