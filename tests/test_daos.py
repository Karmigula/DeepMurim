from types import SimpleNamespace

import pytest

import systems.daos as DA
import systems.encounters as encounters
import systems.heart as HT
import systems.world_events as W
from debug.invariants import check_heart
from engine.game import Game
from systems import realms
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.cultivation import meditate_events, practise_events
from systems.duel import fighter_for
from systems.techniques import heart_method, known_arts, martial_arts
from world.events import Event, commit


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


def spear(game):
    return martial_arts(game.world, game.player.id)[0]  # the hunter's Hidden Crane Spear Art: spear, yang


def test_an_epiphany_opens_a_dao_by_comprehension_and_a_shaken_heart_sees_none(game):
    world, me, here = game.world, game.player.id, game.place.id
    [event] = DA.epiphany_events(world, me, here, "spear", "resonance")
    assert event.data["after"] == DA.gain(world, me) and GAIN_OK(DA.gain(world, me))
    commit(world, [event])
    assert DA.dao(world, me, "spear") == event.data["after"]
    HT.write(world, me, steady=10.0)
    assert DA.epiphany_events(world, me, here, "spear", "resonance") == []
    assert DA.epiphany_events(world, me, here, "neutral", "resonance") == []


def GAIN_OK(value):
    return DA.GAIN_BOUNDS[0] <= value <= DA.GAIN_BOUNDS[1]


def test_a_dao_completed_is_the_return_to_the_origin(game):
    world, me, here = game.world, game.player.id, game.place.id
    HT.write(world, me, daos={"sword": 0.99})
    commit(world, DA.epiphany_events(world, me, here, "sword", "fight"))
    body = load_body(world, me)
    assert DA.dao(world, me, "sword") == 1.0 and DA.ORIGIN in body.flags
    body.realm = 6
    assert realms.requirement(body, known_arts(world, me))[0]


def test_great_completion_opens_both_its_daos(game):
    world, me, here = game.world, game.player.id, game.place.id
    art = spear(game)
    DA._from_practice(world, Event("practised", (me,), here, {"technique_id": art.technique.id, "days": 7,
                                                             "mastered": True}), 1)
    assert set(DA.daos(world, me)) == {"spear", "yang"}


def test_practice_in_a_dao_resonance_brings_an_epiphany(game, monkeypatch):
    world, me, here = game.world, game.player.id, game.place.id
    monkeypatch.setattr(DA, "RESONANCE_CHANCE", 1.0)
    commit(world, practise_events(world, me, here, spear(game).technique.id))
    assert DA.daos(world, me) == {}
    monkeypatch.setattr(W, "factor", lambda world, place, key, at=None: 2.0 if key == "practice" else 1.0)
    commit(world, practise_events(world, me, here, spear(game).technique.id))
    assert "spear" in DA.daos(world, me)


def test_a_life_and_death_fight_won_and_a_bout_watched_bring_epiphanies_of_the_form(game, monkeypatch):
    world, me, here = game.world, game.player.id, game.place.id
    monkeypatch.setattr(DA, "DEATH_FIGHT_CHANCE", 1.0)
    monkeypatch.setattr(DA, "WATCH_CHANCE", 1.0)
    tech = spear(game).technique.id
    monkeypatch.setattr(world, "chronicle_entry", lambda i: SimpleNamespace(data={"technique": tech}))
    DA._from_fight(world, Event("duel_ended", (me, 99), here, {"result": "won", "by": "player", "duel": 5,
                                                               "life_and_death": True}), 1)
    assert "spear" in DA.daos(world, me)
    sword = world.add_entity("technique", "a sword art", {"form": "sword", "element": "metal"})
    occurrence = world.add_entity("sky", "a bout", {"data": {"arts": {"77": sword}}})
    DA._from_watching(world, Event("watched", (me, 77, 78), here, {"occurrence": occurrence, "winner": 77}), 2)
    assert "sword" in DA.daos(world, me)


def test_a_heart_leaning_hard_finds_its_element_in_meditation(game, monkeypatch):
    world, me, here = game.world, game.player.id, game.place.id
    monkeypatch.setattr(DA, "LEANING_CHANCE", 1.0)
    commit(world, meditate_events(world, me, here, 7))
    assert DA.daos(world, me) == {}
    HT.write(world, me, lean=-80.0)
    commit(world, meditate_events(world, me, here, 7))
    assert list(DA.daos(world, me)) == [heart_method(world, me).technique.data["element"]]


def test_a_dao_speeds_practice_and_sharpens_blows(game):
    world, me, here = game.world, game.player.id, game.place.id
    art = spear(game).technique.id
    plain = practise_events(world, me, here, art)[0].data
    plain_fighter = fighter_for(world, me, art)
    HT.write(world, me, daos={"yang": 0.5, "spear": 0.2})
    quick = practise_events(world, me, here, art)[0].data
    gained = lambda d: d["mastery_after"] - d["mastery_before"]
    assert gained(quick) == pytest.approx(gained(plain) * 1.5, rel=0.01)
    assert fighter_for(world, me, art).realm_mult == pytest.approx(plain_fighter.realm_mult * 1.02)


def test_check_heart_flags_a_dao_out_of_bounds(game):
    world, me = game.world, game.player.id
    HT.write(world, me, daos={"spear": 0.4})
    assert check_heart(world) == []
    HT.write(world, me, daos={"spear": 1.4, "moon": 0.1})
    assert "dao" in " | ".join(check_heart(world))
