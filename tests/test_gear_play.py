import pytest

import systems.encounters as encounters
import systems.famous as FW
import systems.gear as gear
import systems.provenance as provenance
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.brief import scene_brief
from narrate.outcomes import SUMMARIES
from systems import factions as F
from systems import halls
from systems.beliefs import believe
from systems.creation import CreationChoice
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


def labels(turn):
    return [c.label for c in turn.all_choices]


def someone(game, tag, **data):
    base = {"occupation": "wandering swordsman", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:play:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def a_blade(game, grade=3, **extra):
    world, me = game.world, game.player.id
    item = gear.make_item(world, "weapon", "sword", grade, me, "found", name="the Test Moon Sword", **extra)
    commit(world, gear.wield_events(world, me, item, game.place.id))
    return item


def test_the_gear_page_lists_what_you_hold_and_lets_you_change_it(game):
    world, me = game.world, game.player.id
    spare = gear.make_item(world, "armour", "mail", 1, me, "bought")
    turn = game.perform(Action("inventory"))
    text = " | ".join(t for t, _ in turn.lines)
    assert "Your gear" in text and "Wielding:" in text
    assert f"Wear {world.entity(spare).name}" in labels(turn)
    game.perform(Action("wield", spare))
    assert gear.item_in(world, me, "armour").id == spare
    assert f"Put away {world.entity(spare).name}" in labels(game.perform(Action("inventory")))


def test_typed_words_reach_your_gear(game):
    world, me = game.world, game.player.id
    spare = gear.make_item(world, "armour", "robe", 0, me, "bought")
    turn = game.perform(Action("inventory"))
    assert parse("gear", turn.choices) == Action("inventory")
    assert parse("wear padded robe", turn.choices, turn.extra) == Action("wield", spare)
    assert parse("unwield", turn.choices) == Action("put_away", "weapon")


def test_the_smith_sells_and_buys(game):
    world, me = game.world, game.player.id
    world.update_data(me, silver=5000)
    turn = game.perform(Action("smith"))
    buys = [c for c in turn.all_choices if c.action.verb == "buy_gear"]
    assert buys
    game.perform(buys[0].action)
    [item] = gear.gear_items(world, me)
    assert f"Sell {item.name}" in " ".join(labels(game.perform(Action("smith"))))


def test_a_member_of_rank_draws_from_the_armoury_at_the_seat(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    label = f"Draw a weapon from the {world.entity(sect).name}'s armoury"
    assert label in labels(game.perform(Action("look")))
    game.perform(Action("draw_gear", (sect, "weapon")))
    assert gear.item_in(world, me, "weapon").data["armoury"] == sect


def test_the_beaten_can_be_stripped_of_their_weapon(game):
    world, me = game.world, game.player.id
    loser = someone(game, "loser")
    world.update_data(loser, gear={"weapon": 1, "armour": None, "form": "saber"})
    [ended] = commit(world, [Event("duel_ended", (me, loser), game.place.id, {
        "duel": None, "mode": "duel", "result": "won", "reason": "yielded", "verdict": "spare", "by": "player",
        "silver": 0, "crippled": None, "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None,
        "purpose": {}, "killed": False, "left_for_dead": False})])
    game._beaten = loser
    label = f"Take {world.entity(loser).name}'s weapon"
    assert label in labels(game.perform(Action("look")))
    game.perform(Action("take_gear", (loser, "weapon")))
    assert any(i.data["owners"][0]["person"] == loser for i in gear.gear_items(world, me))


def test_those_who_know_your_blade_speak_up(game, monkeypatch):
    monkeypatch.setattr(provenance, "COVET_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    item = a_blade(game, claimed_by=sect)
    variant = {"predicate": "blade_legend", "actor": item, "target": None, "count": 1, "place": None, "realm": None,
               "art": None, "form": None, "masked": False, "soft": False, "legend": "a test"}
    fact = world.add_fact(item, "blade_legend", None, place=game.place.id, weight=1.0, is_true=True,
                          data={"variant": variant})
    member = someone(game, "member")
    world.relate(member, sect, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                "secret": False})
    rival = someone(game, "rival", traits=["proud", "cunning"])
    for knower in (member, rival):
        believe(world, knower, fact, variant, None, 1.0, 1, "gossip")
    turn = game.perform(Action("look"))
    assert game.challenger == rival and game._stake == (rival, item)
    game.perform(Action("answer_challenge", False))
    choices = labels(game.perform(Action("look")))
    assert f"Refuse to give up {world.entity(item).name}" in choices
    game.perform(Action("answer_demand", False))
    assert world.facts(predicate="kept_gear", subject=me) and turn


def test_an_item_page_tells_only_what_you_know(game):
    world, me = game.world, game.player.id
    first = someone(game, "first")
    world.unrelate(first, "located_in")  # its first bearer, far away and never met
    giver = someone(game, "giver")
    item = gear.make_item(world, "weapon", "sword", 2, first, "carried")
    commit(world, gear.pass_events(world, first, giver, item, None, "given"))
    commit(world, gear.pass_events(world, giver, me, item, game.place.id, "given"))
    lines = " | ".join(t for t, _ in game.perform(Action("inspect", item)).lines)
    assert "carried by someone" in lines and world.entity(first).name not in lines  # a name never learned
    assert f"given to {world.entity(giver).name}" in lines and "Made by" not in lines


def test_inspecting_your_plain_weapon_gives_it_a_past(game):
    world, me = game.world, game.player.id
    if gear.weapon_of(world, me) is None:
        pytest.skip("a hand art")
    game.perform(Action("inspect", None))
    item = gear.item_in(world, me, "weapon")
    assert item is not None and item.data["owners"][0] == {"person": me, "since": item.data["made_at"], "how": "carried"}


def test_the_sheet_shows_your_weapon_and_what_it_does(game):
    world, me = game.world, game.player.id
    a_blade(game, grade=4)
    text = " | ".join(t for t, _ in sheet_lines(world, me))
    assert "the Test Moon Sword x" in text and "no armour" in text


def test_the_brief_names_a_famous_blade_you_know_by_its_tales(game):
    world, me = game.world, game.player.id
    bearer = someone(game, "bearer")
    item = FW.make_famous(world, "test", "saber", bearer, "made", "a test legend", game.place.id)
    [legend] = world.facts(predicate="blade_legend", subject=item)
    assert not any(world.entity(item).name in f for f in scene_brief(world, game.place.id, me, "t").facts)
    believe(world, me, legend.id, legend.data["variant"], None, 1.0, 1, "gossip")
    assert any(f"{world.entity(bearer).name} carries {world.entity(item).name}" in f
               for f in scene_brief(world, game.place.id, me, "t2").facts)


def test_help_names_the_gear_commands(game):
    assert any("gear | smith | wield" in t for t, _ in game.perform(Action("help")).lines)


def test_every_gear_deed_has_a_journal_line():
    for kind in ("gear_taken_up", "gear_put_away", "gear_passed", "gear_bought", "gear_sold", "armoury_drawn",
                 "armoury_returned", "gear_seized", "heirloom_returned", "blade_demanded"):
        assert kind in SUMMARIES, kind


def test_an_heir_takes_up_the_blade_and_armour_of_the_one_before(game):
    from systems import agendas
    from systems.succession import succession_events
    world, old = game.world, game.player.id
    heir = someone(game, "heir", age=20)
    agendas._pair(world, old, heir, "child")
    blade = a_blade(game)
    robe = gear.make_item(world, "armour", "robe", 1, old, "bought")
    commit(world, gear.wield_events(world, old, robe, game.place.id))
    commit(world, succession_events(world, old, heir))
    assert gear.item_in(world, heir, "weapon").id == blade and gear.item_in(world, heir, "armour").id == robe
    assert world.entity(blade).data["owners"][-1]["how"] == "inherited"
    assert world.targets(old, "wields") == [] and world.targets(old, "wears") == []
