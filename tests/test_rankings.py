import time

import pytest

import systems.rankings as R
import systems.world_events as W
from debug.invariants import check_rankings
from engine.game import Game
from systems import founding
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from systems.reputation import reputation
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(3 * W.SEASON + 8)
    yield g
    g.close()


def deed(world, person, predicate, town, realm=None, target=None, age=None, heard=True):
    variant = make_variant(predicate, person, target, place=place_name(world, town), realm=realm)
    if age is not None:
        variant["age"] = age
    fact = record_fact(world, person, predicate, target, place=town, variant=variant, spread=False)
    if heard:
        believe(world, R.ensure_pavilion(world), fact, variant, None, 0.9, 1, "informant")
    return fact


def master(world, town, path, realm="first-rate", age=50):
    return founding.make_person(world, path, town, occupation="wandering swordsman", age=age, realm=realm)


def publish(world, n=4):
    from world.events import commit
    commit(world, R.revision_events(world, n))
    return world.entity(R.ensure_pavilion(world)).data


def test_only_the_pavilions_beliefs_count(game):
    world, town = game.world, game.place.id
    known, unheard = master(world, town, "test:known"), master(world, town, "test:unheard")
    deed(world, known, "tribulation", town, realm="first-rate")
    deed(world, unheard, "tribulation", town, realm="peak", heard=False)
    table = R.scores(world, R.ensure_pavilion(world))
    assert table[known] == 300 and unheard not in table


def test_a_hidden_master_stays_unranked(game):
    world, town = game.world, game.place.id
    hidden = master(world, town, "test:hidden", realm="profound")
    lists = publish(world)["lists"]
    assert all(hidden not in names for names in lists.values())


def test_the_dead_stay_listed_until_the_pavilion_hears(game):
    world, town = game.world, game.place.id
    old = master(world, town, "test:old", realm="peak", age=80)
    deed(world, old, "tribulation", town, realm="peak")
    assert old in publish(world)["lists"]["heaven"]
    died = deed(world, old, "died", town, heard=False)
    assert old in publish(world, 8)["lists"]["heaven"]
    believe(world, R.ensure_pavilion(world), died, world.fact(died).variant, None, 0.9, 1, "informant")
    assert old not in publish(world, 12)["lists"]["heaven"]


def test_beating_the_seventh_takes_most_of_their_score(game):
    world, town, me = game.world, game.place.id, game.player.id
    rivals = [master(world, town, f"test:rival:{i}", realm="first-rate") for i in range(8)]
    for i, rival in enumerate(rivals):
        deed(world, rival, "tribulation", town, realm="first-rate")
        for _ in range(i):
            deed(world, rival, "treasure", town)
    seventh = publish(world)["lists"]["heaven"][6]
    before = R.scores(world, R.ensure_pavilion(world))[seventh]
    deed(world, me, "defeated", town, realm="first-rate", target=seventh)
    mine = R.scores(world, R.ensure_pavilion(world))[me]
    assert mine == pytest.approx(300 + 10 + 0.6 * before)


