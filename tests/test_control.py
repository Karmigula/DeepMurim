import pytest

import systems.alchemy as A
import systems.control as C
import systems.encounters as encounters
import systems.lives as lives
import systems.physic as PY
import systems.pills as P
import systems.recipe_trade as RT
from debug.invariants import check_alchemy_world
from engine.game import Game
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.law import SCHEMES
from world.body import WATCHES_PER_DAY
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


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal", "age": 30,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:control:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def a_master(game, tag="master"):
    return someone(game, tag, occupation="bandit", realm="first-rate", traits=["cunning", "greedy"])


def duel_end(world, a, b, place, **data):
    base = {"result": "won", "mode": "duel", "verdict": "spare", "by": "player", "silver": 0, "crippled": None,
            "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None, "purpose": None, "killed": False,
            "left_for_dead": False, "duel": None, "reason": "yielded"}
    return Event("duel_ended", (a, b), place, {**base, **data})


def control_pill(world, me):
    return A.make_pill(world, me, A.recipe_entity(world, "control"), 4, 0.6)


def test_the_control_recipe_is_secret_and_kept_only_by_unorthodox_halls(game):
    world = game.world
    assert "control" not in A.RECIPES
    assert A.best_match(A.combine(["black lotus", "black lotus", "corpse flower"]))[0] != "control"
    recipe = A.recipe_entity(world, "control")
    assert world.entity(recipe).data["effect"] == "control" and "Corpse-Worm Pill" in world.entity(recipe).name
    for fid in F.ensure_roster(world):
        kind = world.entity(fid).data["type"]
        assert ("control" in RT.secret_recipes(world, fid)) == (kind in F.DARK)
    assert "control" not in RT.guild_offers(world, game.player.id)


def test_the_bound_are_harmed_each_day_unfed_and_die_after_ninety(game):
    world = game.world
    master, victim = a_master(game), someone(game, "victim")
    C.bind(world, victim, master)
    world.update_data(master, is_player=True)  # a master who does not feed them
    world.set_time(world.time + C.MONTH + 3 * WATCHES_PER_DAY)
    C.starve(world, victim)
    assert len([i for i in load_body(world, victim).injuries if i.cause == "the worms of a control pill"]) == 3
    C.starve(world, victim)
    assert len([i for i in load_body(world, victim).injuries if i.cause == "the worms of a control pill"]) == 3
    assert C.death_events(world, victim) == []
    world.set_time(world.time + C.STARVE_DAYS * WATCHES_PER_DAY)
    [death] = C.death_events(world, victim)
    assert death.data["cause"] == "control_pill" and death.actors == (master, victim)


def test_an_npc_master_feeds_their_bound_and_a_dead_ones_bound_go_free(game):
    world = game.world
    master, victim = a_master(game), someone(game, "fed")
    C.bind(world, victim, master)
    world.set_time(world.time + 2 * lives.SEASON)
    commit(world, C.season_hook(world, 2))
    assert C.bound(world, victim)["fed_until"] > world.time and C.days_starved(world, victim) == 0
    killer = someone(game, "killer")
    commit(world, [Event("died", (killer, master), game.place.id, {"cause": "killed", "world": True})])
    assert C.bound(world, victim) is None and victim not in (world.get_meta("bound") or [])
    assert any(m.feeling == "grateful" for m in world.memories(victim, about=killer))


def test_a_grade_five_antidote_or_a_famous_doctor_frees_the_bound(game):
    world, me = game.world, game.player.id
    master = a_master(game)
    C.bind(world, me, master)
    pill = A.make_pill(world, me, A.recipe_entity(world, "metal_antidote"), 5, 0.9)
    commit(world, P.swallow_events(world, me, game.place.id, pill))
    assert C.bound(world, me) is None
    C.bind(world, me, master)
    assert "control" in PY.doctor_cures(world, me)
    doctor = someone(game, "doctor", doctor={"title": "the Test Doctor", "whim": "righteous", "home": [0, 0],
                                             "block": [0, 0]})
    commit(world, PY.doctor_events(world, me, doctor, "control", game.place.id))
    assert C.bound(world, me) is None


def test_a_transcendent_master_forces_the_worms_out(game, monkeypatch):
    world, me = game.world, game.player.id
    C.bind(world, me, a_master(game))
    assert "transcendent" in C.force_block(world, me)
    body = load_body(world, me)
    body.realm, body.energy_years, body.qi = 5, 70.0, 200.0
    save_body(world, me, body)
    assert C.force_block(world, me) is None
    monkeypatch.setattr(C, "FORCE_CHANCE", 1.0)
    commit(world, C.force_events(world, me, game.place.id))
    assert C.bound(world, me) is None


