import random
import time

import pytest

import systems.duel as duel
import systems.mortality as mortality
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


def start(world, kind, town, data):
    commit(world, sky.start_events(world, kind, town, world.time, data))
    return W.index(world)[-1][W.ID]


def assembly(game, **extra):
    import systems.events.grand_assembly as ga
    town = game.place.id
    return start(game.world, "grand_assembly", town, {**ga.start_data(game.world, town, 10, rng_for(1, "a")), **extra})


def to_day(game, occurrence, k):
    game.world.set_time(T.day_start(game.world.entity(occurrence), k))
    sky.observe(game.world, game.place.id)


def bracket(world, occurrence):
    return world.entity(occurrence).data["data"]


def test_the_assembly_comes_every_twelve_seasons(game):
    world = game.world
    world.set_time(0)
    found = [n for n in range(48) for e in sky.season_events(world, n)
             if e.kind == "sky_started" and e.data["type"] == "grand_assembly"]
    assert len(found) == 4 and [b - a for a, b in zip(found, found[1:])] == [12, 12, 12]


def test_the_bracket_is_seeded_by_what_the_host_believes(game):
    world, town = game.world, game.place.id
    famous = founding.make_person(world, "test:famous", town, occupation="monk", age=40, realm="second-rate")
    hidden = founding.make_person(world, "test:hidden", town, occupation="monk", age=40, realm="profound")
    for i in range(4):
        victim = founding.make_person(world, f"test:victim:{i}", town, occupation="monk", age=40)
        record_fact(world, famous, "defeated", victim, place=town, weight=3.0,
                    variant=make_variant("defeated", famous, victim, place=place_name(world, town)))
    occurrence = assembly(game, registered=[famous, hidden])
    to_day(game, occurrence, 1)
    entrants = bracket(world, occurrence)["entrants"]
    assert entrants[0] == famous and entrants.index(hidden) > entrants.index(famous)
    assert len(entrants) == 32 and len(bracket(world, occurrence)["rounds"]) == 5


def test_rounds_resolve_by_day_and_crown_one_champion(game):
    world, town = game.world, game.place.id
    occurrence = assembly(game)
    to_day(game, occurrence, 1)
    assert all(m["how"] is None for m in bracket(world, occurrence)["rounds"][0])
    to_day(game, occurrence, 2)
    rounds = bracket(world, occurrence)["rounds"]
    assert all(m["how"] is not None for m in rounds[0]) and all(m["how"] is None for m in rounds[1])
    to_day(game, occurrence, 9)
    t = bracket(world, occurrence)
    champion = t["champion"]
    assert t["finished"] and champion == t["rounds"][-1][0]["winner"]
    assert t["title"] in world.entity(champion).data["titles"]
    assert world.facts(predicate="won_tournament", subject=champion)
    assert len(world.facts(predicate="placed")) == 3
    assert check_tournaments(world) == []


def test_the_same_seed_crowns_the_same_champion(tmp_path):
    champions = []
    for n in range(2):
        g = Game.new(tmp_path / f"g{n}.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
        g.start()
        g.world.set_time(10 * W.SEASON + 8)
        occurrence = assembly(g)
        to_day(g, occurrence, 9)
        champions.append(bracket(g.world, occurrence)["champion"])
        g.close()
    assert champions[0] == champions[1] is not None


def test_a_dead_entrant_gives_a_walkover(game):
    world = game.world
    occurrence = assembly(game)
    to_day(game, occurrence, 1)
    first = bracket(world, occurrence)["rounds"][0][0]
    world.update_data(first["b"], dead=True)
    to_day(game, occurrence, 2)
    first = bracket(world, occurrence)["rounds"][0][0]
    assert first["how"] == "walkover" and first["winner"] == first["a"]


def test_a_tournament_seen_only_after_it_ended_resolves_in_order(game):
    world = game.world
    occurrence = assembly(game)
    world.set_time(world.entity(occurrence).data["over_at"] + 10)
    sky.observe(world, game.place.id)
    t = bracket(world, occurrence)
    assert t["finished"] and t["champion"] is not None
    assert all(m["how"] is not None for r in t["rounds"] for m in r)
    assert check_tournaments(world) == []


def test_npcs_never_kill_in_a_bout(game, monkeypatch):
    for key in mortality.KILL_CHANCE:
        monkeypatch.setitem(mortality.KILL_CHANCE, key, 1.0)
    world, town = game.world, game.place.id
    brute = founding.make_person(world, "test:brute", town, occupation="bandit", age=30,
                                 traits=["cunning", "greedy"])
    game._start_duel(brute, "bout")
    d = game.combat
    event = duel._end_event(world, d, "lost", "broken", random.Random(1), {"player": 90.0, "opponent": 10.0}, 5)
    assert event.data["verdict"] == "spare" and not event.data.get("player_killed") and event.data["silver"] == 0


def test_a_bout_verdict_is_spare_or_kill(game):
    world, town = game.world, game.place.id
    rival = founding.make_person(world, "test:rival", town, occupation="monk", age=30)
    game._start_duel(rival, "bout")
    game.combat.stage = "verdict"
    assert duel.verdict_events(world, game.combat, "rob") == []
    assert duel.verdict_events(world, game.combat, "spare")[0].data["result"] == "won"


def test_the_tournament_rules_catch_a_bad_bracket(game):
    world = game.world
    occurrence = assembly(game)
    to_day(game, occurrence, 2)
    t = dict(bracket(world, occurrence))
    t["rounds"][0][0] = dict(t["rounds"][0][0], winner=999999)
    world.update_data(occurrence, data=t)
    assert any("winner" in p for p in check_tournaments(world))


def test_a_round_of_the_assembly_is_quick(game):
    world = game.world
    occurrence = assembly(game)
    to_day(game, occurrence, 1)  # the draw prepares every fighter's arts and body
    world.set_time(T.day_start(world.entity(occurrence), 2))
    start = time.process_time()
    T.resolve(world, occurrence)
    assert time.process_time() - start < 0.06
