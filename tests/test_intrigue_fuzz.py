"""A plotting heir, played at random through poisoned masters, puppets, forgeries and frames (phase 4h):
nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing


@pytest.mark.parametrize("seed", [5, 21])
def test_a_plotting_heir(tmp_path, seed, monkeypatch):
    import systems.claimants as C
    import systems.frames as R
    import systems.lives as lives
    import systems.murder as M
    import systems.puppets as U
    import systems.succession_crisis as SC
    import systems.world_events as W
    from systems import factions as F
    from systems import founding, halls
    from world.events import Event, commit
    monkeypatch.setitem(W.TYPES, "succession_crisis", {**W.TYPES["succession_crisis"],
                                                       "stages": {**W.TYPES["succession_crisis"]["stages"],
                                                                  "announced": 4, "active": 8, "aftermath": 3}})
    monkeypatch.setattr(M, "MURDER_CHANCE", 1.0)
    monkeypatch.setattr(M, "EXAMINE_BASE", 1.0)
    monkeypatch.setattr(U, "PUPPET_CHANCE", 0.5)
    monkeypatch.setattr(R, "FORGE_CHANCE", 0.5)
    monkeypatch.setattr(R, "FRAME_CHANCE", 0.3)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Plotter{seed}", world_seed=seed)
    world = app.game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    me = world.get_meta("player_id")
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    world.update_data(me, silver=20000)
    founding.make_person(world, f"fuzz:follower:{seed}", seat, occupation="wandering swordsman", age=25, sworn_to=me)
    vial = world.add_entity("treasure", "a vial of black lotus", {"kind": "poison", "value": 50, "used": False})
    world.relate(me, vial, "owns")
    app.submit("look")

    def a_leader_falls(world):
        """The seat falls empty by a natural death (a poisoning, most often), and a crisis begins here."""
        if SC.live(world, sect) is not None:
            return
        for leader in C.staff(world, sect, ("leader",)):
            if world.entity(leader).data.get("is_player"):
                return
            commit(world, [Event("died", (leader, leader), seat, {"cause": "illness", "world": True})])
        claims = C.declare(world, sect, None)
        if len(claims) >= 2:
            commit(world, SC.begin_events(world, sect, lives.current_season(world), "suspicion", claims, None,
                                          force=True))
    happened = set()
    for step in range(300):
        game = app.game
        if game is None:
            break
        if step % 25 == 0 and game.world.get_meta("player_id") == me and game.focus is None and game.combat is None:
            a_leader_falls(game.world)
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.6 and app.choices:
            stay = [n for n, c in enumerate(app.choices, 1) if c.action.verb not in ("travel", "routes")]
            app.submit(str(rng.choice(stay or [1])))
        else:
            app.submit(rng.choice(["claim", "examine body", "standing", "look", "rest", "journal", "sky",
                                   "accuse " + rng.choice("abcdefghijklmnopqrstuvwxyz"), "meditate week"]))
        if rng.random() < 0.05:
            app.handle_key("f6", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    assert {"plot_made", "crisis_settled"} <= happened, happened
    app.shutdown()
