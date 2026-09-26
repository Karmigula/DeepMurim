"""Phase 5a's deferred minors, each pinned."""
import pytest

import systems.armoury as A
import systems.duel as duel
import systems.encounters as encounters
import systems.famous as FW
import systems.gear as gear
import systems.provenance as provenance
import systems.smithy as SM
import systems.spoils as SP
from engine.actions import Action
from engine.game import Game
from engine.gear_page import item_lines
from systems import factions as F
from systems import halls
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.membership import left_events
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


def someone(game, tag, place=None, **data):
    base = {"occupation": "wandering swordsman", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:min:{tag}")
    game.world.relate(pid, place or game.place.id, "located_in")
    return pid


def the_sect(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    return sect, halls.seat_of(world, sect)


def a_city(world):
    from world.gen.materialize import ensure_town
    from world.gen.region import region_spec
    from world.gen.town import town_spec
    for x in range(-2, 3):
        for y in range(-2, 3):
            for i in range(region_spec(world.world_seed, x, y).town_count):
                if town_spec(world.world_seed, x, y, i).kind == "city":
                    return ensure_town(world, x, y, i)
    raise AssertionError("no city near")


def test_a_city_without_a_wanderer_yet_is_tried_again_next_spring(game):
    world = game.world
    city = a_city(world)
    for p in list(world.sources(city, "located_in")):
        if world.entity(p).data.get("occupation") == "wandering swordsman":
            world.unrelate(p, "located_in")
    FW.ensure_famous(world)
    assert f"city:{city}" not in (world.get_meta("famous_keys") or [])
    someone(game, "wanderer", place=city, realm="first-rate")
    FW.ensure_famous(world)
    assert f"city:{city}" in world.get_meta("famous_keys")


def test_a_far_kill_leaves_the_killers_gear_unmade(game):
    world = game.world
    sect, seat = the_sect(world)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    far = seat if seat != game.place.id else a_city(world)
    bearer = someone(game, "far", place=far)
    world.update_data(bearer, gear={"weapon": 3, "armour": None, "form": "sword"})
    before = len(world.entities("gear"))
    commit(world, [Event("died", (bearer, leader), far, {"cause": "killed"})])
    assert len(world.entities("gear")) == before and gear.carried(world, bearer)["deeds"]


def test_asking_what_the_beaten_carry_writes_nothing(game):
    world, me = game.world, game.player.id
    fresh = someone(game, "fresh")
    world.update_data(fresh, dead=True)  # beaten past doubt: the block reaches the question of their art
    SP.take_block(world, me, fresh, "weapon", game.place.id)
    assert not world.entity(fresh).data.get("arts_ready")


def test_an_epithet_is_shown_only_to_one_who_knows_its_tale(game):
    world, me = game.world, game.player.id
    item = gear.make_item(world, "weapon", "sword", 3, me, "found", famous=True, epithet="which slew Somebody")
    assert not any("which slew" in t for t, _ in item_lines(world, me, world.entity(item)))


def test_kin_hate_a_blade_only_for_a_death_they_have_heard_of(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    item = gear.make_item(world, "weapon", "sword", 3, me, "found")
    commit(world, gear.wield_events(world, me, item, game.place.id))
    commit(world, [Event("died", (me, leader), game.place.id, {"cause": "killed"})])
    kin = someone(game, "kin")
    world.relate(leader, kin, "kin_of", 1.0, {"role": "child"})
    legend = world.add_fact(item, "blade_legend", None, place=game.place.id, weight=1.0, is_true=True,
                            data={"variant": {"predicate": "blade_legend", "actor": item, "target": None}})
    believe(world, kin, legend, {"predicate": "blade_legend", "actor": item, "target": None}, None, 1.0, 1, "gossip")
    assert provenance.reactions(world, me, game.place.id, [kin])["hates"] == []  # they know the blade, not the deed
    [told] = world.facts(predicate="wielded_in", subject=item)
    believe(world, kin, told.id, told.data["variant"], None, 1.0, 1, "gossip")
    assert provenance.reactions(world, me, game.place.id, [kin])["hates"] == [kin]


def test_a_greedy_victor_takes_your_blade_even_when_sparing_you(game, monkeypatch):
    monkeypatch.setattr(SP, "NPC_TAKES", 1.0)
    world, me = game.world, game.player.id
    if gear.weapon_of(world, me) is None:
        pytest.skip("a hand art")
    victor = someone(game, "victor", traits=["greedy", "kind"])
    commit(world, [Event("duel_ended", (me, victor), game.place.id, {
        "duel": None, "mode": "duel", "result": "lost", "reason": "broken", "verdict": "spare", "by": "opponent",
        "silver": 0, "crippled": None, "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None,
        "purpose": {}, "killed": False, "left_for_dead": False})])
    assert gear.weapon_of(world, me) is None and gear.gear_items(world, victor)


def test_an_armoury_blade_handed_back_goes_back_to_the_armoury(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    commit(world, A.draw_events(world, me, sect, "weapon", seat))
    item = gear.item_in(world, me, "weapon").id
    commit(world, left_events(world, me, sect, seat, "deserter"))
    before = A.table(world, sect)
    member = someone(game, "member")
    commit(world, provenance.demand_events(world, me, member, item, game.place.id, hand_over=True))
    grade = world.entity(item).data["grade"]
    assert item not in world.targets(member, "owns") and A.table(world, sect)[grade] == before[grade] + 1


def test_an_heirloom_wins_its_favour_once(game):
    from systems.founding import my_sect
    world, me = game.world, game.player.id
    clan = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] in FW.CLANS)
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    item = gear.make_item(world, "weapon", "saber", 3, me, "found", famous=True, heirloom_of=clan)
    world.set_meta("famous_weapons", FW.famous_weapons(world) + [item])
    head = someone(game, "head")
    event = Event("heirloom_returned", (me, head), game.place.id, {"item": item, "clan": clan})
    import systems.founding as founding
    original = founding.my_sect
    founding.my_sect = lambda w, p: sect
    try:
        commit(world, [event])
        once = F.stance(world, clan, sect)
        commit(world, [event])
        assert F.stance(world, clan, sect) == once
    finally:
        founding.my_sect = original
    assert my_sect


def test_a_dodged_challenge_does_not_follow_you(game):
    game._stake = (123, 456)
    game._after_arrival()
    assert game._stake is None


def test_the_famous_lying_about_are_indexed(game):
    world = game.world
    keeper = someone(game, "keeper")
    item = FW.make_famous(world, "test:lie", "sword", keeper, "made", "a test", game.place.id)
    commit(world, gear.pass_events(world, keeper, None, item, game.place.id, "lost"))
    assert world.get_meta("famous_lying") == [item] and FW.lying_at(world, game.place.id) == [item]
    commit(world, FW.take_lying_events(world, game.player.id, item, game.place.id))
    assert world.get_meta("famous_lying") == []


def test_a_fighter_looks_at_their_gear_once_per_exchange(game, monkeypatch):
    world, me = game.world, game.player.id
    foe = someone(game, "foe2")
    [started] = commit(world, duel.start_events(world, me, foe, game.place.id, "duel"))
    d = duel.Duel.from_event(started, world.chronicle_entry(started))
    calls = {"n": 0}
    original = gear.carried

    def counted(*a, **k):
        calls["n"] += 1
        return original(*a, **k)
    monkeypatch.setattr(gear, "carried", counted)
    duel.exchange_events(world, d, "strike")
    assert calls["n"] <= 2


def test_the_smiths_prices_follow_the_price_of_iron(game, monkeypatch):
    import systems.market as market
    world, town = game.world, game.place.id
    plain = SM.price(world, town, "weapon", 1)
    monkeypatch.setattr(market, "EVENT_FACTORS", [lambda w, t, g: 2.0 if g == "iron" else 1.0])
    assert SM.price(world, town, "weapon", 1) > plain
