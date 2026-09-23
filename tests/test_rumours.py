import random
import time

import pytest

from engine.game import Game
from systems.beliefs import CONF_DECAY
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.rumours import (
    HOP_WATCHES, catch_up, heard_events, mutate, mutation_chance, news_about, no_news_events, pick_news, retell,
)
from world.events import commit
from world.gen.materialize import ensure_town

STORY = make_variant("killed", 101, 102, place="Rivermouth", realm="third-rate", art="Iron Tiger Fist",
                     form="fist", masked=True)


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("kind", "honest")):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {"occupation": "innkeeper", "traits": list(traits), "realm": "mortal",
                                                 "surname": surname, "given": given})
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def far_fact(game, weight, x=2, y=0, **data):
    origin = ensure_town(game.world, x, y, 0)
    with game.world.transaction():
        fid = game.world.add_fact(101, "killed", 102, place=origin, weight=weight,
                                  data={"variant": STORY, **data}, is_true=data.get("liar") is None)
    return fid, origin


def test_mutation_never_changes_who_did_what_to_whom():
    for seed in range(2000):
        story = mutate(STORY, random.Random(seed), hops=3)
        assert story["predicate"] == "killed" and story["target"] == 102
        assert story["actor"] in (101, None)
        assert story["count"] in (1, 2, 3)


def test_identity_is_never_retold_differently():
    story = make_variant("is", 7, 8)
    for seed in range(200):
        assert mutate(story, random.Random(seed), hops=5) == story


def test_a_masked_actor_is_only_forgotten_after_two_retellings():
    for seed in range(300):
        assert mutate(STORY, random.Random(seed), hops=1)["actor"] == 101


def test_retelling_is_seeded_and_honest_tellers_change_less():
    assert retell(STORY, 5, 9, 11, 1, 4) == retell(STORY, 5, 9, 11, 1, 4)
    assert mutation_chance(("honest",)) < mutation_chance(()) < mutation_chance(("cheerful",))

    def changed(traits):
        return sum(retell(STORY, n, 1, 11, 1, 3, traits) != STORY for n in range(400))
    assert changed(("honest", "secretive")) < changed(("cheerful", "cunning"))


def test_big_news_reaches_far_towns_after_travel_time(game):
    fid, origin = far_fact(game, 3.0)
    here, t0 = game.place.id, game.world.time
    assert catch_up(game.world, here, now=t0 + 2 * HOP_WATCHES - 1) == []
    assert catch_up(game.world, here, now=t0 + 2 * HOP_WATCHES) == [fid]
    [belief] = game.world.beliefs(here)
    assert (belief.hops, belief.channel, belief.source) == (3, "distance", origin)
    assert belief.confidence == pytest.approx(round(CONF_DECAY ** 3, 3))
    assert catch_up(game.world, here, now=t0 + 100) == []


def test_small_news_stays_local(game):
    far_fact(game, 1.0)
    assert catch_up(game.world, game.place.id, now=game.world.time + 1000) == []


def test_rejected_lies_do_not_travel(game):
    far_fact(game, 3.0, x=1, liar=1, spread=False)
    assert catch_up(game.world, game.place.id, now=game.world.time + 1000) == []


def test_catching_up_on_500_facts_is_quick(game):
    origin = ensure_town(game.world, 1, 0, 0)
    with game.world.transaction():
        for _ in range(500):
            game.world.add_fact(101, "killed", 102, place=origin, weight=3.0, data={"variant": STORY})
    start = time.perf_counter()
    added = catch_up(game.world, game.place.id, now=game.world.time + 100)
    elapsed = time.perf_counter() - start
    assert len(added) == 500
    assert elapsed < 0.05, f"catch_up took {elapsed * 1000:.0f} ms"


def test_news_prefers_the_biggest_story_about_others_and_is_not_repeated(game):
    teller = person(game, "Old Wu")
    small = record_fact(game.world, 101, "robbed", 102, place=game.place.id, variant=make_variant("robbed", 101, 102))
    big = record_fact(game.world, 101, "killed", 102, place=game.place.id, variant=make_variant("killed", 101, 102))
    mine = record_fact(game.world, game.player.id, "killed", 102, place=game.place.id, weight=9.0,
                       variant=make_variant("killed", game.player.id, 102))
    order = []
    while (found := pick_news(game.world, teller, game.player.id)) is not None:
        belief, fact = found
        [event] = heard_events(game.world, game.player.id, teller, game.place.id, belief, fact)
        commit(game.world, [event])
        order.append(fact.id)
        assert len(order) < 10
    assert order == [big, small, mine]
    heard = {b.fact_id: b for b in game.world.beliefs(game.player.id)}
    assert heard[big].source == teller and heard[big].channel == "told" and heard[big].hops == 3


def test_with_nothing_new_the_answer_is_nothing(game):
    teller = person(game, "Old Wu")
    assert pick_news(game.world, teller, game.player.id) is None
    [event] = no_news_events(game.player.id, teller, game.place.id, about="Wang Li")
    assert event.kind == "no_news" and event.data == {"about": "Wang Li"}


def test_news_about_someone_gives_the_surest_story(game):
    teller = person(game, "Old Wu")
    target = person(game, "Ma Bo", traits=("greedy", "proud"))
    record_fact(game.world, 101, "robbed", target, place=game.place.id, variant=make_variant("robbed", 101, target))
    _, fact = news_about(game.world, teller, target)
    assert fact.object == target
    assert news_about(game.world, teller, person(game, "No Body")) is None
