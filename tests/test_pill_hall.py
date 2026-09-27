import pytest

import systems.encounters as encounters
import systems.herbs as H
import systems.lives as lives
import systems.pill_hall as PH
import systems.sect as sect_mod
from debug.invariants import check_alchemy_world
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.events import commit


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


def the_sect(world, kind="orthodox_sect"):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)
    return sect, halls.seat_of(world, sect)


def join(game, sect, seat, rank=1, role="disciple", merit=200):
    world, me = game.world, game.player.id
    world.relate(me, sect, "member_of", rank, {"role": role, "hall": 0, "merit": merit, "status": "member",
                                              "secret": False})
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")


def merit(world, me, sect):
    return F.membership(world, me, sect)[1]["merit"]


def test_a_great_sect_stocks_three_grades_and_a_bandit_fort_none(game):
    world = game.world
    sect, _ = the_sect(world)
    stock = PH.table(world, sect)
    by_grade = {}
    for key, count in stock.items():
        by_grade[int(key.split(":")[0])] = by_grade.get(int(key.split(":")[0]), 0) + count
    assert by_grade == PH.SEED["great"]
    assert PH.table(world, sect) == stock  # seeded: the same hall every time it is read
    fort = world.add_entity("faction", "Black Wind Fort", {"type": "bandit_fort", "tier": "minor", "seat": None})
    assert not PH.keeps_hall(world, fort)


def test_rank_caps_the_grade_and_a_draw_costs_merit(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=1)
    assert PH.best_grade(world, me, sect) == 1
    assert all(grade == 1 for grade, _ in PH.offers(world, me, sect))
    grade, kind = PH.offers(world, me, sect)[0]
    assert PH.draw_block(world, me, sect, 2, kind, seat) is not None
    before = PH.table(world, sect)[f"{grade}:{kind}"]
    commit(world, PH.draw_events(world, me, sect, grade, kind, seat))
    assert merit(world, me, sect) == 200 - PH.DRAW_MERIT * grade
    assert PH.table(world, sect).get(f"{grade}:{kind}", 0) == before - 1
    [pill] = [world.entity(i) for i in world.targets(me, "owns") if world.entity(i).kind == "pill"]
    assert pill.data["effect"] == kind and pill.data["grade"] == grade and pill.data["maker"] == sect


def test_an_elder_draws_the_third_grade_and_a_rank_nought_nothing(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=3, role="elder")
    assert PH.best_grade(world, me, sect) == PH.ELDER_GRADE
    join(game, sect, seat, rank=0)
    assert PH.best_grade(world, me, sect) is None
    assert PH.offers(world, me, sect) == []


def test_the_hall_is_drawn_from_only_at_the_seat_and_with_the_merit(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=1, merit=5)
    grade, kind = PH.offers(world, me, sect)[0]
    assert "merit" in PH.draw_block(world, me, sect, grade, kind, seat)
    assert "seat" in PH.draw_block(world, me, sect, grade, kind, seat + 100000)


def test_a_drawn_pill_is_kept_on_leaving(game):
    from systems.membership import set_membership
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=1)
    commit(world, PH.draw_events(world, me, sect, *PH.offers(world, me, sect)[0], seat))
    set_membership(world, me, sect, status="expelled")
    assert any(world.entity(i).kind == "pill" for i in world.targets(me, "owns"))
    assert not world.facts(predicate="stole")


def test_each_spring_a_drawn_hall_is_its_seed_again(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=1)
    commit(world, PH.draw_events(world, me, sect, *PH.offers(world, me, sect)[0], seat))
    assert PH.table(world, sect) != PH.seed_of(world, sect)
    PH.season_hook(world, 3)
    assert PH.table(world, sect) != PH.seed_of(world, sect)
    PH.season_hook(world, 4)
    assert PH.table(world, sect) == PH.seed_of(world, sect)


def test_a_garden_holds_herbs_of_the_seats_land_and_grows_each_season(game):
    world = game.world
    sect, seat = the_sect(world)
    grown = PH.garden(world, sect)
    terrain = world.entity(seat).data["terrain"]
    assert PH.GARDEN_HERBS[0] <= len(grown) <= PH.GARDEN_HERBS[1] or len(grown) == len(H.growing(terrain))
    assert all(terrain in H.props(name)["terrains"] for name in grown)
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {n: [1, 0] for n in grown}})
    world.set_time(world.time + 2 * lives.SEASON)
    assert all(count == 1 + 2 * PH.GROWTH for count, _ in PH.garden(world, sect).values())
    world.set_time(world.time + 20 * lives.SEASON)
    assert all(count == PH.GARDEN_CAP for count, _ in PH.garden(world, sect).values())


