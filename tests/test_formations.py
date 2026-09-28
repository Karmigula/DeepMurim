import pytest

import systems.encounters as encounters
import systems.formations as FM
from debug.invariants import check_crafts
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
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


def test_every_pattern_has_a_use_flags_and_a_difficulty():
    for key, row in FM.PATTERNS.items():
        assert row["use"] in ("defence", "battle", "ward") and row["flags"] >= 1 and 1 <= row["difficulty"] <= 3, key
        assert (row["days"] == 0) == (row["use"] == "battle"), key


def test_a_manual_studied_teaches_its_pattern_and_is_kept(game):
    world, me = game.world, game.player.id
    manual = FM.make_manual(world, me, "confusion", "bought")
    assert FM.study_block(world, me, manual) is None
    commit(world, FM.study_events(world, me, manual, game.place.id))
    assert FM.mastery(world, me, "confusion") == FM.FIRST_MASTERY and manual in world.targets(me, "owns")
    assert "already" in FM.study_block(world, me, manual)
    assert FM.manual_price("killing") == FM.MANUAL_PRICE * 9


def test_flags_are_one_item_that_counts_them(game):
    world, me = game.world, game.player.id
    FM.add_flags(world, me, 5)
    FM.add_flags(world, me, 3)
    assert FM.flags_of(world, me) == 8 and len([i for i in world.targets(me, "owns")
                                                 if world.entity(i).kind == "flags"]) == 1
    FM.spend_flags(world, me, 8)
    assert FM.flags_of(world, me) == 0 and check_crafts(world) == []


def test_a_battle_array_is_laid_until_the_next_dawn_and_teaches_the_hand(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    FM.learn(world, me, "binding")
    FM.add_flags(world, me, 10)
    assert FM.lay_block(world, me, "binding", town) is None
    monkeypatch.setattr(FM, "BOUNDS", (1.0, 1.0))
    commit(world, FM.lay_events(world, me, "binding", town))
    [laid] = FM.laid(world, town)
    assert laid["pattern"] == "binding" and laid["owner"] == me and laid["until"] % WATCHES_PER_DAY == 0
    assert laid["strength"] == pytest.approx(0.5 + FM.FIRST_MASTERY / 2)
    assert FM.flags_of(world, me) == 10 - FM.PATTERNS["binding"]["flags"]
    assert FM.mastery(world, me, "binding") == pytest.approx(FM.FIRST_MASTERY + FM.MASTERY_STEP)
    assert world.entity(me).data["formation_xp"] == 3
    world.set_time(laid["until"])
    assert FM.laid(world, town) == [] and FM.strength(world, town, "binding") == 0.0


def test_a_failed_laying_spends_the_flags(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    FM.learn(world, me, "seclusion")
    FM.add_flags(world, me, 3)
    monkeypatch.setattr(FM, "BOUNDS", (0.0, 0.0))
    commit(world, FM.lay_events(world, me, "seclusion", town))
    assert FM.laid(world, town) == [] and FM.flags_of(world, me) == 0


def test_a_harder_pattern_is_harder_to_lay_and_a_master_lays_it_better(game):
    world, me = game.world, game.player.id
    FM.learn(world, me, "confusion")
    FM.learn(world, me, "killing")
    assert FM.chance(world, me, "killing") < FM.chance(world, me, "confusion")
    before = FM.chance(world, me, "killing")
    world.update_data(me, formation_xp=90)
    assert FM.level(world, me) == 3 and FM.chance(world, me, "killing") == pytest.approx(before + 0.15)


def test_a_sects_defences_are_laid_at_the_seat_of_ones_own_sect(game):
    world, me, town = game.world, game.player.id, game.place.id
    FM.learn(world, me, "veiled_garden")
    FM.learn(world, me, "heavenly_gate")
    FM.add_flags(world, me, 20)
    assert "own sect" in FM.lay_block(world, me, "veiled_garden", town)
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.relate(me, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 0, "status": "member",
                                            "secret": False})
    assert FM.lay_block(world, me, "veiled_garden", seat) is None
    assert "your own sect's gate" in FM.lay_block(world, me, "heavenly_gate", seat)


def test_a_formation_master_reads_an_ancient_array_better_and_it_may_teach_them(game, monkeypatch):
    world, me = game.world, game.player.id
    world.update_data(me, formation_xp=40)
    assert FM.trial_bonus(world, me) == pytest.approx(2 * FM.TRIAL_LEVEL)
    monkeypatch.setattr(FM, "TRIAL_TEACHES", 1.0)
    realm = world.add_entity("secret_realm", "a test realm", {"floors": [[{"kind": "trial", "state": "untouched",
                                                                            "contents": {"trial": "formation"}}]]})
    FM._array_teaches(world, Event("trial_attempted", (me,), realm, {"realm": realm, "floor": 1, "chamber": 0,
                                                                      "trial": "formation", "passed": True}), 0)
    assert len(FM.known(world, me)) == 1


def test_the_rules_hold_a_laid_formation_to_a_pattern_and_a_person(game):
    world, town = game.world, game.place.id
    world.update_data(town, formations=[{"pattern": "nothing", "owner": 999999, "until": 10 ** 9, "strength": 2}])
    assert "malformed" in " | ".join(check_crafts(world))
