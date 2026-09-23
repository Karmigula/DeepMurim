import pytest

import systems.duel as duel
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.combat_core import BROKEN, INTENTS
from systems.creation import CreationChoice
from systems.items import create_manual, manuals_of
from systems.purse import silver_of
from systems.techniques import create_technique, generate
from world.body import add_injury
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def npc(game, realm="mortal", traits=("curious", "honest"), occupation="tea seller", tag=""):
    data = {"occupation": occupation, "traits": list(traits), "realm": realm, "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Opponent {tag}", data, seed_path=f"test:{realm}:{occupation}:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def make_strong(game, realm=3, energy=20.0):
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years = realm, energy
    save_body(game.world, game.player.id, body)


def start(game, opponent, mode="duel"):
    events = duel.start_events(game.world, game.player.id, opponent, game.place.id, mode)
    [event_id] = commit(game.world, events)
    return duel.Duel.from_event(event_id, events[0])


def fight(game, d, intent="strike", limit=40):
    """Exchange until the duel ends or waits for a verdict; returns the last batch of events."""
    for _ in range(limit):
        events = duel.exchange_events(game.world, d, intent)
        commit(game.world, events)
        duel.apply_record(d, events[0].data)
        if len(events) > 1 or d.stage == "verdict":
            return events
    raise AssertionError("the fight never ended")


def test_npc_arts_are_seeded_once(game):
    swordsman = npc(game, occupation="wandering swordsman", tag="s")
    first = duel.ensure_npc_arts(game.world, swordsman)
    again = duel.ensure_npc_arts(game.world, swordsman)
    assert [a.technique.id for a in first] == [a.technique.id for a in again]
    assert first[0].form == "sword" and game.world.entity(swordsman).data["arts_ready"]


def test_fighter_reflects_body_and_art(game):
    art = duel.best_art(game.world, game.player.id)
    me = duel.fighter_for(game.world, game.player.id, art.technique.id)
    assert me.realm_mult == 1 and me.technique == art.name and me.form == art.form
    body = load_body(game.world, game.player.id)
    add_injury(body, "right arm", "cut", 2, game.world.time, "x")
    save_body(game.world, game.player.id, body)
    hurt = duel.fighter_for(game.world, game.player.id, art.technique.id)
    assert hurt.limb_injuries == (1 if art.form != "footwork" else 0)
    assert duel.fighter_for(game.world, game.player.id, None).form == "bare"


def test_exchange_is_decided_up_front_and_applied(game):
    d = start(game, npc(game, tag="a"))
    first = duel.exchange_events(game.world, d, "strike")
    assert first[0].data == duel.exchange_events(game.world, d, "strike")[0].data  # deterministic
    commit(game.world, first)
    data = first[0].data
    assert data["player_intent"] == "strike" and data["opponent_intent"] in INTENTS
    assert set(data["harm_after"]) == {"player", "opponent"}
    wounds_on_me = sum(1 for b in data["blows"] if b["target"] == "player" and b["wound"])
    assert len(load_body(game.world, game.player.id).injuries) == wounds_on_me


def test_beating_a_weaker_opponent_asks_for_a_verdict_and_robbing_takes_all(game):
    make_strong(game)
    victim = npc(game, tag="b")
    name, art = generate(rng_for(1, "m"), "martial", form="palm")
    item = create_manual(game.world, victim, create_technique(game.world, name, art), 0.7)
    before_mine, theirs = silver_of(game.world, game.player.id), silver_of(game.world, victim)
    d = start(game, victim)
    fight(game, d)
    assert d.stage == "verdict" and d.harm["opponent"] >= BROKEN
    [end] = duel.verdict_events(game.world, d, "rob")
    commit(game.world, [end])
    assert end.data["result"] == "won" and end.data["loot"] == [item]
    assert silver_of(game.world, game.player.id) == before_mine + theirs and silver_of(game.world, victim) == 0
    assert [m.item.id for m in manuals_of(game.world, game.player.id)] == [item]
    assert game.world.memories(victim, about=game.player.id)[-1].feeling == "humiliated"


def test_crippling_is_permanent_and_never_forgotten(game):
    make_strong(game)
    victim = npc(game, tag="c")
    d = start(game, victim)
    fight(game, d)
    [end] = duel.verdict_events(game.world, d, "cripple")
    commit(game.world, [end])
    assert any(i.permanent for i in load_body(game.world, victim).injuries)
    memory = game.world.memories(victim, about=game.player.id)[-1]
    assert memory.feeling == "hatred" and memory.indelible


def test_losing_to_a_bandit_costs_silver_but_never_life(game):
    bandit = npc(game, realm="first-rate", traits=("greedy", "cunning"), occupation="bandit", tag="d")
    before = silver_of(game.world, game.player.id)
    d = start(game, bandit)
    events = fight(game, d)
    end = events[-1]
    assert end.kind == "duel_ended" and end.data["result"] == "lost" and end.data["by"] == "opponent"
    assert end.data["verdict"] in ("rob", "cripple") and silver_of(game.world, game.player.id) <= before
    assert game.world.entity(game.player.id) is not None


def test_a_spar_is_short_and_gentle(game):
    friend = npc(game, tag="e")
    d = start(game, friend, mode="spar")
    events = fight(game, d)
    assert events[-1].data["result"] in ("spar_won", "spar_lost", "spar_even") and d.exchange <= 3
    for entry in game.world.chronicle_about(game.player.id, limit=10):
        for blow in entry.data.get("blows", []):
            assert blow["wound"] is None or blow["wound"][2] <= 2
    assert game.world.memories(friend, about=game.player.id)[-1].feeling == "sparred"


def test_fleeing(game, monkeypatch):
    d = start(game, npc(game, tag="f"))
    monkeypatch.setattr(duel, "flee_chance", lambda *a: 0.0)
    [failed] = duel.exchange_events(game.world, d, "flee")
    assert failed.data["fled"] is False and failed.data["blows"][0]["target"] == "player"
    monkeypatch.setattr(duel, "flee_chance", lambda *a: 1.0)
    escaped = duel.exchange_events(game.world, d, "flee")
    assert escaped[0].data["fled"] is True and escaped[-1].data["result"] == "fled"


def test_an_opponent_can_yield_and_a_win_upward_teaches(game, monkeypatch):
    elder = npc(game, realm="third-rate", tag="g")
    d = start(game, elder)
    monkeypatch.setattr(duel, "gives_up", lambda *a: "yield")
    events = duel.exchange_events(game.world, d, "guard")
    commit(game.world, events)
    duel.apply_record(d, events[0].data)
    assert events[0].data["gave_up"] == "yield" and d.stage == "verdict"
    [end] = duel.verdict_events(game.world, d, "spare")
    commit(game.world, [end])
    assert end.data["insight"] == 5.0 and end.data["life_and_death"]
    body = load_body(game.world, game.player.id)
    assert "life_and_death_insight" in body.flags and body.insight >= 5.0


def test_a_duel_in_progress_is_rebuilt_from_the_chronicle(game):
    d = start(game, npc(game, tag="h"))
    for intent in ("probe", "guard"):
        events = duel.exchange_events(game.world, d, intent)
        commit(game.world, events)
        duel.apply_record(d, events[0].data)
        if len(events) > 1:
            pytest.skip("the duel ended early for this seed")
    rebuilt = duel.active_duel(game.world, game.player.id)
    assert rebuilt is not None
    assert (rebuilt.exchange, rebuilt.harm, rebuilt.history, rebuilt.stage) == (d.exchange, d.harm, d.history, d.stage)
    commit(game.world, duel.yield_events(game.world, d))
    assert duel.active_duel(game.world, game.player.id) is None


def test_who_accepts_a_fight(game):
    proud = npc(game, traits=("proud", "loyal"), tag="i")
    assert duel.accepts(game.world, proud, game.player.id, "duel")
    assert duel.refusal_events(game.player.id, proud, game.place.id, "spar")[0].kind == "refused_duel"
