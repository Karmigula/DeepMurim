import time

import pytest

import systems.encounters as encounters
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from engine.realm_page import realms_lines
from engine.sheet import sheet_lines
from narrate.outcomes import SUMMARIES
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(G, "WANDERER_CHANCE", 0.0)
    monkeypatch.setattr(G, "near_sects", lambda world, gate: [])


def texts(turn):
    return [t for t, _ in turn.lines]


def heralded(game, realm, here=True):
    """An opening of this realm, foretold; its gate in the player's town, or far away."""
    world = game.world
    town = game.place.id if here else world.entity(realm).data["gate"]
    world.update_data(realm, gate=town)
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    return W.index(world)[-1][W.ID]


def test_the_page_shows_only_the_realms_you_know(game):
    world, me = game.world, game.player.id
    far, other = SR.ensure_realms(world)[:2]
    lines = " ".join(texts(game.perform(Action("realms")))).lower()
    assert not any(world.entity(r).name.lower() in lines for r in (far, other))
    occurrence = heralded(game, far, here=False)
    gate = world.entity(far).data["gate"]
    variant = make_variant("phenomenon", gate, None, place=place_name(world, gate))
    variant.update(kind="realm_opening", stage="foretold", reading=None)
    fact = record_fact(world, gate, "phenomenon", None, place=gate, variant=variant, spread=False,
                       extra={"occurrence": occurrence, "until": world.time + 40 * 4})
    believe(world, me, fact, variant, None, 0.7, 2, "gossip")
    lines = " ".join(texts(game.perform(Action("realms")))).lower()
    assert world.entity(far).name.lower() in lines and "heralded" in lines and world.entity(other).name.lower() not in lines


def test_f5_opens_the_realms_page(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Watcher", world_seed=5)
    app.handle_key("f5", "")
    assert any("Secret realms" in t for t, _ in app.last_turn.lines)


def test_the_gate_town_hears_the_heralds_once_and_sees_the_gate_open(game):
    world = game.world
    realm = SR.ensure_realms(world)[0]
    occurrence = heralded(game, realm)
    assert any("Heralds" in t and world.entity(realm).name in t for t in texts(game.perform(Action("look"))))
    world.set_time(world.time + 1)
    assert not any("Heralds" in t for t in texts(game.perform(Action("look"))))
    world.set_time(world.entity(occurrence).data["active"][0])
    turn = game.perform(Action("look"))
    assert any("stands open" in t for t in texts(turn))
    facts = " ".join(f for b in game.last_briefs if b.kind == "scene" for f in b.facts)
    assert "stands open here" in facts and realm in game.player.data.get("realms_seen", [])


def test_the_sheet_shows_your_tokens_and_whether_you_are_sealed(game):
    world, me = game.world, game.player.id
    realm = SR.ensure_realms(world)[0]
    token = world.add_entity("treasure", "a jade token", {"kind": "token", "realm": realm, "used": False, "value": 120})
    world.relate(me, token, "owns")
    text = " ".join(t for t, _ in sheet_lines(world, me))
    assert "Jade tokens" in text and world.entity(realm).name in text and "Sealed" not in text
    world.update_data(me, sealed_in={"realm": realm, "season": 10})
    assert f"Sealed in {world.entity(realm).name}" in " ".join(t for t, _ in sheet_lines(world, me))


def test_every_realm_event_you_take_part_in_has_a_journal_line():
    for kind in ("realm_entered", "sneak_caught", "realm_left", "chamber_looted", "guardian_slipped", "guardian_slain",
                 "trial_attempted", "inheritance_claimed", "inheritance_failed", "remains_taken", "pass_asked",
                 "band_routed", "band_joined", "sealed_season", "exit_searched", "unsealed"):
        assert kind in SUMMARIES, kind


def test_a_save_reloaded_inside_a_realm_resumes_the_delve(game):
    world, me, town = game.world, game.player.id, game.place.id
    realm = SR.ensure_realms(world)[0]
    world.update_data(realm, gate=town, rule={"kind": "open", "value": None})
    commit(world, sky.start_events(world, "realm_opening", town, world.time, SR.opening_data(realm)))
    world.set_time(world.entity(W.index(world)[-1][W.ID]).data["active"][0])
    game.perform(Action("look"))
    game.perform(Action("enter_realm", realm))
    path = world.path
    game.close()
    again = Game.load(path)
    try:
        turn = again.look()
        assert "floor 1 of" in texts(turn)[0] and Action("delve_rest") in [c.action for c in turn.all_choices]
    finally:
        again.close()


def test_help_names_the_realms(game):
    assert any("realms (F5)" in t for t in texts(game.perform(Action("help"))))


def test_the_realms_page_is_quick(game):
    world, me = game.world, game.player.id
    for realm in SR.ensure_realms(world):
        world.update_data(me, realms_seen=game.player.data.get("realms_seen", []) + [realm])
    for i in range(200):
        variant = make_variant("delved", me, None, place="somewhere")
        variant["realm_name"] = world.entity(SR.realms(world)[i % 3]).name
        fact = record_fact(world, me, "delved", None, place=game.place.id, variant=variant, spread=False)
        believe(world, me, fact, variant, None, 0.7, 2, "gossip")
    realms_lines(world, me)
    start = time.process_time()
    realms_lines(world, me)
    assert time.process_time() - start < 0.03
