import pytest

import systems.alchemy as A
import systems.duties as duties
import systems.encounters as encounters
import systems.hall_theft as T
import systems.herbs as H
import systems.lives as lives
import systems.pill_hall as PH
import systems.recipe_trade as RT
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.standing import standing
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


def the_sect(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    return sect, halls.seat_of(world, sect)


def go(game, place):
    world, me = game.world, game.player.id
    world.unrelate(me, "located_in")
    world.relate(me, place, "located_in")


def to_night(world):
    while not T.night(world):
        world.set_time(world.time + 1)


def to_day(world):
    while T.night(world):
        world.set_time(world.time + 1)


# --- alchemy duties ------------------------------------------------------------------------------------------

def member(game, sect, seat):
    game.world.relate(game.player.id, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 0,
                                                            "status": "member", "secret": False})
    go(game, seat)


def test_an_alchemy_duty_asks_herbs_of_the_sects_land_and_is_done_when_they_are_brought(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    member(game, sect, seat)
    [keeper] = halls.staff_at(world, sect, seat, roles=("keeper",))
    commit(world, duties.issue_events(world, me, sect, keeper, seat, kind="alchemy"))
    duty = duties.open_duty(world, me)
    d = duty.data
    assert d["task"] == "bring" and duties.BRING[0] <= d["count"] <= duties.BRING[1]
    assert world.entity(seat).data["terrain"] in H.props(d["herb"])["terrains"]
    assert d["deadline"] == world.time + duties.ALCHEMY_DAYS * 4
    assert duties.progress(world, me) is None
    herbs = [H.make_herb(world, d["herb"], 0, me) for _ in range(d["count"])]
    assert duties.progress(world, me) == "done"
    commit(world, duties.done_events(world, me, seat))
    assert F.membership(world, me, sect)[1]["merit"] == 10 * d["difficulty"]
    assert not any(h in world.targets(me, "owns") for h in herbs)


def test_a_refining_duty_asks_a_pill_made_after_it_was_given(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    member(game, sect, seat)
    recipe = A.recipe_entity(world, "calming")
    world.relate(me, recipe, "knows_recipe", 0.5)
    old = A.make_pill(world, me, recipe, 1, 0.8)
    [keeper] = halls.staff_at(world, sect, seat, roles=("keeper",))
    for n in range(8):  # the seeded choice of task: find a refining duty
        world.update_data(me, duties_taken=n, duty=None)
        commit(world, duties.issue_events(world, me, sect, keeper, seat, kind="alchemy"))
        if duties.open_duty(world, me).data["task"] == "refine":
            break
    d = duties.open_duty(world, me).data
    assert d["task"] == "refine" and d["recipe"] == recipe
    assert duties.progress(world, me) is None  # a pill made before the duty does not count
    world.set_time(world.time + 1)
    A.make_pill(world, me, recipe, 1, 0.8)
    assert duties.progress(world, me) == "done"
    commit(world, duties.done_events(world, me, seat))
    assert old in world.targets(me, "owns")


# --- theft ------------------------------------------------------------------------------------------------

def test_theft_is_by_night_at_the_seat(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_day(world)
    assert "dark" in T.steal_block(world, me, sect, "hall", seat)
    commit(world, T.nightfall_events(world, me, seat))
    assert T.night(world)
    assert T.steal_block(world, me, sect, "hall", seat) is None
    assert T.steal_block(world, me, sect, "hall", game.place.id + 100000) is not None


def test_the_chance_weighs_the_thiefs_realm_against_the_guards(game):
    world, me = game.world, game.player.id
    sect, _ = the_sect(world)
    guard, realm = T.guard_of(world, sect)
    assert guard is not None
    world.update_data(me, realm="mortal")
    assert T.chance(world, me, sect) == max(0.1, min(0.9, 0.5 - 0.1 * realm))
    world.update_data(me, realm="life-and-death")
    assert T.chance(world, me, sect) == 0.9


def test_an_unseen_theft_of_the_hall_takes_two_pills_and_leaves_a_deed_without_a_doer(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_night(world)
    monkeypatch.setattr(T, "BOUNDS", (1.0, 1.0))
    before = sum(PH.table(world, sect).values())
    commit(world, T.steal_events(world, me, sect, "hall", seat))
    pills = [world.entity(i) for i in world.targets(me, "owns") if world.entity(i).kind == "pill"]
    assert len(pills) == T.PILLS_TAKEN and all(p.data["how"] == "stolen" for p in pills)
    assert sum(PH.table(world, sect).values()) == before - T.PILLS_TAKEN
    [fact] = world.facts(predicate="robbed_hall")
    assert fact.variant["actor"] is None and fact.variant["target"] == sect
    assert not world.facts(predicate="stole")


def test_a_caught_thief_is_a_criminal_the_sect_hates_and_takes_nothing(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_night(world)
    monkeypatch.setattr(T, "BOUNDS", (0.0, 0.0))
    before = PH.table(world, sect)
    commit(world, T.steal_events(world, me, sect, "hall", seat))
    assert PH.table(world, sect) == before and not any(world.entity(i).kind == "pill" for i in world.targets(me, "owns"))
    [fact] = world.facts(predicate="stole")
    assert fact.object == sect
    assert standing(world, sect, me).score < 0
    guard, _ = T.guard_of(world, sect)
    assert any(m.feeling == "hatred" for m in world.memories(guard, about=me))


def test_a_garden_theft_takes_the_oldest_herbs_first(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_night(world)
    monkeypatch.setattr(T, "BOUNDS", (1.0, 1.0))
    herbs = sorted(PH.garden(world, sect))
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {herbs[0]: [5, 0], herbs[1]: [1, 1]}})
    commit(world, T.steal_events(world, me, sect, "garden", seat))
    taken = sorted(H.herb_info(h) for h in H.herbs_of(world, me))
    assert taken == sorted([(herbs[1], 1), (herbs[0], 0), (herbs[0], 0)])
    assert PH.garden(world, sect)[herbs[0]][0] == 3 and PH.garden(world, sect)[herbs[1]][0] == 0


def test_a_hundred_year_herb_is_guarded_by_a_beast_that_must_be_beaten_first(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_night(world)
    name = sorted(PH.garden(world, sect))[0]
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {name: [4, 2]}})
    assert "guards" in T.steal_block(world, me, sect, "garden", seat)
    [met] = T.guardian_events(world, me, sect, seat)
    beast = met.actors[1]
    assert world.entity(beast).data["beast"] and world.entity(beast).data["guardian_of"] == sect
    commit(world, [Event("duel_ended", (me, beast), seat, {"result": "won", "mode": "encounter", "verdict": "kill",
                                                             "by": "player", "silver": 0, "crippled": None,
                                                             "loot": [], "insight": 0.0, "life_and_death": False,
                                                             "fragment": None, "purpose": None, "killed": True,
                                                             "left_for_dead": False, "duel": None, "reason": "broken"})])
    commit(world, T.nightfall_events(world, me, seat))  # the fight took a watch: the next dark will do
    assert T.steal_block(world, me, sect, "garden", seat) is None


def test_a_secret_scroll_can_be_stolen(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    to_night(world)
    monkeypatch.setattr(T, "BOUNDS", (1.0, 1.0))
    commit(world, T.steal_events(world, me, sect, "scroll", seat))
    [scroll] = RT.scrolls_of(world, me)
    assert scroll.data["source"] == "stolen" and scroll.data["faction"] == sect
    assert scroll.data["key"] in RT.secret_recipes(world, sect)


def test_a_thief_knows_a_hall_only_after_a_look(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    assert not T.knows_hall(world, me, sect)
    to_night(world)
    assert T.look_block(world, me, sect, seat) is None
    commit(world, T.look_events(world, me, sect, seat))
    assert T.knows_hall(world, me, sect)
    assert "know" in T.look_block(world, me, sect, seat)
