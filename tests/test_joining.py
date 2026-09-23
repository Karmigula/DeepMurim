import pytest

import systems.duel as duel
import systems.telling as telling
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls, membership
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.purse import silver_of
from systems.standing import believed_factions
from world.events import commit
from world.gen.materialize import ensure_town
from world.gen.region import region_spec


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def move_to(game, town):
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")


def town_with_hall(game, faction):
    for x in range(-3, 4):
        for y in range(-3, 4):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                town = ensure_town(game.world, x, y, i)
                halls.settle_town(game.world, town)
                if faction in halls.halls_here(game.world, town) and halls.keeper_at(game.world, faction, town):
                    return town
    raise AssertionError("no hall found")


def at_hall(game, kind, seat=True):
    faction = of_type(game.world, kind)
    town = halls.seat_of(game.world, faction) if seat else town_with_hall(game, faction)
    move_to(game, town)
    keeper = halls.keeper_at(game.world, faction, town)
    game.perform(Action("talk", keeper))
    return faction, town, keeper


def lines(turn):
    return [text for text, _ in turn.lines]


def test_the_alliance_takes_no_one_and_members_are_not_asked_twice(game):
    alliance = of_type(game.world, "alliance")
    assert membership.refusal(game.world, game.player.id, alliance, game.place.id).startswith("The Alliance")
    sect = of_type(game.world, "orthodox_sect")
    game.world.relate(game.player.id, sect, "member_of", 0, {"role": "member", "status": "member"})
    assert membership.refusal(game.world, game.player.id, sect, game.place.id) == "You are already one of them."


def test_a_sect_tests_you_with_a_spar_and_takes_you_in(game):
    sect, seat, keeper = at_hall(game, "orthodox_sect")
    turn = game.perform(Action("faction_menu"))
    assert Action("join", sect) in [c.action for c in turn.choices]
    game.perform(Action("join", sect))
    assert game.combat is not None and game.combat.mode == "test" and game.combat.purpose == {"join": sect}
    lines_ = game._finish_duel({"mode": "test", "result": "passed", "purpose": {"join": sect}})
    rank, data = F.membership(game.world, game.player.id, sect)
    assert rank == 0 and data["status"] == "member" and data["sponsor"] in halls.elders(game.world, sect).values()
    assert any("outer disciple" in text for text, _ in lines_)
    assert game.player.data.get("trial") is None
    assert sect in believed_factions(game.world, sect, game.player.id)


def test_failing_the_spar_ends_the_trial(game):
    sect, seat, keeper = at_hall(game, "orthodox_sect")
    game.perform(Action("join", sect))
    game._finish_duel({"mode": "test", "result": "failed", "purpose": {"join": sect}})
    assert F.membership(game.world, game.player.id, sect) is None and game.player.data.get("trial") is None


def test_a_dark_name_is_turned_away(game):
    sect, seat, keeper = at_hall(game, "orthodox_sect")
    victim = game.world.add_entity("person", "Hu Mei", {"realm": "mortal", "occupation": "innkeeper"})
    record_fact(game.world, game.player.id, "robbed", victim, place=seat,
                variant=make_variant("robbed", game.player.id, victim, place=game.world.entity(seat).name))
    assert "Your name is too dark for them." in lines(game.perform(Action("join", sect)))


def test_a_cult_demands_blood(game):
    cult, seat, keeper = at_hall(game, "demonic_cult")
    game.perform(Action("join", cult))
    trial = game.player.data["trial"]
    assert trial["kind"] == "blood" and trial["target"]
    target = trial["target"]
    move_to(game, game.world.targets(target, "located_in")[0])
    [sid] = commit(game.world, duel.start_events(game.world, game.player.id, target, game.place.id, "duel"))
    d = duel.Duel.from_event(sid, game.world.chronicle_entry(sid))
    d.stage, d.harm = "verdict", {"player": 0.0, "opponent": 90.0}
    game._commit(duel.verdict_events(game.world, d, "kill"))
    assert F.membership(game.world, game.player.id, cult)[1]["status"] == "member"


def test_the_beggars_want_three_rumours(game, monkeypatch):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 1.0)
    beggars, town, keeper = at_hall(game, "beggars", seat=False)
    game.perform(Action("join", beggars))
    assert game.player.data["trial"]["kind"] == "ears"
    for n in range(3):
        a = game.world.add_entity("person", f"Zhou Ta{n}", {"realm": "mortal"})
        fid = record_fact(game.world, a, "robbed", game.player.id, place=None, variant=make_variant("robbed", a, game.player.id))
        game.world.upsert_belief(game.player.id, fid, make_variant("robbed", a, game.player.id), None, 1.0, 0, "witness")
        key = next(b.variant_key for b in game.world.beliefs(game.player.id) if b.fact_id == fid)
        game.perform(Action("tell", (fid, key)))
    assert F.membership(game.world, game.player.id, beggars)[1]["status"] == "member"


def test_a_clan_sends_you_on_an_errand(game):
    clan, seat, keeper = at_hall(game, "martial_clan")
    game.perform(Action("join", clan))
    trial = game.player.data["trial"]
    assert trial["kind"] == "service" and trial["town"] != seat
    move_to(game, trial["town"])
    game.perform(Action("look"))
    assert F.membership(game.world, game.player.id, clan)[1]["status"] == "member"


def test_the_guild_takes_a_fee(game):
    guild, town, keeper = at_hall(game, "merchant_guild", seat=False)
    game.world.update_data(game.player.id, silver=60)
    game.perform(Action("join", guild))
    assert silver_of(game.world, game.player.id) == 10 and game.player.data["trial"]["kind"] == "escort"


def test_the_bureau_takes_only_proven_fighters(game):
    bureau, town, keeper = at_hall(game, "imperial", seat=False)
    assert "proven fighters" in lines(game.perform(Action("join", bureau)))[-1]
    game.world.update_data(game.player.id, realm="third-rate")
    game.perform(Action("talk", keeper))
    game.perform(Action("join", bureau))
    assert F.membership(game.world, game.player.id, bureau)[0] == 0


def test_a_second_sect_only_in_secret(game):
    first = of_type(game.world, "demonic_cult")
    game.world.relate(game.player.id, first, "member_of", 0, {"role": "member", "status": "member", "secret": False})
    sect, seat, keeper = at_hall(game, "orthodox_sect")
    choices = [c.action for c in game.perform(Action("faction_menu")).choices]
    assert Action("join_secret", sect) in choices
    assert "You already belong" in lines(game.perform(Action("join", sect)))[-1]
    game.perform(Action("join_secret", sect))
    game._finish_duel({"mode": "test", "result": "passed", "purpose": {"join": sect}})
    assert F.membership(game.world, game.player.id, sect)[1]["secret"] is True
    assert sect in believed_factions(game.world, sect, game.player.id)
    assert sect not in believed_factions(game.world, first, game.player.id)


def test_an_overdue_trial_fails(game):
    cult, seat, keeper = at_hall(game, "demonic_cult")
    game.perform(Action("join", cult))
    game.world.set_time(game.player.data["trial"]["deadline"] + 1)
    turn = game.perform(Action("look"))
    assert game.player.data.get("trial") is None
    assert any("failed" in text for text in lines(turn))
