import time

import pytest

import systems.encounters as encounters
import systems.lives as lives
from engine.game import Game
from systems import founding
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.realms import add_energy


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def person(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **data)


def seasons_pass(game, n):
    game.world.set_time(game.world.time + n * lives.SEASON)


def test_a_new_person_starts_in_the_present(game):
    pid = person(game, "test:new", occupation="innkeeper")
    assert lives.lived_to(game.world, pid) == lives.current_season(game.world)
    assert lives.catch_up(game.world, pid) == 0


def test_a_year_away_ages_everyone_a_year(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    pid = person(game, "test:ager", occupation="innkeeper", age=30)
    lives.lived_to(game.world, pid)
    seasons_pass(game, 4)
    assert lives.catch_up(game.world, pid) == 4
    data = game.world.entity(pid).data
    assert data["age"] == 31.0 and data["lived_to"] == lives.current_season(game.world)


def test_commoners_do_not_cultivate_and_fighters_do(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    monkeypatch.setattr(lives, "breakthrough_chance", lambda body, met: 0.0)
    clerk = person(game, "test:clerk", occupation="innkeeper")
    blade = person(game, "test:blade", occupation="wandering swordsman", realm="third-rate")
    before = {p: load_body(game.world, p).energy_years for p in (clerk, blade)}
    for p in (clerk, blade):
        lives.lived_to(game.world, p)
    seasons_pass(game, 4)
    for p in (clerk, blade):
        lives.catch_up(game.world, p)
    assert load_body(game.world, clerk).energy_years == before[clerk]
    gained = load_body(game.world, blade).energy_years - before[blade]
    assert gained == pytest.approx(lives.talent(game.world, blade), abs=1e-3)


def test_the_old_die_and_are_buried(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    pid = person(game, "test:elder", occupation="innkeeper", age=95)
    lives.lived_to(game.world, pid)
    seasons_pass(game, 1)
    lives.catch_up(game.world, pid)
    entity = game.world.entity(pid)
    assert entity.data["dead"] and game.world.targets(pid, "buried_at") == [game.place.id]
    [fact] = game.world.facts(predicate="died", subject=pid)
    assert fact.place == game.place.id and fact.weight == 1.0


def test_a_breakthrough_to_second_rate_is_news(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    monkeypatch.setattr(lives, "breakthrough_chance", lambda body, met: 1.0)
    pid = person(game, "test:rising", occupation="wandering swordsman", realm="third-rate")
    body = load_body(game.world, pid)
    body.energy_years = 5.0
    add_energy(body, 0.0)
    save_body(game.world, pid, body)
    lives.lived_to(game.world, pid)
    seasons_pass(game, 1)
    lives.catch_up(game.world, pid)
    assert game.world.entity(pid).data["realm"] == "second-rate"
    assert game.world.facts(predicate="broke_through", subject=pid)


def test_one_catch_up_or_many_give_the_same_life(game, tmp_path):
    twin = Game.new(tmp_path / "twin.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    twin.start()
    results = []
    for g, steps in ((game, [8]), (twin, [1] * 8)):
        pid = person(g, "test:twin", occupation="wandering swordsman", realm="third-rate", age=60)
        lives.lived_to(g.world, pid)
        for n in steps:
            seasons_pass(g, n)
            lives.catch_up(g.world, pid)
        data = g.world.entity(pid).data
        results.append((data["age"], data.get("dead", False), data["realm"],
                        round(load_body(g.world, pid).energy_years, 6)))
    twin.close()
    assert results[0] == results[1]


def test_a_century_stale_person_catches_up_coarsely_and_fast(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    pid = person(game, "test:hermit", occupation="wandering swordsman", age=20)
    lives.lived_to(game.world, pid)
    seasons_pass(game, 400)
    start = time.perf_counter()
    lived = lives.catch_up(game.world, pid)
    elapsed = time.perf_counter() - start
    data = game.world.entity(pid).data
    assert lived == 400 and data["age"] == 120.0 and data["lived_to"] == lives.current_season(game.world)
    years = [e for e in game.world.chronicle_about(pid, limit=500) if e.kind == "lived"]
    assert len(years) < 150 and any(e.data["span"] == 4 for e in years)
    assert elapsed < 0.06, f"a century took {elapsed * 1000:.0f} ms"  # ruling 10: spec says 20 ms


def test_the_player_is_never_aged(game):
    age = game.player.data.get("age")
    seasons_pass(game, 8)
    assert lives.catch_up(game.world, game.player.id) == 0
    assert game.world.entity(game.player.id).data.get("age") == age


def test_ages_never_go_down(game):
    pid = person(game, "test:steady", occupation="innkeeper", age=40)
    lives.lived_to(game.world, pid)
    ages = []
    for _ in range(6):
        seasons_pass(game, 1)
        lives.catch_up(game.world, pid)
        entity = game.world.entity(pid)
        if entity.data.get("dead"):
            break
        ages.append(entity.data["age"])
    assert ages == sorted(ages)


def test_a_child_comes_of_age_with_a_trade(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    pid = person(game, "test:kid", occupation="child", age=15.5)
    lives.lived_to(game.world, pid)
    seasons_pass(game, 2)
    lives.catch_up(game.world, pid)
    assert game.world.entity(pid).data["occupation"] != "child"
