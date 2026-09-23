import pytest

import systems.encounters as encounters
import systems.leaving as leaving
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.purse import silver_of
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def member_of(game, kind, rank=0, secret=False):
    faction = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == kind)
    seat = halls.seat_of(game.world, faction)
    game.world.relate(game.player.id, faction, "member_of", rank, {
        "role": "member", "hall": 0, "sponsor": None, "merit": 0, "secret": secret, "joined_at": 0,
        "status": "member", "judged": [], "stipend_at": 0})
    return faction, seat


def go(game, town):
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")


def test_an_orthodox_sect_releases_you_for_a_price(game):
    sect, seat = member_of(game, "orthodox_sect", rank=1)
    go(game, seat)
    game.world.update_data(game.player.id, silver=200)
    game.perform(Action("talk", halls.keeper_at(game.world, sect, seat)))
    game.perform(Action("release", sect))
    assert F.membership(game.world, game.player.id, sect)[1]["status"] == "released"
    assert silver_of(game.world, game.player.id) == 100


def test_a_cult_never_releases_anyone(game):
    cult, seat = member_of(game, "demonic_cult")
    go(game, seat)
    game.perform(Action("talk", halls.keeper_at(game.world, cult, seat)))
    turn = game.perform(Action("faction_menu"))
    actions = {c.action.verb for c in turn.choices}
    assert "release" not in actions and "desert" in actions


def test_deserters_are_hated_and_hunted(game, monkeypatch):
    cult, seat = member_of(game, "demonic_cult")
    go(game, seat)
    keeper = halls.keeper_at(game.world, cult, seat)
    game.perform(Action("talk", keeper))
    game.perform(Action("desert", cult))
    assert F.membership(game.world, game.player.id, cult)[1]["status"] == "deserter"
    assert any(m.feeling == "wronged" for m in game.world.memories(keeper, about=game.player.id))
    assert keeper in leaving.town_hunters(game.world, game.player.id)
    monkeypatch.setattr(leaving, "HUNTER_CHANCE", 1.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    x, y = game.world.entity(cult).data["home"]
    events = encounters.road_encounter_events(game.world, game.player.id, game.world.entity(ensure_town(game.world, x, y, 0)))
    assert events and events[0].data["kind"] == "sect_hunter"
    assert not encounters.talk_succeeds(game.world, events[0].actors[1], game.player.id, "sect_hunter")


def test_a_release_by_final_duty(game):
    sect, seat = member_of(game, "orthodox_sect")
    go(game, seat)
    game.perform(Action("talk", halls.keeper_at(game.world, sect, seat)))
    game.perform(Action("release_duty", sect))
    duty = game.world.entity(game.player.data["duty"])
    assert duty.data["release"] is True
    go(game, duty.data["town"]) if duty.data.get("town") else None
    game.world.update_data(duty.id, kind="deliver", town=game.place.id)
    game.perform(Action("look"))
    assert F.membership(game.world, game.player.id, sect)[1]["status"] == "released"


def test_a_spy_is_found_out_when_word_reaches_the_first_faction(game):
    sect, seat = member_of(game, "orthodox_sect")
    cult, cult_seat = member_of(game, "demonic_cult", secret=True)
    go(game, seat)
    assert game.world.entity(game.player.id).data.get("summons") is None
    record_fact(game.world, game.player.id, "member_of", cult, place=seat,
                variant=make_variant("member_of", game.player.id, cult, place=game.world.entity(seat).name))
    turn = game.perform(Action("look"))
    assert F.membership(game.world, game.player.id, sect)[1]["status"] == "spy"
    assert any("spy" in text for text, _ in turn.lines)
