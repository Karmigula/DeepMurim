import pytest

from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls, ranks
from systems.creation import CreationChoice
from systems.items import manuals_of
from systems.membership import set_membership
from systems.purse import silver_of
from systems.techniques import known_arts


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def member_at_seat(game, rank=0, merit=0):
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, seat, "located_in")
    sponsor = halls.elders(game.world, sect)[0]
    game.world.relate(game.player.id, sect, "member_of", rank, {
        "role": "member", "hall": 0, "sponsor": sponsor, "merit": merit, "secret": False, "joined_at": 0,
        "status": "member", "judged": [], "stipend_at": game.world.time})
    return sect, seat, sponsor


def texts(turn):
    return [t for t, _ in turn.lines]


def test_promotion_needs_merit(game):
    sect, seat, sponsor = member_at_seat(game)
    assert ranks.promotion_block(game.world, game.player.id, sect) == "You need 30 merit; you have 0."
    set_membership(game.world, game.player.id, sect, merit=30)
    game.perform(Action("talk", sponsor))
    turn = game.perform(Action("faction_menu"))
    assert Action("promote", sect) in [c.action for c in turn.choices]
    turn = game.perform(Action("promote", sect))
    assert F.membership(game.world, game.player.id, sect)[0] == 1
    assert any("inner disciple" in t for t in texts(turn))


def test_the_high_ranks_need_a_realm_and_a_friendly_sponsor(game):
    sect, seat, sponsor = member_at_seat(game, rank=1, merit=90)
    assert "Third-rate" in ranks.promotion_block(game.world, game.player.id, sect)
    game.world.update_data(game.player.id, realm="second-rate")
    set_membership(game.world, game.player.id, sect, rank=2, merit=250)
    assert ranks.promotion_block(game.world, game.player.id, sect) == "Your sponsor does not favour you enough."
    game.world.update_data(game.player.id, silver=500)
    game.perform(Action("talk", sponsor))
    for _ in range(3):
        game.perform(Action("gift", sect))
    assert ranks.promotion_block(game.world, game.player.id, sect) is None
    set_membership(game.world, game.player.id, sect, rank=3)
    assert "Only a crisis opens the leader's seat" in ranks.promotion_block(game.world, game.player.id, sect)


def test_a_stipend_every_thirty_days(game):
    sect, seat, sponsor = member_at_seat(game, rank=2)
    assert ranks.stipend_due(game.world, game.player.id, sect) == 0
    game.world.set_time(game.world.time + ranks.STIPEND_DAYS * 4)
    assert ranks.stipend_due(game.world, game.player.id, sect) == 20
    before = silver_of(game.world, game.player.id)
    game.perform(Action("talk", halls.keeper_at(game.world, sect, seat)))
    game.perform(Action("stipend", sect))
    assert silver_of(game.world, game.player.id) == before + 20
    assert ranks.stipend_due(game.world, game.player.id, sect) == 0


def test_elders_teach_the_arts_your_rank_allows(game):
    sect, seat, sponsor = member_at_seat(game)
    arts = ranks.sect_arts(game.world, sect)
    assert len(arts) == 3 and ranks.sect_arts(game.world, sect) == arts
    assert ranks.teachable(game.world, game.player.id, sect) == arts[:1]
    game.perform(Action("talk", sponsor))
    game.perform(Action("learn_sect_art", sect))
    assert arts[0] in {a.technique.id for a in known_arts(game.world, game.player.id)}
    assert ranks.teachable(game.world, game.player.id, sect) == []


def test_the_library_lends_a_manual_to_inner_disciples(game):
    sect, seat, sponsor = member_at_seat(game, rank=1)
    game.perform(Action("talk", halls.keeper_at(game.world, sect, seat)))
    game.perform(Action("library", sect))
    assert any(m.technique.id in ranks.sect_arts(game.world, sect) for m in manuals_of(game.world, game.player.id))
