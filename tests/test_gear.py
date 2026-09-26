import random

import pytest

import systems.duel as duel
import systems.gear as gear
from debug.invariants import check_gear
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.combat_core import technique_power
from systems.creation import CreationChoice
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def sect_staff(world, role):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    return sect, seat, halls.staff_at(world, sect, seat, roles=(role,))


def commoner(game, tag="c", occupation="tea seller"):
    data = {"occupation": occupation, "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", data, seed_path=f"test:gear:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def my_art_form(game):
    return duel.best_art(game.world, game.player.id).form


def test_a_blade_strengthens_the_arts_of_its_form(game):
    world, me = game.world, game.player.id
    sword = gear.make_item(world, "weapon", "sword", 3, me, "bought")
    commit(world, gear.wield_events(world, me, sword, game.place.id))
    assert gear.weapon_mult(world, me, "sword") == gear.POWER[3]
    assert gear.weapon_mult(world, me, "saber") == pytest.approx(gear.POWER[3] * gear.NEAR_MULT)
    assert gear.weapon_mult(world, me, "spear") == gear.UNARMED
    assert gear.weapon_mult(world, me, "palm") == 1.0  # a hand art needs nothing
    world.update_data(sword, broken=True)
    assert gear.weapon_mult(world, me, "sword") == gear.UNARMED


def test_an_npc_carries_a_seeded_grade_and_no_item(game):
    world = game.world
    before = len(world.entities("gear"))
    sect, seat, elders = sect_staff(world, "elder")
    _, _, [keeper] = sect_staff(world, "keeper")
    assert gear.seeded(world, elders[0]) == {"weapon": 2, "armour": 1}  # an elder: spirit steel, fine armour
    assert gear.seeded(world, keeper)["weapon"] >= 1
    someone = commoner(game)
    assert gear.seeded(world, someone) == {"weapon": 0, "armour": None}  # an iron blade, and cloth
    assert gear.weapon_mult(world, someone, "saber") == 1.0  # their blade is for their art
    assert len(world.entities("gear")) == before  # reading gear makes nothing


def test_what_an_npc_carries_is_made_real_once(game):
    world = game.world
    sect, seat, elders = sect_staff(world, "elder")
    form = gear.best_weapon_form(world, elders[0])
    made = gear.materialize(world, elders[0], "weapon")
    if form is None:
        assert made is None  # a hand art: nothing to make
        return
    item = world.entity(made)
    assert item.data["grade"] == 2 and item.data["form"] == form
    assert item.data["owners"] == [{"person": elders[0], "since": world.time, "how": "carried"}]
    assert gear.materialize(world, elders[0], "weapon") == made
    assert gear.carried(world, elders[0])["weapon"] is None and gear.weapon_of(world, elders[0])["item"] == made
    assert check_gear(world) == []


def test_the_hero_starts_with_a_plain_weapon_for_their_art(game):
    world, me = game.world, game.player.id
    form = my_art_form(game)
    if form in gear.WEAPON_FORMS:
        assert gear.weapon_of(world, me) == {"grade": 0, "form": form, "item": None, "broken": False}
        assert gear.weapon_mult(world, me, form) == 1.0
    else:
        assert gear.weapon_of(world, me) is None


def test_a_fighter_strikes_harder_with_a_better_blade(game):
    world, me = game.world, game.player.id
    art = duel.best_art(world, me)
    if art.form not in gear.WEAPON_FORMS:
        pytest.skip("a hand art")
    plain = technique_power(duel.fighter_for(world, me, art.technique.id))
    blade = gear.make_item(world, "weapon", art.form, 4, me, "found")
    commit(world, gear.wield_events(world, me, blade, game.place.id))
    assert technique_power(duel.fighter_for(world, me, art.technique.id)) == pytest.approx(plain * gear.POWER[4])


def test_armour_softens_the_wound_not_the_fight(game):
    bare = duel._blow("player", 40.0, "saber", random.Random(1), False)
    armed = duel._blow("player", 40.0, "saber", random.Random(1), False, armour=0.3)
    assert bare["damage"] == armed["damage"] == 40.0
    assert armed["wound"][2] < bare["wound"][2]


def test_the_lesser_blade_may_break(game, monkeypatch):
    monkeypatch.setattr(gear, "BREAK_CHANCE", 1.0)
    world, me = game.world, game.player.id
    art = duel.best_art(world, me)
    if art.form not in gear.WEAPON_FORMS:
        pytest.skip("a hand art")
    mine = gear.make_item(world, "weapon", art.form, 0, me, "bought")
    commit(world, gear.wield_events(world, me, mine, game.place.id))
    foe = commoner(game, "foe", occupation="bandit")
    world.update_data(foe, gear={"weapon": 3, "armour": None})
    [started] = commit(world, duel.start_events(world, me, foe, game.place.id, "duel"))
    d = duel.Duel.from_event(started, world.chronicle_entry(started))
    events = duel.exchange_events(world, d, "strike")
    if events[0].data.get("broke") is None:
        pytest.skip("they did not meet blade to blade")  # the foe fought with a hand art
    commit(world, events)
    assert events[0].data["broke"] == "player" and world.entity(mine).data["broken"]
    assert gear.weapon_mult(world, me, art.form) == gear.UNARMED


def test_gear_changes_hands_and_remembers(game):
    world, me = game.world, game.player.id
    someone = commoner(game, "giver")
    world.update_data(someone, gear={"weapon": 1, "armour": None, "form": "saber"})
    item = gear.materialize(world, someone, "weapon")
    commit(world, gear.pass_events(world, someone, me, item, game.place.id, "taken"))
    history = world.entity(item).data["owners"]
    assert [h["person"] for h in history] == [someone, me] and history[-1]["how"] == "taken"
    assert world.targets(someone, "wields") == [] and gear.weapon_of(world, someone) is None
    commit(world, gear.wield_events(world, me, item, game.place.id))
    assert gear.item_in(world, me, "weapon").id == item and check_gear(world) == []
    other = gear.make_item(world, "weapon", "spear", 0, me, "bought")
    world.relate(me, other, "wields")
    assert any("at once" in p for p in check_gear(world))
