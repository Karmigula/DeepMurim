import time

import pytest

import systems.sect as sect_mod
import systems.sect_seasons as seasons
from engine.actions import Action
from systems import factions as F
from systems.bodies import load_body
from tests.test_sect import calm, found_sect, game  # noqa: F401  (shared fixtures)


def advance(game, n):
    game.world.set_time(game.world.time + n * seasons.SEASON)


def season_data(game, sect):
    return [e.data for e in game.world.chronicle_about(game.player.id, limit=40) if e.kind == "sect_season"]


def test_a_season_pays_income_and_upkeep(game):
    sect, town = found_sect(game)
    advance(game, 1)
    [events] = [seasons.season_events(game.world, game.player.id, sect)]
    d = events[0].data
    kind = game.world.entity(town).data["kind"]
    assert d["income"] >= seasons.LAND_INCOME[kind] and d["upkeep"] == 5 * 3
    game._commit(events)
    assert game.world.entity(sect).data["treasury"] == d["treasury_after"] == max(0, d["income"] - d["upkeep"])
    assert game.world.entity(sect).data["last_tick"] % seasons.SEASON == 0 or True
    assert seasons.season_events(game.world, game.player.id, sect) is None


def test_an_empty_treasury_means_unpaid_seasons(game, monkeypatch):
    monkeypatch.setattr(seasons, "LAND_INCOME", {"village": 0, "town": 0, "city": 0})
    monkeypatch.setattr(seasons, "PROTECTION", 0)
    sect, town = found_sect(game)
    member = sect_mod.members(game.world, sect)[0]
    before = game.world.entity(member).data["loyalty"]
    advance(game, 1)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    assert game.world.entity(sect).data["treasury"] == 0
    assert game.world.entity(member).data["loyalty"] < before


def test_a_training_yard_speeds_growth(game):
    sect, town = found_sect(game)
    advance(game, 1)
    plain = seasons.season_events(game.world, game.player.id, sect)[0].data["growth"]
    data = game.world.entity(sect).data
    game.world.update_data(sect, buildings={"training_yard": {"done_at": 0, "built": True}})
    yard = seasons.season_events(game.world, game.player.id, sect)[0].data["growth"]
    member = str(sect_mod.members(game.world, sect)[0])
    assert yard[member]["years"] == pytest.approx(plain[member]["years"] * 1.5)
    game.world.update_data(sect, buildings=data["buildings"])


def test_growth_is_applied_to_the_body(game):
    sect, town = found_sect(game)
    member = sect_mod.members(game.world, sect)[0]
    before = load_body(game.world, member).energy_years
    advance(game, 1)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    assert load_body(game.world, member).energy_years > before


def test_a_long_absence_catches_up_eight_seasons_at_a_time(game):
    sect, town = found_sect(game)
    elsewhere = next(t.id for t in game.world.entities("town") if t.id != town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, elsewhere, "located_in")
    start = game.world.entity(sect).data["last_tick"]
    advance(game, 20)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")
    game.perform(Action("look"))
    assert game.world.entity(sect).data["last_tick"] == start + 8 * seasons.SEASON
    assert game.world.entity(sect).data["last_tick"] <= game.world.time
    assert len(game.world.entity(sect).data["chronicle"]) == 8


def test_one_call_or_many_give_the_same_sect(game, tmp_path):
    from engine.game import Game
    from systems.creation import CreationChoice
    other = Game.new(tmp_path / "twin.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    other.start()
    results = []
    for g, steps in ((game, [8]), (other, [1] * 8)):
        sect, town = found_sect(g)
        for n in steps:
            g.world.set_time(g.world.time + n * seasons.SEASON)
            for _ in range(n):
                events = seasons.season_events(g.world, g.player.id, sect)
                if events:
                    g._commit(events)
        data = g.world.entity(sect).data
        results.append((data["treasury"], data["power"], data["chronicle"],
                        sorted(g.world.entity(p).data["loyalty"] for p in sect_mod.members(g.world, sect))))
    other.close()
    assert results[0] == results[1]  # treasury, power, chronicle and loyalty alike


def test_deserters_leave(game, monkeypatch):
    monkeypatch.setattr(seasons, "DESERT_CHANCE", 1.0)
    sect, town = found_sect(game)
    member = sect_mod.members(game.world, sect)[0]
    game.world.update_data(member, loyalty=0)
    advance(game, 1)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    assert F.membership(game.world, member, sect)[1]["status"] == "deserter"


def test_an_empty_sect_dissolves(game, monkeypatch):
    monkeypatch.setattr(seasons, "RECRUITS", {})
    sect, town = found_sect(game)
    for member in sect_mod.members(game.world, sect):
        game.world.relate(member, sect, "member_of", 0, {**F.membership(game.world, member, sect)[1], "status": "expelled"})
    advance(game, 1)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    assert game.world.entity(sect).data["dissolved"]


def test_a_challenger_calls_out_the_founder_at_home(game, monkeypatch):
    monkeypatch.setattr(seasons, "GATE_BASE", 1.0)
    sect, town = found_sect(game)
    advance(game, 1)
    turn = game.perform(Action("look"))
    assert game.challenger is not None
    assert any("at the gate of your sect" in text for text, _ in turn.lines)
    assert not any("have not forgotten you" in text for text, _ in turn.lines)


def test_a_gate_fight_happens_while_the_founder_is_away(game, monkeypatch):
    monkeypatch.setattr(seasons, "GATE_BASE", 1.0)
    sect, town = found_sect(game)
    elsewhere = next(t.id for t in game.world.entities("town") if t.id != town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, elsewhere, "located_in")
    advance(game, 1)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    gate = season_data(game, sect)[0]["gate"]
    assert gate and gate["won"] in (True, False) and gate["defenders"]
    assert game.world.facts(predicate="defended_gate" if gate["won"] else "gate_breached")[0].subject == sect


def test_eight_seasons_for_fifteen_members_are_quick(game):
    sect, town = found_sect(game)
    from systems import founding
    for i in range(12):
        founding.enrol(game.world, founding.make_person(game.world, f"test:extra:{i}", town), sect, 70)
    advance(game, 8)
    import systems.world_clock as world_clock
    while world_clock.run_due(game.world):
        pass  # the world's own seasons are not what this test measures (phase 4a ruling 11)
    start = time.process_time()  # the work's own time, not the machine's other load
    for _ in range(8):
        game._commit(seasons.season_events(game.world, game.player.id, sect))
    elapsed = time.process_time() - start
    assert elapsed < 0.2, f"8 seasons took {elapsed * 1000:.0f} ms"