def test_informants_hear_near_deeds_more_than_far_ones(game):
    world = game.world
    pav = R.ensure_pavilion(world)
    near, far = R.capital(world), ensure_town(world, 9, 9, 0)
    people = {place: [master(world, place, f"test:{place}:{i}") for i in range(40)] for place in (near, far)}
    for place, folk in people.items():
        for person in folk:
            deed(world, person, "broke_through", place, realm="second-rate", heard=False)
    world.set_time(world.time + W.SEASON + 1)
    R.informants(world, world.time // W.SEASON)
    heard = {f.subject for b, f in world.known_facts(pav)}
    assert len(heard & set(people[near])) > len(heard & set(people[far]))


def test_each_fact_gets_two_chances(game, monkeypatch):
    world = game.world
    monkeypatch.setattr(R, "INFORMANT_REACH", 0.0)
    person = master(world, game.place.id, "test:unlucky")
    deed(world, person, "broke_through", game.place.id, realm="second-rate", heard=False)
    world.set_time(world.time + W.SEASON + 1)
    R.informants(world, world.time // W.SEASON)
    assert len(world.get_meta("pavilion_retry")) == 1
    world.set_time(world.time + R.YEAR)
    R.informants(world, world.time // W.SEASON)
    assert world.get_meta("pavilion_retry") == []


def test_spring_publishes_the_lists_and_they_keep_the_rules(game):
    world, town = game.world, game.place.id
    for i in range(12):
        deed(world, master(world, town, f"test:m{i}", age=20 + 3 * i), "tribulation", town, realm="first-rate",
             age=20 + 3 * i)
    assert R.season_hook(world, 5) == []
    [event] = R.season_hook(world, 8)
    assert event.kind == "rankings_published" and len(event.data["lists"]["heaven"]) == 10
    from world.events import commit
    commit(world, [event])
    assert world.facts(predicate="published") and check_rankings(world) == []


def test_young_dragons_are_young_by_the_pavilions_belief(game):
    world, town = game.world, game.place.id
    youth = master(world, town, "test:youth", age=25)
    deed(world, youth, "tribulation", town, realm="first-rate", age=25)
    assert youth in publish(world)["lists"]["young"]
    world.set_time(world.time + 10 * R.YEAR)
    assert youth not in publish(world, 44)["lists"]["young"]


def test_a_city_posts_the_new_lists(game):
    world, me = game.world, game.player.id
    deed(world, master(world, game.place.id, "test:m"), "tribulation", game.place.id, realm="first-rate")
    publish(world)
    assert R.latest(world, me) is None
    assert not R.post_in_city(world, me, game.place.id) or world.entity(game.place.id).data["kind"] == "city"
    assert R.post_in_city(world, me, R.capital(world))
    assert R.latest(world, me)["year"] == 2


def test_a_ranked_name_carries_its_title_and_renown(game):
    world, town = game.world, game.place.id
    champion = master(world, town, "test:champion", realm="peak")
    deed(world, champion, "tribulation", town, realm="peak")
    before = reputation(world, town, champion).renown
    publish(world)
    fact = world.facts(predicate="published")[-1]
    believe(world, town, fact.id, fact.variant, None, 0.9, 1, "posted")
    found = reputation(world, town, champion)
    assert found.epithet.startswith("First of Heaven") and found.renown == pytest.approx(before + R.RANK_RENOWN["heaven"])


def test_a_list_you_have_heard_names_people_you_know_of(game):
    from systems.beliefs import known_people
    world, me, town = game.world, game.player.id, game.place.id
    champion = master(world, town, "test:champion", realm="peak")
    deed(world, champion, "tribulation", town, realm="peak")
    publish(world)
    assert champion not in known_people(world, me)
    fact = world.facts(predicate="published")[-1]
    believe(world, me, fact.id, fact.variant, town, 0.8, 2, "gossip")
    assert champion in known_people(world, me)


def test_an_old_save_gets_the_pavilion_and_publishes_in_spring(game):
    world = game.world
    assert R.pavilion(world) is None
    assert R.season_hook(world, 5) == [] and R.pavilion(world) is not None
    assert R.season_hook(world, 8)


def test_the_ranking_rules_catch_an_unknown_entrant(game):
    world, town = game.world, game.place.id
    deed(world, master(world, town, "test:m"), "tribulation", town, realm="first-rate")
    publish(world)
    pav = R.ensure_pavilion(world)
    stranger = master(world, town, "test:stranger")
    lists = dict(world.entity(pav).data["lists"])
    lists["heaven"] = lists["heaven"] + [stranger]
    world.update_data(pav, lists=lists, scores={**world.entity(pav).data["scores"], str(stranger): 0.0})
    assert any("no belief" in p for p in check_rankings(world))


def test_a_revision_is_quick(game):
    world, town = game.world, game.place.id
    folk = [master(world, town, f"test:q{i}") for i in range(200)]
    for i in range(2000):
        deed(world, folk[i % 200], "defeated", town, realm="second-rate", target=folk[(i + 1) % 200])
    world.known_facts(R.ensure_pavilion(world))
    start = time.process_time()
    R.revision_events(world, 4)
    assert time.process_time() - start < 0.05


def test_a_young_dragon_is_judged_by_the_age_believed_when_listed(game):
    from debug.invariants import check_rankings
    world, town = game.world, game.place.id
    youth = master(world, town, "test:youth", realm="second-rate", age=30)
    deed(world, youth, "tribulation", town, realm="second-rate", age=30)
    assert youth in publish(world)["lists"]["young"]
    world.set_time(world.time + R.YEAR)  # a year on, the Pavilion would think them 31; the list is last spring's
    world._rankings_checked = None
    assert check_rankings(world) == []
