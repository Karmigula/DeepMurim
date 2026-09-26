"""A sect heir, played at random through crisis after crisis (phase 4g): nothing breaks, no rule is broken."""

import random

import pytest

from app import App
from config import Config
from tests.test_fuzz import FIGHTING, keep_playing


@pytest.mark.parametrize("seed", [4, 13])
def test_a_sect_heir(tmp_path, seed, monkeypatch):
    """A core disciple at their sect's seat as its leaders fall, again and again: claim, declare, sway, search,
    champion, trade the token, and whatever the camps decide."""
    import systems.claimants as C
    import systems.lives as lives
    import systems.succession_crisis as SC
    import systems.world_events as W
    from systems import factions as F
    from systems import halls
    from world.events import Event, commit
    monkeypatch.setitem(W.TYPES, "succession_crisis", {**W.TYPES["succession_crisis"],
                                                       "stages": {**W.TYPES["succession_crisis"]["stages"],
                                                                  "announced": 4, "active": 8, "aftermath": 3}})
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Heir{seed}", world_seed=seed)
    world = app.game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    me = world.get_meta("player_id")
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    app.submit("look")

    def a_leader_falls(world):
        """The seat falls empty, and a crisis begins where the heir stands."""
        if SC.live(world, sect) is not None:
            return
        for leader in C.staff(world, sect, ("leader",)):
            if world.entity(leader).data.get("is_player"):
                return
            commit(world, [Event("died", (leader, leader), seat, {"cause": "killed", "world": True})])
        claims = C.declare(world, sect, None)
        if len(claims) >= 2:
            commit(world, SC.begin_events(world, sect, lives.current_season(world), "violence", claims, None,
                                          force=True))
    happened = set()
    for step in range(300):
        game = app.game
        if game is None:
            break
        if step % 25 == 0 and game.world.get_meta("player_id") == me and game.combat is None:
            a_leader_falls(game.world)
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2", "3"]))
        elif rng.random() < 0.5 and app.choices:
            stay = [n for n, c in enumerate(app.choices, 1) if c.action.verb not in ("travel", "routes")]
            app.submit(str(rng.choice(stay or [1])))
        else:
            app.submit(rng.choice(["claim", "search chambers", "standing", "look", "rest", "meditate week",
                                   "journal", "sky", "step down", "declare " + rng.choice("abcdefghijklmnopqrstuvwxyz")]))
        if rng.random() < 0.05:
            app.handle_key("f6", "")
        if app.game is not None:
            happened |= {row[0] for row in app.game.world._conn.execute("select distinct kind from chronicle")}
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    assert {"sky_started", "crisis_settled"} <= happened, happened
    app.shutdown()
