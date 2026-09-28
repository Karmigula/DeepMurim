import pytest

import systems.encounters as encounters
import systems.karma as K
from debug.invariants import check_karma
from engine.game import Game
from systems.creation import CreationChoice
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


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "lazy"], "realm": "second-rate", "age": 40}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:karma:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_a_fresh_ledger_is_empty_and_reading_it_writes_nothing(game):
    world, me = game.world, game.player.id
    assert K.karma_of(world, me) == {"merit": 0.0, "sin": 0.0, "threads": []}
    assert world.entity(me).data.get("karma") is None and K.balance(world, me) == 0.0


def test_an_npc_ledger_is_read_from_their_trade_and_traits(game):
    world = game.world
    bandit = someone(game, "bandit", occupation="bandit", traits=["cunning", "greedy"])
    monk = someone(game, "monk", occupation="monk", traits=["kind", "honest"])
    assert K.karma_of(world, bandit)["sin"] >= 20 and K.karma_of(world, monk)["merit"] >= 20
    assert K.karma_of(world, bandit) == K.karma_of(world, bandit) and world.entity(bandit).data.get("karma") is None


def test_every_deed_of_the_table_is_an_event_the_world_makes():
    for kind, row in K.DEEDS.items():
        assert kind in EFFECTS or len(LISTENERS.get(kind, [])) > 2, kind
        assert row["actor"] >= 0 and (row.get("merit", 0) > 0) != (row.get("sin", 0) > 0), kind


def test_a_duels_verdict_counts(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    for verdict in ("spare", "rob", "cripple"):
        K._verdict(world, Event("duel_ended", (me, foe), game.place.id,
                                {"result": "won", "by": "player", "verdict": verdict}), 0)
    assert K.karma_of(world, me)["merit"] == 5 and K.karma_of(world, me)["sin"] == 20


def kill(game, victim):
    commit(game.world, [Event("died", (game.player.id, victim), game.place.id, {"cause": "killed"})])


def test_killing_weighs_on_who_was_killed(game):
    world, me = game.world, game.player.id
    kill(game, someone(game, "fighter"))
    assert K.karma_of(world, me)["sin"] == K.KILL_SIN
    kill(game, someone(game, "mortal", realm="mortal"))
    assert K.karma_of(world, me)["sin"] == K.KILL_SIN + K.KILL_INNOCENT_SIN
    wicked = someone(game, "wicked")
    K.write(world, wicked, sin=200.0)
    kill(game, wicked)
    assert K.karma_of(world, me)["merit"] == K.KILL_WICKED_MERIT
    wolf = someone(game, "wolf", beast=True, occupation="grey wolf")
    kill(game, wolf)
    assert K.balance(world, me) == K.KILL_WICKED_MERIT - K.KILL_SIN - K.KILL_INNOCENT_SIN


def test_killing_one_who_yielded_is_the_heaviest(game):
    world, me, here = game.world, game.player.id, game.place.id
    import systems.duel as duel
    foe = someone(game, "yielded")
    [started] = commit(world, duel.start_events(world, me, foe, here, "duel"))
    d = duel.Duel.from_event(started, world.chronicle_entry(started))
    d.stage, d.harm = "verdict", {"player": 0.0, "opponent": 10.0}  # not broken: they yielded
    commit(world, duel.verdict_events(world, d, "kill"))
    assert K.karma_of(world, me)["sin"] == K.KILL_INNOCENT_SIN


def test_karma_is_told_in_words():
    assert [K.words(v) for v in (150, 50, 0, -50, -200)] == [
        "heaven smiles on you", "your merit outweighs your sins", "your merit and your sins stand even",
        "your sins outweigh your merit", "heaven's patience with you is thin"]


def test_check_karma_flags_a_malformed_ledger(game):
    world, me = game.world, game.player.id
    K.add(world, me, merit=5)
    assert check_karma(world) == []
    K.write(world, me, sin=-3.0)
    assert "karma" in " | ".join(check_karma(world))
