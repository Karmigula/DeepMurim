import pytest

import systems.armoury as A
import systems.gear as gear
import systems.smithy as SM
import systems.spoils as SP
from debug.invariants import check_gear
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def someone(game, tag, **data):
    base = {"occupation": "wandering swordsman", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:arms:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def the_sect(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    return sect, halls.seat_of(world, sect)


def join(world, me, sect, rank, role="member"):
    world.relate(me, sect, "member_of", rank, {"role": role, "hall": None, "merit": 0, "status": "member",
                                               "secret": False})


# --- the smith --------------------------------------------------------------------------------------------

def test_a_stall_stocks_by_the_season_capped_by_the_towns_size(game):
    world, town = game.world, game.place.id
    offers = SM.stock(world, town)
    assert 4 <= len(offers) <= 9
    assert all(o["grade"] <= SM.cap(world, town) for o in offers)
    assert SM.stock(world, town) == offers  # the same all season


def test_buying_makes_an_item_by_the_towns_smith_and_selling_pays_half(game):
    world, me, town = game.world, game.player.id, game.place.id
    world.update_data(me, silver=5000)
    offer = SM.stock(world, town)[0]
    cost = SM.price(world, town, offer["slot"], offer["grade"])
    assert SM.buy_block(world, me, town, offer["key"]) is None
    commit(world, SM.buy_events(world, me, town, offer["key"]))
    [item] = gear.gear_items(world, me)
    assert item.data["grade"] == offer["grade"] and item.data["maker"] == SM.smith_name(world, town)
    assert item.data["owners"][-1]["how"] == "bought" and silver_of(world, me) == 5000 - cost
    assert offer["key"] not in {o["key"] for o in SM.stock(world, town)}
    back = SM.sell_price(world, town, item.id)
    assert back == max(1, int(cost * SM.SELL_SHARE))
    commit(world, SM.sell_events(world, me, town, item.id))
    assert gear.gear_items(world, me) == [] and silver_of(world, me) == 5000 - cost + back
    assert check_gear(world) == []


def test_the_poor_cannot_buy(game):
    world, me, town = game.world, game.player.id, game.place.id
    world.update_data(me, silver=0)
    assert SM.buy_block(world, me, town, SM.stock(world, town)[0]["key"]) == "You cannot pay for it."


def test_a_famous_blade_sells_only_to_a_citys_merchant(game):
    world, me, town = game.world, game.player.id, game.place.id
    blade = gear.make_item(world, "weapon", "sword", 3, me, "found", famous=True)
    if world.entity(town).data.get("kind") != "city":
        assert SM.sell_block(world, me, town, blade) is not None
    else:
        pytest.skip("the start is a city")


# --- the armoury ------------------------------------------------------------------------------------------

def test_rank_draws_its_grade_from_the_armoury_and_returns_it(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    assert A.draw_block(world, me, sect, "weapon", seat) is not None  # not a member
    join(world, me, sect, 2)
    assert A.draw_block(world, me, sect, "weapon", game.place.id if game.place.id != seat else -1) is not None
    before = A.table(world, sect)
    commit(world, A.draw_events(world, me, sect, "weapon", seat))
    item = gear.item_in(world, me, "weapon")
    assert item.data["grade"] == 1 and item.data["armoury"] == sect and item.data["owners"][-1]["how"] == "drawn"
    assert A.table(world, sect)[1] == before[1] - 1
    assert A.draw_block(world, me, sect, "weapon", seat) == "You already hold one from the armoury."
    commit(world, A.return_events(world, me, item.id, seat))
    assert A.table(world, sect) == before and gear.item_in(world, me, "weapon") is None
    assert check_gear(world) == []


def test_an_elder_draws_a_treasure_once(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(world, me, sect, 4, role="elder")
    commit(world, A.draw_events(world, me, sect, "weapon", seat))
    assert gear.item_in(world, me, "weapon").data["grade"] == A.ELDER_GRADE
    assert A.allowed(world, me, sect) == A.RANK_GRADE[3]


def test_leaving_with_the_armourys_blade_is_theft(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(world, me, sect, 1)
    commit(world, A.draw_events(world, me, sect, "weapon", seat))
    item = gear.item_in(world, me, "weapon")
    from systems.membership import left_events
    commit(world, left_events(world, me, sect, seat, "deserter"))
    assert world.entity(item.id).data["claimed_by"] == sect
    assert world.facts(predicate="stole", subject=me)


def test_the_armoury_restocks_a_season_at_a_time(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(world, me, sect, 1)
    commit(world, A.draw_events(world, me, sect, "weapon", seat))
    low = min(A.seed_of(world, sect))
    assert A.table(world, sect)[low] == A.seed_of(world, sect)[low] - 1
    A.season_hook(world, 1)
    assert A.table(world, sect)[low] == A.seed_of(world, sect)[low]


# --- the fallen -------------------------------------------------------------------------------------------

def test_taking_from_the_beaten_is_remembered_and_robbery_if_lawful(game):
    world, me = game.world, game.player.id
    loser = someone(game, "loser", traits=["proud", "honest"])
    world.update_data(loser, gear={"weapon": 1, "armour": 0, "form": "saber"})
    assert SP.take_block(world, me, loser, "weapon", game.place.id) == "You have not beaten them."
    commit(world, [Event("duel_ended", (me, loser), game.place.id, {
        "duel": None, "mode": "duel", "result": "won", "reason": "yielded", "verdict": "spare", "by": "player",
        "silver": 0, "crippled": None, "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None,
        "purpose": {}, "killed": False, "left_for_dead": False})])
    assert SP.take_block(world, me, loser, "weapon", game.place.id) is None
    commit(world, SP.take_events(world, me, loser, "weapon", game.place.id))
    item = gear.item_in(world, me, "weapon") or gear.gear_items(world, me)[0]
    assert item.data["owners"][0]["person"] == loser and item.data["owners"][-1]["how"] == "taken"
    assert any(m.feeling == "hatred" and m.indelible for m in world.memories(loser, about=me))
    assert world.facts(predicate="robbed", subject=me)


def test_taking_from_a_bandit_is_no_crime(game):
    world, me = game.world, game.player.id
    bandit = someone(game, "bandit", occupation="bandit")
    world.update_data(bandit, dead=True)
    assert SP.take_block(world, me, bandit, "weapon", game.place.id) is None
    commit(world, SP.take_events(world, me, bandit, "weapon", game.place.id))
    assert not world.facts(predicate="robbed", subject=me)


def test_a_greedy_victor_may_take_your_weapon(game, monkeypatch):
    monkeypatch.setattr(SP, "NPC_TAKES", 1.0)
    world, me = game.world, game.player.id
    if gear.weapon_of(world, me) is None:
        pytest.skip("a hand art: nothing to take")
    victor = someone(game, "victor", traits=["greedy", "cunning"], occupation="bandit")
    commit(world, [Event("duel_ended", (me, victor), game.place.id, {
        "duel": None, "mode": "duel", "result": "lost", "reason": "broken", "verdict": "rob", "by": "opponent",
        "silver": 0, "crippled": None, "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None,
        "purpose": {}, "killed": False, "left_for_dead": False})])
    assert gear.weapon_of(world, me) is None
    assert gear.item_in(world, victor, "weapon") is None and gear.gear_items(world, victor)
