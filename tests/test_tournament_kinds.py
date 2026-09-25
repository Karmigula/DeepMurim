import pytest

import systems.rankings as R
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.game import Game
from systems import factions as F
from systems import founding
from systems.beliefs import believe
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


def finish(world, occurrence, town):
    world.set_time(world.entity(occurrence).data["over_at"] + 1)
    sky.observe(world, town)
    return world.entity(occurrence).data["data"]


def school(world):
    return next(f.id for f in world.entities("faction") if f.data["type"] == "school")


def test_the_meet_takes_only_the_young(game):
    import systems.events.dragon_phoenix as dp
    world, town = game.world, game.place.id
    old = founding.make_person(world, "test:old", town, occupation="monk", age=50, realm="first-rate")
    occurrence = start(world, "dragon_phoenix", town, {**dp.start_data(world, town, 10, rng_for(1, "d")),
                                                        "registered": [old]})
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)
    entrants = world.entity(occurrence).data["data"]["entrants"]
    assert len(entrants) == 16 and old not in entrants
    assert all(world.entity(p).data.get("age", 30) <= 30 for p in entrants)


def test_the_meets_champion_honours_their_sect(game):
    import systems.events.dragon_phoenix as dp
    world, town = game.world, game.place.id
    faction = school(world)
    prodigy = founding.make_person(world, "test:prodigy", town, occupation="monk", age=20, realm="first-rate")
    world.relate(prodigy, faction, "member_of", 1, {"role": "disciple", "hall": None, "merit": 0, "status": "member",
                                                    "secret": False})
    power = world.entity(faction).data.get("power", 50)
    occurrence = start(world, "dragon_phoenix", town, dp.start_data(world, town, 10, rng_for(1, "d")))
    commit(world, dp.rewards(world, world.entity(occurrence), prodigy))
    assert world.entity(faction).data["power"] == min(100, power + dp.HONOUR)
    t = finish(world, occurrence, town)
    assert t["finished"] and t["title"].startswith("Dragon-Phoenix of year")


def test_sect_contests_go_to_seats_with_disciples(game):
    import systems.events.sect_contest as sc
    assert game.place.id in sc.places(game.world, 10, rng_for(1, "s"))
    assert sc.eligible(game.world, game.place.id, 10)


def test_a_sect_contest_far_away_only_names_its_champion(game):
    import systems.events.sect_contest as sc
    from world.gen.materialize import ensure_town
    world, town = game.world, game.place.id
    occurrence = start(world, "sect_contest", town, sc.start_data(world, town, 10, rng_for(1, "s")))
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, ensure_town(world, 4, 4, 0), "located_in")
    t = finish(world, occurrence, town)
    assert t["finished"] and t["rounds"] == [] and t["champion"] in sc.invite(world, world.entity(occurrence))
    assert check_tournaments(world) == []


def test_a_sect_contest_nobody_is_near_is_settled_in_a_line(game):
    import systems.events.sect_contest as sc
    world, town = game.world, game.place.id
    events = sc.summary(world, town, 10, rng_for(1, "s"))
    commit(world, events)
    champion = events[0].actors[0]
    assert sc.eligible(world, town, 10) and events[0].data["title"] in world.entity(champion).data["titles"]
    assert world.facts(predicate="won_tournament", subject=champion)
    assert F.membership(world, champion, school(world))[1]["merit"] >= 20


def test_a_lei_tai_goes_up_only_near_the_player(game):
    import systems.events.lei_tai as lt
    from world.gen.materialize import ensure_town
    world = game.world
    far = ensure_town(world, 6, 6, 0)
    assert not lt.eligible(world, far, 10)


def test_a_small_sect_contest_fills_with_byes(game):
    import systems.events.sect_contest as sc
    world, town = game.world, game.place.id
    occurrence = start(world, "sect_contest", town, sc.start_data(world, town, 10, rng_for(1, "s")))
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)  # the draw: the byes go through at once
    t = world.entity(occurrence).data["data"]
    entrants = t["entrants"]
    assert len(entrants) == 4 and sum(m["how"] == "bye" for m in t["rounds"][0]) == 4
    t = finish(world, occurrence, town)
    assert t["finished"] and t["champion"] in entrants
    rank, data = F.membership(world, t["champion"], school(world))
    assert data["merit"] >= 20 and rank >= 1
    assert check_tournaments(world) == []


def test_a_lei_tai_settles_its_afternoon_and_pays_the_holder(game):
    import systems.events.lei_tai as lt
    world, town = game.world, game.place.id
    for i in range(3):
        founding.make_person(world, f"test:brawler:{i}", town, occupation="wandering swordsman", age=30,
                             realm="third-rate")
    assert lt.eligible(world, town, 10)
    occurrence = start(world, "lei_tai", town, lt.start_data(world, town, 10, rng_for(1, "l")))
    sky.observe(world, town)
    t = world.entity(occurrence).data["data"]
    holder = t["holder"]
    assert holder is not None and t["results"]
    silver = silver_of(world, holder)
    t = finish(world, occurrence, town)
    assert t["paid"] and silver_of(world, holder) == silver + t["purse"]
    assert world.facts(predicate="held_lei_tai", subject=holder)


def test_the_pavilion_counts_bouts_and_championships(game):
    world, town = game.world, game.place.id
    pav = R.ensure_pavilion(world)
    champ = founding.make_person(world, "test:champ", town, occupation="monk", age=30, realm="first-rate")
    rival = founding.make_person(world, "test:rival", town, occupation="monk", age=30, realm="first-rate")
    for predicate, target, extra in (("bested", rival, {}), ("won_tournament", None, {"kind": "grand_assembly"})):
        variant = make_variant(predicate, champ, target, place=place_name(world, town), realm="first-rate")
        variant.update(extra)
        fact = record_fact(world, champ, predicate, target, place=town, variant=variant, spread=False)
        believe(world, pav, fact, variant, None, 0.9, 1, "informant")
    assert R.scores(world, pav)[champ] == pytest.approx(300 + R.WIN_POINTS + 60)


def test_the_pavilion_forgets_deeds_older_than_a_generation(game):
    world, town = game.world, game.place.id
    pav = R.ensure_pavilion(world)
    hero = founding.make_person(world, "test:hero", town, occupation="monk", age=30, realm="first-rate")
    for predicate in ("bested", "tribulation"):
        variant = make_variant(predicate, hero, None, place=place_name(world, town), realm="first-rate")
        fact = record_fact(world, hero, predicate, None, place=town, variant=variant, spread=False)
        believe(world, pav, fact, variant, None, 0.9, 1, "informant")
    world.set_time(world.time + (R.FORGET_YEARS + 1) * R.YEAR)
    n = world.time // W.SEASON
    R.season_hook(world, n - n % 4)
    kept = {f.predicate for _, f in world.known_facts(pav)}
    assert "tribulation" in kept and "bested" not in kept


def test_the_rules_catch_an_entrant_too_old_for_the_meet(game):
    import systems.events.dragon_phoenix as dp
    world, town = game.world, game.place.id
    occurrence = start(world, "dragon_phoenix", town, dp.start_data(world, town, 10, rng_for(1, "d")))
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)
    entrant = world.entity(occurrence).data["data"]["entrants"][0]
    world.update_data(entrant, age=55)
    assert any("does not qualify" in p for p in check_tournaments(world))
