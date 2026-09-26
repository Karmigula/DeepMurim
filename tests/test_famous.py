import pytest

import systems.famous as FW
import systems.gear as gear
import systems.provenance as P
from debug.invariants import check_gear
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.beliefs import believe
from systems.claimants import staff
from systems.creation import CreationChoice
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def of_type(world, *kinds):
    return [i for i in F.ensure_roster(world) if world.entity(i).data["type"] in kinds]


def famous_of(world, faction):
    return next(i for i in FW.famous_weapons(world) if world.entity(i).seed_path == f"famous:faction:{faction}")


def staffed(world):
    """The factions' masters stand in the world once their seats are made (as a visit or a season makes them)."""
    for fid in F.ensure_roster(world):
        seat = halls.seat_of(world, fid)
        if seat is not None:
            halls.staff_at(world, fid, seat)


def test_great_sects_clans_and_cities_have_their_famous_blades(game):
    world = game.world
    staffed(world)
    FW.ensure_famous(world)
    listed = FW.famous_weapons(world)
    assert listed and len(listed) == len(set(listed))
    great = [f for f in F.ensure_roster(world) if world.entity(f).data.get("tier") == "great"
             and world.entity(f).data["type"] not in FW.CLANS]  # a great clan keeps an heirloom instead
    for sect in [g for g in great if staff(world, g, ("leader",))]:
        blade = world.entity(famous_of(world, sect))
        assert blade.data["famous"] and blade.data["grade"] >= 3
        leaders = staff(world, sect, ("leader",))
        if leaders:
            assert gear.item_in(world, leaders[0], "weapon").id == blade.id  # the master holds the sect's treasure
    for clan in [c for c in of_type(world, "martial_clan", "local_clan") if staff(world, c, ("leader",))]:
        heirloom = world.entity(famous_of(world, clan))
        assert heirloom.data["heirloom_of"] == clan and heirloom.data["claimed_by"] == clan
        assert world.sources(heirloom.id, "owns") or heirloom.data["lost_at"] is not None
    assert all(world.facts(predicate="blade_legend", subject=i) for i in listed)
    FW.ensure_famous(world)
    assert FW.famous_weapons(world) == listed  # seeded once
    assert check_gear(world) == []


def test_no_master_no_famous_blade_yet(game):
    world = game.world
    before = len(world.entities("person"))
    FW.ensure_famous(world)
    for fid in F.ensure_roster(world):
        if not staff(world, fid, ("leader",)):
            assert f"faction:{fid}" not in (world.get_meta("famous_keys") or [])
    assert len(world.entities("person")) == before  # no one is made for a blade


def a_keeper(game):
    world = game.world
    staffed(world)
    FW.ensure_famous(world)
    for item in FW.famous_weapons(world):
        owners = world.sources(item, "owns")
        if owners and not world.entity(owners[0]).data.get("is_player"):
            return owners[0], item
    raise AssertionError("no one keeps a famous blade")


def test_a_killer_takes_a_famous_blade_and_the_player_finds_it_lying(game):
    world, me = game.world, game.player.id
    keeper, item = a_keeper(game)
    killer = world.add_entity("person", "A Killer", {"occupation": "bandit", "traits": ["greedy"], "realm": "peak",
                                                     "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:killer")
    world.relate(killer, game.place.id, "located_in")
    commit(world, [Event("died", (killer, keeper), game.place.id, {"cause": "killed"})])
    assert item in world.targets(killer, "owns")
    commit(world, [Event("died", (me, killer), game.place.id, {"cause": "killed"})])
    assert not world.sources(item, "owns") and item in FW.lying_at(world, game.place.id)
    commit(world, FW.take_lying_events(world, me, item, game.place.id))
    assert item in world.targets(me, "owns") and world.entity(item).data["owners"][-1]["how"] == "found"
    assert check_gear(world) == []


def test_a_famous_blade_goes_to_the_heir_at_a_natural_death(game):
    world = game.world
    keeper, item = a_keeper(game)
    child = world.add_entity("person", "An Heir", {"occupation": "tea seller", "traits": ["kind"], "realm": "mortal",
                                                   "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:heir")
    world.relate(keeper, child, "kin_of", 1.0, {"role": "child"})
    commit(world, [Event("died", (keeper, keeper), None, {"cause": "age", "world": True})])
    assert item in world.targets(child, "owns")
    assert world.entity(item).data["owners"][-1] == {"person": child, "since": world.time, "how": "inherited"}


def test_an_heirloom_given_back_wins_the_clans_favour(game):
    world, me = game.world, game.player.id
    staffed(world)
    FW.ensure_famous(world)
    clan = of_type(world, "martial_clan", "local_clan")[0]
    item = famous_of(world, clan)
    for owner in world.sources(item, "owns"):
        world.unrelate(owner, "owns", item)
        world.unrelate(owner, "wields", item)
    world.relate(me, item, "owns")
    world.update_data(item, owners=world.entity(item).data["owners"] + [{"person": me, "since": 0, "how": "found"}])
    seat = world.entity(clan).data["seat"]
    assert FW.return_block(world, me, item, game.place.id if game.place.id != seat else -1) is not None
    [head] = staff(world, clan, ("leader",))[:1] or [None]
    if head is None:
        pytest.skip("the clan has no head")
    commit(world, FW.return_events(world, me, item, seat))
    assert item in world.targets(head, "owns")
    assert any(m.feeling == "grateful" and m.indelible for m in world.memories(head, about=me))
    assert world.facts(predicate="returned_gear", subject=me)


def test_a_famous_blade_that_slays_a_master_earns_an_epithet(game):
    world = game.world
    keeper, item = a_keeper(game)
    sect = next(f for f in F.ensure_roster(world) if staff(world, f, ("leader",))
                and staff(world, f, ("leader",))[0] != keeper)
    [master] = staff(world, sect, ("leader",))
    commit(world, [Event("died", (keeper, master), None, {"cause": "killed"})])
    assert world.entity(item).data["epithet"] == f"which slew {world.entity(master).name}"


def test_the_hundred_weapons_chronicle_ranks_and_is_told(game):
    world, me = game.world, game.player.id
    staffed(world)
    FW.ensure_famous(world)
    [ranked] = FW.chronicle_events(world, 4)
    order = ranked.data["order"]
    assert order == sorted(order, key=lambda i: FW.standing_of(world, i))
    commit(world, [ranked])
    news = world.facts(predicate="weapon_ranked")
    assert {f.subject for f in news} == set(order[:FW.CHRONICLE_SIZE])  # all new this year
    [told] = world.facts(predicate="weapons_ranked")
    assert FW.chronicle_known(world, me) is None
    believe(world, me, told.id, told.data["variant"], None, 1.0, 1, "posted")
    assert FW.chronicle_known(world, me)["order"] == order


def test_a_legend_alone_lets_you_know_a_famous_blade(game):
    world, me = game.world, game.player.id
    keeper, item = a_keeper(game)
    [legend] = world.facts(predicate="blade_legend", subject=item)
    believe(world, me, legend.id, legend.data["variant"], None, 1.0, 1, "gossip")
    assert P.known_blades(world, me, [keeper]) == [(keeper, item)]
