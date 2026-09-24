"""Findings from the phase 4b final review."""

import pytest

import systems.agendas as agendas
import systems.duties as duties
import systems.encounters as encounters
import systems.lives as lives
import systems.mortality as mortality
from app import App
from config import Config
from debug.invariants import check_people, check_world
from debug.replay import replay
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls, law, masks
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.kin import avengers_for
from world.gen.materialize import ensure_town, people_at


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
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


def local(game, path, town=None, **data):
    return founding.make_person(game.world, path, town or game.place.id, **{"occupation": "herbalist", "age": 30, **data})


def die(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    turn = game.perform(Action("meditate", 90))
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    return turn


def succeed(game, monkeypatch, heir, role="child"):
    agendas._pair(game.world, game.player.id, heir, role)
    old = game.player.id
    die(game, monkeypatch)
    return old, game.perform(Action("succeed", heir))


def test_an_inherited_debt_can_be_paid_off(game, monkeypatch):
    town = game.place.id
    for i in range(3):
        slain = local(game, f"test:slain:{i}")
        record_fact(game.world, game.player.id, "killed", slain, place=town, weight=3.0,
                    variant=make_variant("killed", game.player.id, slain, place=game.world.entity(town).name))
    son = local(game, "test:son", age=20)
    succeed(game, monkeypatch, son)
    owed = law.bounty(game.world, town, son)
    assert owed > 0
    constable = local(game, "test:constable", occupation="constable")
    game.world.update_data(son, silver=10000, arrest={"constable": constable, "bounty": owed,
                                                      "facts": [f for f, _ in law.crimes(game.world, town, son)]})
    game.perform(Action("arrest", "pay"))
    assert law.bounty(game.world, town, son) == 0


def test_the_family_grieves_the_player(game, monkeypatch):
    wife, son = local(game, "test:wife"), local(game, "test:son", age=20)
    agendas._pair(game.world, game.player.id, wife, "spouse")
    agendas._pair(game.world, game.player.id, son, "child")
    old = game.player.id
    die(game, monkeypatch)
    for kin in (wife, son):
        assert any(m.feeling == "grief" for m in game.world.memories(kin))
    assert wife not in avengers_for(game.world, old) and son not in avengers_for(game.world, old)


def test_an_heir_in_an_unvisited_town_wakes_among_people(game, monkeypatch):
    far = ensure_town(game.world, 6, 6, 0)
    son = local(game, "test:son", town=far, age=20)
    succeed(game, monkeypatch, son)
    assert game.place.id == far and game.world.entity(far).data.get("factions_ready")
    assert len(people_at(game.world, far, exclude=son)) > 0


def test_an_heir_who_held_a_post_leaves_it(game, monkeypatch):
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    elder = halls.staff_at(game.world, sect, seat, roles=("elder",))[0]
    game.world.update_data(elder, age=40)
    succeed(game, monkeypatch, elder, role="sworn_sibling")
    status = F.membership(game.world, elder, sect)[1]
    assert status["status"] != "member" or status.get("role") == "member"
    assert not [p for p in check_world(game.world) if "holds rank" in p]


def test_an_inherited_mask_is_a_new_face(game, monkeypatch):
    mask = game.world.add_entity("mask", "plain mask", {"persona": None})
    game.world.relate(game.player.id, mask, "owns")
    masks.persona_for(game.world, game.player.id, mask)
    son = local(game, "test:son", age=20)
    succeed(game, monkeypatch, son)
    assert game.world.entity(mask).data.get("persona") is None


def test_dying_with_an_open_duty_breaks_no_rule(game, monkeypatch):
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, seat, "located_in")
    game.world.relate(game.player.id, sect, "member_of", 0, {"role": "member", "hall": 0, "merit": 0, "status": "member",
                                                            "secret": False, "joined_at": 0, "judged": [], "stipend_at": 0})
    game._commit(duties.issue_events(game.world, game.player.id, sect, halls.keeper_at(game.world, sect, seat), seat))
    assert duties.open_duty(game.world, game.player.id) is not None
    game._commit(mortality.death_events(game.world, game.player.id, "age", None))  # die with the duty still open
    assert game.player.data.get("dying")
    assert not [p for p in check_world(game.world) if "duty" in p]


def test_the_lineage_page_names_only_known_forebears(game, monkeypatch):
    son = local(game, "test:son", age=20)
    succeed(game, monkeypatch, son)
    grandson = local(game, "test:grandson", age=20)
    succeed(game, monkeypatch, grandson)
    turn = game.perform(Action("lineage"))
    assert not [p for p in check_people(game, turn) if "never heard" in p]


def test_a_newcomer_session_can_be_replayed(tmp_path, monkeypatch):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs")
    app.start_new("First", world_seed=11)
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    app.submit("meditate season")
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    app.submit(str(next(i for i, c in enumerate(app.choices, 1) if c.action.verb == "newcomer")))
    for ch in "Second":
        app.handle_key(ch, ch)
    app.handle_key("return", "\r")
    app.handle_key("return", "\r")
    app.submit("look")
    session = app.session.path
    app.shutdown()
    result = replay(session, tmp_path / "replay")
    assert result.commands >= 1 and result.mismatches == []
