import pytest

import systems.encounters as encounters
import systems.politics as politics
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm_rivals(monkeypatch):
    """The rival is a grudge challenger; keep random call-outs from pre-empting a summons in these tests."""
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)


def joined_sect(game):
    """Join the first orthodox sect through its real joining event (so the rival is picked)."""
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, seat, "located_in")
    from systems.membership import joined_events
    game._commit(joined_events(game.world, game.player.id, halls.keeper_at(game.world, sect, seat), sect, seat, False))
    return sect, seat


def innocent_robbed(game, seat):
    victim = next(p for p in halls.people_at(game.world, seat) if not F.memberships(game.world, p.id)
                  and not p.data.get("is_player"))
    return record_fact(game.world, game.player.id, "robbed", victim.id, place=seat,
                       variant=make_variant("robbed", game.player.id, victim.id, place=game.world.entity(seat).name))


def test_joining_a_great_sect_gives_you_a_proud_rival(game):
    sect, seat = joined_sect(game)
    rival = politics.rival_of(game.world, game.player.id, sect)
    assert rival in halls.staff_at(game.world, sect, seat, roles=("disciple",))
    assert "proud" in game.world.entity(rival).data["traits"]
    assert any(m.feeling == "annoyed" for m in game.world.memories(rival, about=game.player.id))


def test_breaking_a_taboo_brings_a_summons(game):
    sect, seat = joined_sect(game)
    fact = innocent_robbed(game, seat)
    assert [f.id for f in politics.breaches(game.world, game.player.id, sect)] == [fact]
    turn = game.perform(Action("look"))
    assert game.player.data["summons"]["fact"] == fact
    assert [c.action.target for c in turn.choices] == ["accept", "combat", "deny", "refuse"]
    assert game.perform(Action("rest", 1)).lines[-1][1] == "system"  # nothing else until you answer


def test_deeds_before_joining_are_not_judged(game):
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    innocent_robbed(game, seat)
    game.world.set_time(game.world.time + 1)
    joined_sect(game)
    assert politics.breaches(game.world, game.player.id, sect) == []


def test_accepting_punishment_costs_merit_and_can_demote(game):
    sect, seat = joined_sect(game)
    game.world.relate(game.player.id, sect, "member_of", 1, {**F.membership(game.world, game.player.id, sect)[1], "merit": 10})
    innocent_robbed(game, seat)
    game.perform(Action("look"))
    game.perform(Action("judgement", "accept"))
    rank, data = F.membership(game.world, game.player.id, sect)
    assert (rank, data["merit"]) == (0, 0) and game.player.data.get("summons") is None


def test_refusing_judgement_means_expulsion(game):
    sect, seat = joined_sect(game)
    innocent_robbed(game, seat)
    game.perform(Action("look"))
    game.perform(Action("judgement", "refuse"))
    assert F.membership(game.world, game.player.id, sect)[1]["status"] == "expelled"


def test_trial_by_combat_against_the_accuser(game):
    sect, seat = joined_sect(game)
    innocent_robbed(game, seat)
    game.perform(Action("look"))
    game.perform(Action("judgement", "combat"))
    assert game.combat is not None and game.combat.opponent == game.player.data["summons"]["accuser"]
    game._finish_duel({"mode": "duel", "result": "won", "purpose": {"judgement": game.player.data["summons"]["fact"]}})
    assert game.player.data.get("summons") is None and F.membership(game.world, game.player.id, sect)[1]["status"] == "member"


def test_a_framing_can_be_denied_and_the_rival_exposed(game, monkeypatch):
    monkeypatch.setattr(politics, "FRAME_CHANCE", 1.0)
    monkeypatch.setattr(politics, "deny_chance", lambda *args, **kwargs: 1.0)
    sect, seat = joined_sect(game)
    rival = politics.rival_of(game.world, game.player.id, sect)
    game._commit([Event("duty_issued", (game.player.id, halls.keeper_at(game.world, sect, seat)), seat, {
        "faction": sect, "holder": game.player.id, "kind": "deliver", "target": None, "town": seat, "region": None,
        "difficulty": 1, "status": "open", "issued_at": game.world.time, "days": 0, "guarded": 0, "release": False,
        "n": 0, "deadline": game.world.time + 40})])
    game.perform(Action("look"))  # the delivery is done here, and the rival strikes
    lie = game.world.facts(is_true=False)[0]
    assert lie.data["liar"] == rival
    game.perform(Action("look"))
    assert game.player.data["summons"]["fact"] == lie.id
    turn = game.perform(Action("judgement", "deny"))
    assert any(game.world.entity(rival).name in text for text, _ in turn.lines)
    sponsor = F.membership(game.world, game.player.id, sect)[1]["sponsor"]
    game.perform(Action("talk", sponsor))
    game.perform(Action("expose", sect))
    assert F.membership(game.world, rival, sect)[1]["status"] == "expelled"
    assert F.membership(game.world, game.player.id, sect)[1]["merit"] >= 20


def test_a_summons_survives_a_reload(game, tmp_path):
    sect, seat = joined_sect(game)
    innocent_robbed(game, seat)
    game.perform(Action("look"))
    path = game.world.path
    game.close()
    again = Game.load(path)
    turn = again.look()
    assert [c.action.verb for c in turn.choices] == ["judgement"] * 4
    again.close()