def test_a_garden_herb_ages_now_and_then_to_a_hundred_years_at_most(game, monkeypatch):
    world = game.world
    sect, _ = the_sect(world)
    monkeypatch.setattr(PH, "AGE_CHANCE", 1.0)
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {"ginseng": [3, 0]}})
    world.set_time(world.time + 5 * lives.SEASON)
    assert PH.garden(world, sect)["ginseng"][1] == PH.TOP_AGE
    assert PH.guarded(world, sect)


def test_a_member_harvests_two_herbs_a_season_for_merit(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(game, sect, seat, rank=0, merit=100)
    herb = next(name for name, (count, _) in PH.garden(world, sect).items() if count > 0)
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {herb: [5, 0]}})
    for _ in range(PH.HARVEST_LIMIT):
        assert PH.harvest_block(world, me, sect, herb, seat) is None
        commit(world, PH.harvest_events(world, me, sect, herb, seat))
    assert "a season" in PH.harvest_block(world, me, sect, herb, seat)
    assert merit(world, me, sect) == 100 - 2 * PH.HARVEST_MERIT
    assert PH.garden(world, sect)[herb][0] == 3
    assert len(H.herbs_of(world, me)) == 2
    world.set_time(world.time + lives.SEASON)
    assert PH.harvest_block(world, me, sect, herb, seat) is None


def test_reading_a_hall_or_a_garden_writes_nothing(game):
    world = game.world
    sect, _ = the_sect(world)
    before = world.digest()
    PH.table(world, sect), PH.garden(world, sect), PH.guarded(world, sect)
    assert world.digest() == before


def own_sect(game):
    from systems.founding import enrol
    world, me = game.world, game.player.id
    town = game.place.id
    sect = world.add_entity("faction", "Pine Cloud Hall", {
        "type": "player_sect", "tier": "minor", "home": [0, 0], "seat": town, "path": "righteous", "taboos": [],
        "trial": "spar", "ranks": list(F.LADDERS["orthodox_sect"]), "treasury": 2000, "power": 20, "wealth": 0,
        "buildings": {}, "last_tick": world.time, "founder": me, "dissolved": False, "chronicle": [], "arts": [],
        "forms": [], "branches": []})
    world.relate(me, sect, "member_of", 4, {"role": "leader", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    world.update_data(me, sect=sect)
    brewer = world.add_entity("person", "Old Brewer", {"occupation": "herbalist", "traits": ["kind"], "realm": "mortal",
                                                       "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:brewer")
    world.relate(brewer, town, "located_in")
    enrol(world, brewer, sect, 60)
    return sect, town


def test_the_own_sect_builds_a_garden_and_a_hall(game):
    world, me = game.world, game.player.id
    sect, town = own_sect(game)
    assert not PH.keeps_hall(world, sect) and PH.garden(world, sect) == {}
    for name in ("herb_garden", "pill_hall"):
        assert name in sect_mod.BUILDINGS
        commit(world, sect_mod.build_events(world, me, name, town))
    assert not PH.keeps_hall(world, sect)  # a season to build
    buildings = world.entity(sect).data["buildings"]
    world.update_data(sect, buildings={b: {**v, "built": True} for b, v in buildings.items()})
    assert PH.keeps_hall(world, sect) and PH.keeps_garden(world, sect)
    assert PH.table(world, sect) == {}  # nothing refined yet
    world.set_time(world.time + 3 * lives.SEASON)
    stock = PH.table(world, sect)
    assert stock and all(key.startswith("1:") for key in stock)  # the herbalist refines grade 1
    assert sum(stock.values()) <= PH.OWN_HALL_CAP
    grade, kind = PH.offers(world, me, sect)[0]
    commit(world, PH.draw_events(world, me, sect, grade, kind, town))  # the founder draws for nothing
    assert F.membership(world, me, sect)[1]["merit"] == 0
    assert PH.garden(world, sect)


def test_the_rules_hold_a_garden_and_a_hall_to_their_bounds(game):
    world = game.world
    sect, _ = the_sect(world)
    assert check_alchemy_world(world) == []
    world.update_data(sect, garden={"at": 0, "herbs": {"moonflower": [13, 0]}}, pill_hall={"1:qi": -1})
    problems = " | ".join(check_alchemy_world(world))
    assert "garden" in problems and "pill hall" in problems
