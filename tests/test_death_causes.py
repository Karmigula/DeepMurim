import random
from types import SimpleNamespace

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.mortality as mortality
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice


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


def foe(game, path="test:foe", **data):
    return founding.make_person(game.world, path, game.place.id, **{"occupation": "hunter", "age": 30, **data})


def texts(turn):
    return [t for t, _ in turn.lines]


def lose(game, npc, reason="broken", purpose=None):
    game._start_duel(npc, "duel", purpose=purpose)
    d = game.combat
    event = (duel.yield_events(game.world, d)[0] if reason == "yielded"
             else duel._end_event(game.world, d, "lost", reason, random.Random(1), d.harm, 3))
    lines = game._commit([event])
    return lines + game._finish_duel(event.data)


def test_who_fights_to_kill(game):
    plain, cruel = foe(game, "test:plain", traits=["kind", "honest"]), foe(game, "test:cruel", traits=["cunning", "greedy"])
    duelist = SimpleNamespace(purpose={}, opponent=plain)
    assert mortality.kill_chance(game.world, duelist, False) == 0.0
    assert mortality.kill_chance(game.world, duelist, True) == 0.5
    assert mortality.kill_chance(game.world, SimpleNamespace(purpose={"hunter": True}, opponent=plain), False) == 0.3
    assert mortality.kill_chance(game.world, SimpleNamespace(purpose={}, opponent=cruel), False) == 0.1
    assert mortality.kill_chance(game.world, SimpleNamespace(purpose={"hunter": True}, opponent=cruel), True) == 0.5


def test_a_lost_fight_can_be_your_last(game, monkeypatch):
    monkeypatch.setitem(mortality.KILL_CHANCE, "grudge", 1.0)
    npc = foe(game)
    grudge = game.world.chronicle_about(game.player.id, limit=1)[0].id  # any moment the player took part in
    game.world.add_memory(npc, grudge, "hatred", 1.0, True)
    lines = lose(game, npc)
    dying = game.player.data["dying"]
    assert dying["cause"] == "killed" and dying["killer"] == npc
    assert len(game.world.facts(predicate="killed", subject=npc)) == 1
    assert any(t.startswith("Hero died at the hands of") for t, _ in lines)


def test_yielding_is_never_lethal_but_the_law_is(game, monkeypatch):
    for key in mortality.KILL_CHANCE:
        monkeypatch.setitem(mortality.KILL_CHANCE, key, 1.0)
    npc = foe(game, traits=["cunning", "greedy"])
    lose(game, npc, reason="yielded")
    assert not game.player.data.get("dying")
    constable = foe(game, "test:constable", occupation="constable")
    lose(game, constable, reason="yielded", purpose={"arrest": True, "capital": True})
    assert game.player.data["dying"]["cause"] == "executed"


def test_hunters_fight_to_kill(game):
    hunter = foe(game, "test:hunter")
    events = encounters.encounter_events(game.player.id, hunter, game.place.id, "bounty_hunter", 0)
    game._commit(events)
    game.encounter = encounters.encounter_state(events[-1])
    game.perform(Action("road", "fight"))
    assert game.combat is not None and game.combat.purpose == {"hunter": True}


def capital_arrest(game, bounty=200, path="test:officer"):
    constable = foe(game, path, occupation="constable")
    game.world.update_data(game.player.id, arrest={"constable": constable, "bounty": bounty, "facts": []})
    return constable


def test_a_capital_arrest_offers_only_trial_fight_or_flight(game):
    capital_arrest(game)
    verbs = [c.action.target for c in game.perform(Action("look")).choices]
    assert verbs == ["trial", "fight", "flee"]
    assert "cannot be paid" in texts(game.perform(Action("arrest", "pay")))[-1]


def test_a_trial_ends_in_death_or_two_years_in_prison(game, monkeypatch):
    capital_arrest(game)
    monkeypatch.setattr(mortality, "TRIAL_DEATH", 0.0)
    before = game.world.time
    game.perform(Action("arrest", "trial"))
    assert game.world.time >= before + mortality.PRISON_SEASONS * 360
    assert not game.player.data.get("arrest") and not game.player.data.get("dying")
    capital_arrest(game, path="test:officer2")
    monkeypatch.setattr(mortality, "TRIAL_DEATH", 1.0)
    game.perform(Action("arrest", "trial"))
    assert game.player.data["dying"]["cause"] == "executed"
