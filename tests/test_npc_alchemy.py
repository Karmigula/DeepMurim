import pytest

import systems.encounters as encounters
import systems.guild as G
import systems.lives as lives
import systems.npc_alchemy as N
import systems.pills as P
from engine.game import Game
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=5000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal", "age": 30,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:npcalc:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def seasons(world, person, count):
    """Live this person's next seasons, one at a time, through the life clock."""
    start = lives.lived_to(world, person)
    world.set_time(max(world.time, (start + count) * lives.SEASON))
    lives.catch_up(world, person)


def test_an_alchemist_refines_each_season_and_keeps_a_count_not_things(game):
    world = game.world
    brewer = someone(game, "brewer", occupation="herbalist")
    before = world.last_rowid("entities")
    seasons(world, brewer, 4)
    pills = N.held(world.entity(brewer))
    grade = max(1, -(-G.rank_of(world, brewer) // 2))
    assert pills and all(g <= grade for g in pills)
    assert sum(pills.values()) >= 4 or sum(pills.values()) == N.MAX_HELD
    made = [world.entity(i) for i in range(before + 1, world.last_rowid("entities") + 1) if world.entity(i)]
    assert not any(e.kind == "pill" for e in made)  # no entities made


def test_an_alchemists_rank_rises_now_and_then(game, monkeypatch):
    world = game.world
    brewer = someone(game, "riser", occupation="herbalist")
    start = G.rank_of(world, brewer)
    monkeypatch.setattr(N, "RISE_CHANCE", 1.0)
    seasons(world, brewer, 2)
    assert world.entity(brewer).data["guild_rank"] == min(G.MAX_RANK, start + 2)


def test_a_fighter_with_silver_takes_pills_for_years_and_residue(game, monkeypatch):
    world = game.world
    fighter = someone(game, "fighter", realm="third-rate", silver=500)
    body = load_body(world, fighter)
    monkeypatch.setattr(N, "TAKE_CHANCE", 1.0)
    before = world.entity(fighter).data["body"]["energy_years"]
    seasons(world, fighter, 1)
    after = world.entity(fighter).data["body"]
    assert after["residue"] > 0 and silver_of(world, fighter) == 500 - N.BUY_PRICE
    assert after["energy_years"] >= before + N.PILL_YEARS or after["bottleneck"]
    assert body is not None


def test_a_mortal_takes_no_pills(game, monkeypatch):
    world = game.world
    mortal = someone(game, "mortal", silver=500)
    monkeypatch.setattr(N, "TAKE_CHANCE", 1.0)
    seasons(world, mortal, 2)
    assert silver_of(world, mortal) == 500


def test_a_body_full_of_residue_may_deviate(game, monkeypatch):
    world = game.world
    fighter = someone(game, "full", realm="third-rate", silver=500)
    body = dict(world.entity(fighter).data.get("body") or {})
    load_body(world, fighter)
    stored = dict(world.entity(fighter).data["body"])
    stored["residue"] = 90.0
    world.update_data(fighter, body=stored)
    monkeypatch.setattr(N, "TAKE_CHANCE", 1.0)
    monkeypatch.setattr(N, "DEVIATION_CHANCE", 1.0)
    monkeypatch.setattr(N, "DEADLY", 0.0)
    seasons(world, fighter, 1)
    assert any(i.cause == "a qi deviation" for i in load_body(world, fighter).injuries)
    assert body is not None


def test_a_robbed_alchemists_pills_become_things(game):
    world, me = game.world, game.player.id
    brewer = someone(game, "robbed", occupation="herbalist", pills={"2": 2, "1": 1})
    commit(world, [Event("duel_ended", (me, brewer), game.place.id, {
        "result": "won", "mode": "duel", "verdict": "rob", "by": "player", "silver": 0, "crippled": None,
        "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None, "purpose": None, "killed": False,
        "left_for_dead": False, "duel": None, "reason": "yielded"})])
    pills = P.pills_of(world, me)
    assert sorted(P.grade_of(p) for p in pills) == [1, 2, 2] and all(p.data["how"] == "taken" for p in pills)
    assert N.held(world.entity(brewer)) == {}


def test_an_alchemists_stall_sells_their_pills(game):
    world, me = game.world, game.player.id
    brewer = someone(game, "stall", occupation="herbalist", pills={"1": 1})
    assert N.stall_offers(world, brewer) == [1]
    assert N.stall_block(world, me, brewer, 1) is None
    commit(world, N.stall_events(world, me, brewer, 1, game.place.id))
    assert silver_of(world, me) == 5000 - N.stall_price(1) and len(P.pills_of(world, me)) == 1
    assert N.stall_offers(world, brewer) == []


def test_pills_pass_to_the_heir(game):
    from systems.agendas import _pair
    world = game.world
    brewer = someone(game, "old", occupation="herbalist", pills={"1": 3})
    child = someone(game, "child")
    _pair(world, brewer, child, "child")
    commit(world, [Event("died", (brewer, brewer), game.place.id, {"cause": "age", "world": True})])
    assert N.held(world.entity(child)) == {1: 3}


def test_the_life_clock_runs_the_alchemy_agenda(game):
    assert N.season_events in lives.AGENDAS
    from systems.agendas import apprentice_events
    assert lives.AGENDAS.index(apprentice_events) < lives.AGENDAS.index(N.season_events)


def test_the_rules_hold_an_npcs_pills_to_real_grades(game):
    from debug.invariants import check_alchemy_world
    world = game.world
    someone(game, "odd", occupation="herbalist", pills={"1": 2})
    assert check_alchemy_world(world) == []
    someone(game, "bad", occupation="herbalist", pills={"7": 1})
    assert "pills" in " | ".join(check_alchemy_world(world))
