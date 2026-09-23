"""Findings from the phase 3a final review."""

import time

import pytest

import systems.encounters as encounters
import systems.masks as masks
import systems.telling as telling
from debug.invariants import check_people, check_world
from engine.game import Action, Game
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture
def unseen(monkeypatch):
    for name in ("ART_CHANCE", "VOICE_CHANCE", "CHANGE_CHANCE"):
        monkeypatch.setattr(masks, name, 0.0)


def person(game, name, traits=("kind", "honest")):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": "innkeeper", "traits": list(traits), "realm": "mortal", "surname": surname, "given": given,
        "gender": "man", "age": 40, "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def masked(game):
    with game.world.transaction():
        mask = game.world.add_entity("mask", "plain mask", {"persona": None})
        game.world.relate(game.player.id, mask, "owns")
    game.perform(Action("wear_mask"))
    return game.world.entity(game.player.id).data["masked"]


def lie_about(game, listener, victim, other):
    game.perform(Action("talk", listener))
    game.perform(Action("invent_menu"))
    game.perform(Action("invent_pred", "robbed"))
    game.perform(Action("invent_subject", victim))
    return game.perform(Action("invent_object", other))


def test_a_new_roamer_never_borrows_a_living_one(game):
    region = region_of(game.world, game.place.id)
    first = encounters.make_roamer(game.world, region, "bandit", 0, 0.1)
    encounters.make_roamer(game.world, region, "beast", 1, 0.1)
    encounters.make_roamer(game.world, region, "wanderer", 2, 0.1)
    commit(game.world, [Event("died", (game.player.id, first), game.place.id, {"cause": "killed"})])
    assert encounters._free_roamer_slot(game.world, region) == 3


def test_a_lie_told_behind_a_mask_is_blamed_on_the_mask(game, monkeypatch, unseen):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 1.0)
    listener, victim, other = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    for someone in (victim, other):
        game.perform(Action("talk", someone))
        game.perform(Action("farewell"))
    persona = masked(game)
    lie_about(game, listener, victim, other)
    [exposed] = game.world.facts(predicate="lied_about")
    assert exposed.subject == persona and exposed.variant["actor"] == persona
    told_by = [b.source for b in game.world.beliefs(listener) if b.fact_id == game.world.facts(is_true=False)[0].id]
    assert told_by == [persona]


def test_a_lie_is_exposed_only_once_however_long_ago(game, monkeypatch):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 1.0)
    listener, victim, other = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    for someone in (victim, other):
        game.perform(Action("talk", someone))
        game.perform(Action("farewell"))
    lie_about(game, listener, victim, other)
    assert len(game.world.facts(predicate="lied_about")) == 1
    with game.world.transaction():
        for _ in range(450):
            game.world.append_chronicle("rested", (game.player.id,), game.place.id, {}, 1.0)
    assert telling.exposure_events(game.world, game.player.id, game.place.id) == []


def test_the_narrator_is_not_told_a_masked_stranger_is_an_old_friend(game, unseen):
    friend = person(game, "Old Wu")
    for _ in range(3):
        game.perform(Action("talk", friend))
        game.perform(Action("farewell"))
    masked(game)
    game.perform(Action("talk", friend))
    brief = game.last_briefs[0]
    assert brief.other.toward_player == "stranger"
    assert not any("spoken with" in fact or "first met" in fact for fact in brief.facts)


def test_a_long_life_stays_quick(game):
    """30,000 chronicle entries, 3,000 memories, 500 facts known in 28 places: a turn stays quick."""
    world, me = game.world, game.player.id
    npc = person(game, "Old Wu")
    with world.transaction():
        for _ in range(30000):
            world.append_chronicle("rested", (me,), game.place.id, {}, 1.0)
        for _ in range(3000):
            eid = world.append_chronicle("asked", (me, npc), game.place.id, {"topic": "x"}, 1.0)
            world.add_memory(npc, eid, "engaged", 0.1)
        for n in range(500):
            story = {"predicate": "defeated", "actor": me, "target": npc}
            fid = world.add_fact(me, "defeated", npc, place=game.place.id, data={"variant": story})
            for knower in [game.place.id, *range(10001, 10028)]:
                world.upsert_belief(knower, fid, {**story, "n": n}, None, 0.8, 1, "gossip")
    game.perform(Action("talk", npc))
    check_world(world)
    start = time.perf_counter()
    turn = game.perform(Action("ask", "work"))
    check_world(world)
    check_people(game, turn)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.15, f"one question and its checks took {elapsed * 1000:.0f} ms"