def test_the_player_spared_by_an_unorthodox_master_may_wake_bound(game, monkeypatch):
    world, me = game.world, game.player.id
    master = a_master(game)
    monkeypatch.setattr(C, "BIND_CHANCE", 1.0)
    commit(world, [duel_end(world, me, master, game.place.id, result="lost", by="opponent", mode="spar")])
    assert C.bound(world, me) is None  # never in a spar
    commit(world, [duel_end(world, me, master, game.place.id, result="lost", by="opponent")])
    assert C.bound(world, me)["master"] == master
    assert me not in (world.get_meta("bound") or [])  # the player is watched turn by turn, not listed


def test_a_months_service_feeds_the_pill(game):
    world, me = game.world, game.player.id
    master = a_master(game)
    C.bind(world, me, master)
    task = C.service(world, me)
    assert task["kind"] in C.SERVICES and C.service(world, me) == task
    assert not C.service_done(world, me)
    if task["kind"] == "steal":
        commit(world, [Event("hall_theft", (me,), game.place.id, {"faction": 1, "target": "hall", "caught": False,
                                                                  "loot": [], "season": 0})])
    elif task["kind"] == "beat":
        foe = someone(game, "foe")
        commit(world, [duel_end(world, me, foe, game.place.id)])
    else:
        from world.gen.materialize import ensure_town
        world.unrelate(me, "located_in")
        world.relate(me, ensure_town(world, *task["at"]), "located_in")
    assert C.service_done(world, me)
    before = C.bound(world, me)["fed_until"]
    commit(world, C.served_events(world, me, game.place.id))
    assert C.bound(world, me)["fed_until"] == before + C.MONTH
    assert not C.service_done(world, me)  # one service a month


def test_the_player_binds_a_beaten_foe_who_hates_them_and_must_feed_them(game):
    world, me, here = game.world, game.player.id, game.place.id
    foe = someone(game, "foe")
    assert "not beaten" in C.force_feed_block(world, me, foe, here)
    commit(world, [duel_end(world, me, foe, here)])
    assert "no control pill" in C.force_feed_block(world, me, foe, here)
    control_pill(world, me)
    assert C.force_feed_block(world, me, foe, here) is None
    commit(world, C.force_feed_events(world, me, foe, here))
    assert C.bound(world, foe)["master"] == me and foe in world.get_meta("bound")
    assert any(m.feeling == "hatred" for m in world.memories(foe, about=me))
    [fact] = world.facts(predicate="enslaved")
    assert fact.object == foe and "enslaved" in SCHEMES
    assert "no control pill" in C.feed_block(world, me, foe)
    control_pill(world, me)
    before = C.bound(world, foe)["fed_until"]
    commit(world, C.feed_events(world, me, foe, here))
    assert C.bound(world, foe)["fed_until"] == before + C.MONTH


def test_those_the_player_binds_may_find_a_cure(game, monkeypatch):
    world, me = game.world, game.player.id
    foe = someone(game, "seeker")
    C.bind(world, foe, me)
    monkeypatch.setattr(C, "CURE_SEEK", 1.0)
    commit(world, C.season_hook(world, 1))
    assert C.bound(world, foe) is None
    assert world.facts(predicate="freed")


def test_an_unorthodox_master_binds_someone_of_their_town_now_and_then(game, monkeypatch):
    world = game.world
    master = a_master(game, "world master")
    victim = someone(game, "townsman")
    monkeypatch.setattr(C, "WORLD_BIND", 1.0)
    events = C.world_events(world, master, 1, None)
    assert events and events[0].actors[0] == master
    commit(world, events)
    bound = events[0].actors[1]
    assert C.bound(world, bound)["master"] == master
    assert world.facts(predicate="enslaved")
    assert victim is not None


def test_another_is_freed_with_a_grade_five_antidote_and_is_saved(game):
    world, me, here = game.world, game.player.id, game.place.id
    master, victim = a_master(game), someone(game, "held")
    C.bind(world, victim, master)
    assert "grade-5" in C.free_block(world, me, victim, here)
    A.make_pill(world, me, A.recipe_entity(world, "metal_antidote"), 5, 0.9)
    commit(world, C.free_events(world, me, victim, here))
    assert C.bound(world, victim) is None
    assert any(m.feeling == "saved" for m in world.memories(victim, about=me))


def test_the_rules_hold_the_bound_to_living_people(game):
    world = game.world
    master, victim = a_master(game), someone(game, "rule")
    C.bind(world, victim, master)
    assert check_alchemy_world(world) == []
    world.update_data(master, dead=True)
    assert "bound" in " | ".join(check_alchemy_world(world))
