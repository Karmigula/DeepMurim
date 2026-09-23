import pytest

import systems.duties as duties
import systems.encounters as encounters
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event, commit
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def move_to(game, town):
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")


def member(game, kind="orthodox_sect"):
    faction = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == kind)
    seat = halls.seat_of(game.world, faction)
    move_to(game, seat)
    game.world.relate(game.player.id, faction, "member_of", 0, {
        "role": "member", "hall": 0, "sponsor": halls.elders(game.world, faction).get(0), "merit": 0, "secret": False,
        "joined_at": 0, "status": "member", "judged": [], "stipend_at": 0})
    return faction, seat, halls.keeper_at(game.world, faction, seat)


def issue(game, faction, keeper, kind):
    game._commit(duties.issue_events(game.world, game.player.id, faction, keeper, game.place.id, kind=kind))
    return duties.open_duty(game.world, game.player.id)


def merit(game, faction):
    return F.membership(game.world, game.player.id, faction)[1]["merit"]


def test_a_keeper_hands_out_duties_that_fit_the_faction(game):
    faction, seat, keeper = member(game)
    game.perform(Action("talk", keeper))
    turn = game.perform(Action("faction_menu"))
    assert Action("duty", faction) in [c.action for c in turn.choices]
    game.perform(Action("duty", faction))
    duty = duties.open_duty(game.world, game.player.id)
    assert duty.data["kind"] in ("hunt", "deliver", "gather", "guard") and duty.data["deadline"] > game.world.time


def test_a_delivery_is_done_on_arrival(game):
    faction, seat, keeper = member(game)
    duty = issue(game, faction, keeper, "deliver")
    move_to(game, duty.data["town"])
    game.perform(Action("look"))
    assert duties.open_duty(game.world, game.player.id) is None and merit(game, faction) == 10


def test_a_hunt_target_waits_on_the_road_and_beating_it_ends_the_duty(game):
    faction, seat, keeper = member(game)
    duty = issue(game, faction, keeper, "hunt")
    x, y = duty.data["region"]
    town = ensure_town(game.world, x, y, 0)
    events = encounters.road_encounter_events(game.world, game.player.id, game.world.entity(town))
    assert events[0].kind == "encounter" and events[0].actors[1] == duty.data["target"]
    ended = {"duel": None, "mode": "encounter", "result": "won", "reason": "broken", "verdict": "spare", "by": "player",
             "silver": 0, "crippled": None, "loot": [], "insight": 1.0, "life_and_death": False, "fragment": None,
             "purpose": {}}
    game._commit([Event("duel_ended", (game.player.id, duty.data["target"]), game.place.id, ended)])
    assert duties.open_duty(game.world, game.player.id) is None and merit(game, faction) == 10


def test_an_honest_debtor_pays_up(game):
    faction, seat, keeper = member(game, "merchant_guild")
    duty = issue(game, faction, keeper, "collect")
    debtor = duty.data["target"]
    game.world.update_data(debtor, traits=["honest", "lazy"])
    move_to(game, game.world.targets(debtor, "located_in")[0])
    game.perform(Action("talk", debtor))
    game.perform(Action("demand", duty.id))
    assert duties.open_duty(game.world, game.player.id) is None


def test_learning_about_the_target_completes_a_gathering(game):
    faction, seat, keeper = member(game, "beggars")
    duty = issue(game, faction, keeper, "gather")
    target = duty.data["target"]
    fid = record_fact(game.world, target, "robbed", 12345, place=None, variant=make_variant("robbed", target, 12345))
    game.world.upsert_belief(game.player.id, fid, make_variant("robbed", target, 12345), None, 0.6, 2, "told")
    game.perform(Action("look"))
    assert duties.open_duty(game.world, game.player.id) is None


def test_guarding_the_seat_by_resting_there(game, monkeypatch):
    monkeypatch.setattr(duties, "RAID_CHANCE", 0.0)
    faction, seat, keeper = member(game)
    duty = issue(game, faction, keeper, "guard")
    for _ in range(duty.data["days"] // 7 + 1):
        game.perform(Action("rest", 7))
    assert duties.open_duty(game.world, game.player.id) is None


def test_a_raid_on_the_seat_starts_a_fight(game, monkeypatch):
    monkeypatch.setattr(duties, "RAID_CHANCE", 1.0)
    faction, seat, keeper = member(game)
    issue(game, faction, keeper, "guard")
    game.perform(Action("rest", 1))  # one day: the watch is not yet over when the raiders come
    assert game.combat is not None and game.combat.purpose.get("raid")


def test_an_overdue_duty_fails_once(game):
    faction, seat, keeper = member(game)
    duty = issue(game, faction, keeper, "deliver")
    game.world.set_time(duty.data["deadline"] + 1)
    game.perform(Action("look"))
    game.perform(Action("look"))
    failures = [e for e in game.world.chronicle_about(game.player.id, limit=20) if e.kind == "duty_failed"]
    assert len(failures) == 1 and duties.open_duty(game.world, game.player.id) is None


def test_a_dead_target_fails_the_duty(game):
    faction, seat, keeper = member(game, "merchant_guild")
    duty = issue(game, faction, keeper, "collect")
    stranger = game.world.add_entity("person", "Other Killer", {"realm": "mortal"})
    commit(game.world, [Event("died", (stranger, duty.data["target"]), game.place.id, {"cause": "killed"})])
    game.perform(Action("look"))
    assert duties.open_duty(game.world, game.player.id) is None
    assert game.world.entity(duty.id).data["status"] == "failed"


def test_abandoning_a_duty_costs_merit(game):
    faction, seat, keeper = member(game)
    game.world.relate(game.player.id, faction, "member_of", 0, {**F.membership(game.world, game.player.id, faction)[1], "merit": 25})
    issue(game, faction, keeper, "deliver")
    game.perform(Action("talk", keeper))
    game.perform(Action("abandon_duty", faction))
    assert merit(game, faction) == 15
