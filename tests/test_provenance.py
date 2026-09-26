import pytest

import systems.gear as gear
import systems.provenance as P
from debug.invariants import check_gear
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.standing import standing
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def the_sect(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    return sect, halls.seat_of(world, sect)


def someone(game, tag, **data):
    base = {"occupation": "wandering swordsman", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:prov:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def a_treasure_bearer(game, tag="bearer"):
    world = game.world
    bearer = someone(game, tag)
    world.update_data(bearer, gear={"weapon": 3, "armour": None, "form": "sword"})
    return bearer


def slay(game, killer, victim):
    [died] = commit(game.world, [Event("died", (killer, victim), game.place.id, {"cause": "killed"})])
    return died


def test_a_notable_kill_is_remembered_by_the_weapon_that_did_it(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    died = slay(game, me, elder)
    [deed] = gear.carried(world, me)["deeds"]  # a plain carried blade keeps it until it is made real
    assert deed == {"event": died, "kind": "killed", "whom": elder, "weight": P.KILL_WEIGHT}
    item = gear.materialize(world, me, "weapon")
    assert world.entity(item).data["deeds"] == [deed] and "deeds" not in gear.carried(world, me)


def test_a_nobody_killed_is_no_deed(game):
    world, me = game.world, game.player.id
    slay(game, me, someone(game, "nobody"))
    assert not gear.carried(world, me).get("deeds")


def test_a_treasure_blade_is_made_real_by_its_deed_and_told_of(game):
    world = game.world
    sect, seat = the_sect(world)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    bearer = a_treasure_bearer(game)
    died = slay(game, bearer, leader)
    item = gear.item_in(world, bearer, "weapon")
    assert item is not None and item.data["deeds"][0]["weight"] == P.LEADER_WEIGHT
    [fact] = world.facts(predicate="wielded_in", subject=item.id)
    assert fact.object == leader and fact.source_event == died
    assert check_gear(world) == []


def test_a_weapon_keeps_its_twelve_weightiest_deeds(game):
    world, me = game.world, game.player.id
    item = gear.make_item(world, "weapon", "spear", 0, me, "bought")
    commit(world, gear.wield_events(world, me, item, game.place.id))
    first = world.last_rowid("chronicle")
    for n in range(14):
        P.remember(world, me, {"event": first, "kind": "killed", "whom": None, "weight": float(n)}, game.place.id)
    weights = [d["weight"] for d in world.entity(item).data["deeds"]]
    assert weights == [float(n) for n in range(13, 1, -1)]


def test_the_tales_let_you_know_a_blade_on_sight(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    bearer = a_treasure_bearer(game)
    slay(game, bearer, leader)
    item = gear.item_in(world, bearer, "weapon")
    assert P.known_blades(world, me, [bearer]) == []
    [fact] = world.facts(predicate="wielded_in", subject=item.id)
    believe(world, me, fact.id, fact.data["variant"], None, 0.8, 1, "gossip")
    assert P.known_blades(world, me, [bearer]) == [(bearer, item.id)]


def test_those_who_know_a_blade_react_to_its_bearer(game, monkeypatch):
    monkeypatch.setattr(P, "COVET_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    item = gear.make_item(world, "weapon", "sword", 3, me, "found", claimed_by=sect)
    commit(world, gear.wield_events(world, me, item, game.place.id))
    died = slay(game, me, leader)
    [fact] = world.facts(predicate="wielded_in", subject=item)
    kin = someone(game, "kin")
    world.relate(leader, kin, "kin_of", 1.0, {"role": "child"})
    rival = someone(game, "rival", traits=["proud", "cunning"])
    member = someone(game, "member")
    world.relate(member, sect, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                "secret": False})
    for knower in (kin, rival, member):
        believe(world, knower, fact.id, fact.data["variant"], None, 0.8, 1, "gossip")
    seen = P.reactions(world, me, game.place.id, [kin, rival, member])
    assert seen["covets"] == rival and seen["demands"] == member
    assert seen["hates"] == [kin]
    commit(world, P.hatred_events(world, me, seen["hates"], game.place.id, item))
    assert any(m.feeling == "hatred" for m in world.memories(kin, about=me))
    assert P.reactions(world, me, game.place.id, [kin])["hates"] == []  # hated once, not each scene
    assert died


def test_handing_back_a_claimed_blade_or_keeping_it(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    member = someone(game, "claimant")
    world.relate(member, sect, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                "secret": False})
    kept = gear.make_item(world, "weapon", "sword", 2, me, "found", claimed_by=sect)
    commit(world, P.demand_events(world, me, member, kept, game.place.id, hand_over=False))
    assert kept in world.targets(me, "owns") and world.facts(predicate="kept_gear", subject=me)
    given = gear.make_item(world, "weapon", "saber", 2, me, "found", claimed_by=sect)
    commit(world, P.demand_events(world, me, member, given, game.place.id, hand_over=True))
    assert given in world.targets(member, "owns") and world.facts(predicate="returned_gear", subject=me)
    assert world.entity(given).data["owners"][-1]["how"] == "given"


def test_a_sect_thinks_better_of_one_who_gives_back_and_worse_of_one_who_keeps(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    member = someone(game, "judge")
    before = standing(world, sect, me).score
    blade = gear.make_item(world, "weapon", "sword", 2, me, "found", claimed_by=sect)
    commit(world, P.demand_events(world, me, member, blade, seat, hand_over=False))
    [fact] = world.facts(predicate="kept_gear", subject=me)
    believe(world, seat, fact.id, fact.data["variant"], None, 1.0, 0, "witness")  # the seat's town knows it
    worse = standing(world, sect, me).score
    assert worse < before and "you keep what is ours" in standing(world, sect, me).reasons
