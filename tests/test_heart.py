import pytest

import systems.encounters as encounters
import systems.heart as HT
from debug.invariants import check_heart
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.cultivation import breakthrough_events, meditate_events
from world.events import EFFECTS, LISTENERS, Event, commit


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


def someone(game, tag, traits):
    pid = game.world.add_entity("person", f"Someone {tag}", {"occupation": "tea seller", "traits": traits,
                                                              "realm": "mortal", "age": 40}, seed_path=f"test:heart:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_a_fresh_heart_is_steady_and_unaligned_and_reading_it_writes_nothing(game):
    world, me = game.world, game.player.id
    assert HT.heart_of(world, me) == {"steady": 60.0, "lean": 0.0, "demons": [], "daos": {}, "oaths": []}
    assert world.entity(me).data.get("heart") is None
    assert (HT.steady_words(60.0), HT.lean_words(0.0)) == ("steady", "unaligned")


def test_an_npc_heart_is_read_from_their_traits(game):
    world = game.world
    kind = someone(game, "kind", ["kind", "honest"])
    sly = someone(game, "sly", ["cunning", "greedy"])
    assert HT.lean(world, kind) >= 25 and HT.lean(world, sly) <= -25
    assert HT.heart_of(world, kind) == HT.heart_of(world, kind) and world.entity(kind).data.get("heart") is None
    temper = [HT.steady(world, someone(game, f"t{i}", ["hot-tempered", "proud"])) for i in range(6)]
    assert all(s <= 55 for s in temper)


def test_a_deed_moves_the_lean_and_steadies_or_shakes_a_leaning_heart(game):
    world, me = game.world, game.player.id
    HT.deed(world, me, 1, 2)
    assert HT.heart_of(world, me)["lean"] == 10.0 and HT.steady(world, me) == 60.0  # an unaligned heart: no doubt
    HT.write(world, me, lean=40.0)
    HT.deed(world, me, 1, 2)
    assert (HT.lean(world, me), HT.steady(world, me)) == (50.0, 62.0)
    HT.deed(world, me, -1, 3)
    assert (HT.lean(world, me), HT.steady(world, me)) == (35.0, 56.0)


def test_a_duels_verdict_is_a_deed(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe", ["proud"])
    for verdict, reason in (("spare", "yielded"), ("kill", "broken"), ("kill", "yielded"), ("rob", "broken")):
        HT._verdict(world, Event("duel_ended", (me, foe), game.place.id,
                                 {"result": "won", "by": "player", "verdict": verdict, "reason": reason}), 0)
    assert HT.lean(world, me) == 10.0 - 15.0 - 5.0


def test_every_deed_of_the_table_is_an_event_the_world_makes():
    for kind, row in HT.DEEDS.items():
        assert kind in EFFECTS or len(LISTENERS.get(kind, [])) > 1, kind
        assert row["actor"] >= 0 and row["lean"] in (1, -1) and 1 <= row["weight"] <= 3, kind


def test_meditation_brings_the_heart_back_to_rest(game):
    world, me = game.world, game.player.id
    HT.write(world, me, steady=40.0)
    commit(world, meditate_events(world, me, game.place.id, 14))
    assert HT.steady(world, me) == 42.0


def test_a_steady_heart_breaks_through_more_easily_and_deviates_less(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.bottleneck = True
    body.flags.append("sensed_qi")  # the way to Third-rate is open: the heart weighs in full
    save_body(world, me, body)
    HT.write(world, me, steady=100.0)
    high = breakthrough_events(world, me, game.place.id)[0].data["chance"]
    HT.write(world, me, steady=0.0)
    low = breakthrough_events(world, me, game.place.id)[0].data["chance"]
    assert high == pytest.approx(low + 0.2, abs=0.001)
    assert (HT.deviation_factor(world, me), HT.breakthrough_shift(world, me)) == (1.6, -0.12)
    HT.write(world, me, steady=60.0)
    assert (HT.deviation_factor(world, me), HT.breakthrough_shift(world, me)) == (1.0, 0.0)  # a heart at rest


def test_check_heart_flags_a_malformed_heart(game):
    world, me = game.world, game.player.id
    HT.write(world, me, steady=50.0)
    assert check_heart(world) == []
    HT.write(world, me, steady=140.0, lean=-300.0)
    assert "steadiness" in " | ".join(check_heart(world))
