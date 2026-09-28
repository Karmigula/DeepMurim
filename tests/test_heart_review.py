"""Phase 5e review: a hungry blade at the verdict, the mad calling you out, and the heart's reactions told."""

import pytest

import systems.blade_spirits as BS
import systems.daos as DA
import systems.demons as D
import systems.encounters as encounters
import systems.gear as gear
import systems.heart as HT
import systems.heart_world as HW
import systems.oaths as O
import systems.world_events as W
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.techniques import martial_arts
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
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "mortal", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:hreview:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def text(turn):
    return " | ".join(t for t, _ in turn.lines)


def at_the_verdict(game, monkeypatch, foe):
    import systems.duel as duel
    monkeypatch.setattr(duel, "accepts", lambda *a, **k: True)
    game.perform(Action("talk", foe))
    game.perform(Action("challenge"))
    game.combat.stage, game.combat.harm = "verdict", {"player": 0.0, "opponent": 95.0}
    return game._turn([])


def hungry_blade(game):
    world, me = game.world, game.player.id
    blade = gear.make_item(world, "weapon", "spear", 2, me, "bought")
    world.update_data(blade, spirit={"nature": "bloodthirsty", "bond": 0.0, "master": me, "known_by": [me]})
    commit(world, gear.wield_events(world, me, blade, game.place.id))
    return blade


def test_a_hungry_blade_in_a_troubled_hand_offers_no_mercy_and_says_why(game, monkeypatch):
    world, me = game.world, game.player.id
    hungry_blade(game)
    HT.write(world, me, steady=20.0)
    foe = someone(game, "foe")
    turn = at_the_verdict(game, monkeypatch, foe)
    assert [c.label for c in turn.choices] == ["Rob Someone foe", "Cripple Someone foe", "Kill Someone foe"]
    turn = game.perform(Action("verdict", "spare"))
    assert "A spirit-steel spear will not be sheathed dry." in text(turn) and game.combat is not None


def test_the_mad_come_at_you_with_wild_eyes(game, monkeypatch):
    world = game.world
    monkeypatch.setattr(HW, "MAD_CHANCE", 1.0)
    madman = founding.make_person(world, "test:hreview:mad", game.place.id, occupation="monk", age=50,
                                  realm="second-rate")
    world.update_data(madman, portrait={"hair": 0, "face": 0, "robe": 0})
    HT.write(world, madman, steady=10.0)
    commit(world, HW.season_events(world, madman, 0, None))
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 1.0)
    monkeypatch.setattr(encounters, "AVENGER_CHANCE", 1.0)
    turn = game.perform(Action("look"))
    assert "comes at you with wild eyes: their demons have them." in text(turn)
    assert "they have not forgotten you" not in text(turn)


def test_the_blade_line_begins_with_a_capital(game):
    blade = hungry_blade(game)
    page = [t for t, _ in game.perform(Action("heart")).lines]
    assert f"  {game.world.entity(blade).name[:1].upper()}{game.world.entity(blade).name[1:]} holds a bloodthirsty " \
           "spirit." in page


def test_an_epiphany_in_practice_is_told_as_it_comes(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(DA, "RESONANCE_CHANCE", 1.0)
    monkeypatch.setattr(W, "factor", lambda world, place, key, at=None: 2.0 if key == "practice" else 1.0)
    turn = game.perform(Action("practise", martial_arts(world, me)[0].technique.id))
    assert "Understanding opens like a door: the Dao of the Spear, glimpsed." in text(turn)


def test_vengeance_done_at_the_verdict_is_told(game, monkeypatch):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    D.add_demon(world, me, "grudge", foe, 2)
    commit(world, O.swear_events(world, me, "vengeance", foe, game.place.id))
    at_the_verdict(game, monkeypatch, foe)
    turn = game.perform(Action("verdict", "kill"))
    assert "An oath is kept: vengeance on Someone foe." in text(turn)


def test_a_ward_dead_of_illness_releases_the_oath_and_a_beast_breaks_no_abstinence(game):
    world, me, here = game.world, game.player.id, game.place.id
    friend, wolf = someone(game, "friend"), someone(game, "wolf", beast=True, occupation="grey wolf")
    for kind, whom in (("protection", friend), ("abstinence", None)):
        commit(world, O.swear_events(world, me, kind, whom, here))
    steady = HT.steady(world, me)
    commit(world, [Event("died", (friend, friend), here, {"cause": "illness", "world": True}),
                   Event("died", (me, wolf), here, {"cause": "killed"})])
    assert [o["kind"] for o in O.oaths(world, me)] == ["abstinence"] and HT.steady(world, me) == steady
    assert not world.facts("oath_broken", subject=me)
    assert BS.spirit_of(world, 0) is None
