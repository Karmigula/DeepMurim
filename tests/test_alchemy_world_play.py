import pytest

import systems.alchemy as A
import systems.control as C
import systems.encounters as encounters
import systems.guild as G
import systems.hall_theft as T
import systems.physic as PY
import systems.recipe_trade as RT
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.outcomes import SUMMARIES
from systems import factions as F
from systems import halls
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import WATCHES_PER_DAY, add_injury
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=5000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def labels(turn):
    return [c.label for c in turn.all_choices]


def pick(turn, verb):
    return next(c.action for c in turn.all_choices if c.action.verb == verb)


def go(game, place):
    world, me = game.world, game.player.id
    world.unrelate(me, "located_in")
    world.relate(me, place, "located_in")


def the_sect(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    return sect, halls.seat_of(world, sect)


def a_city(world):
    from world.gen.materialize import ensure_town
    from world.gen.region import region_spec
    from world.gen.town import town_spec
    for x in range(-3, 4):
        for y in range(-3, 4):
            for i in range(region_spec(world.world_seed, x, y).town_count):
                if town_spec(world.world_seed, x, y, i).kind == "city":
                    return ensure_town(world, x, y, i)
    raise AssertionError("no city near")


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal", "age": 30,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:awplay:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_a_member_draws_and_harvests_from_the_sects_hall_and_garden(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    world.relate(me, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 300, "status": "member",
                                            "secret": False})
    go(game, seat)
    turn = game.perform(Action("look"))
    assert "Your sect's pill hall and garden" in labels(turn)
    turn = game.perform(Action("pill_hall"))
    page = " | ".join(t for t, _ in turn.lines)
    assert "Pill hall:" in page and "Herb garden:" in page
    game.perform(pick(turn, "draw_pill"))
    assert any(world.entity(i).kind == "pill" for i in world.targets(me, "owns"))
    turn = game.perform(Action("pill_hall"))
    game.perform(pick(turn, "harvest"))
    assert any(world.entity(i).kind == "herb" for i in world.targets(me, "owns"))


def test_the_guild_is_joined_and_sat_in_a_city_and_its_scrolls_read(game, monkeypatch):
    world, me = game.world, game.player.id
    go(game, a_city(world))
    turn = game.perform(Action("look"))
    assert "The Alchemists' Guild" in labels(turn)
    turn = game.perform(Action("guild"))
    game.perform(pick(turn, "guild_join"))
    assert world.entity(me).data["guild_rank"] == 0
    world.relate(me, A.recipe_entity(world, "calming"), "knows_recipe", 0.5)
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (1.0, 1.0))
    turn = game.perform(Action("guild"))
    game.perform(pick(turn, "guild_exam"))
    assert world.entity(me).data["guild_rank"] == 1
    turn = game.perform(Action("guild"))
    game.perform(pick(turn, "buy_scroll"))
    turn = game.perform(Action("alchemy"))
    assert "Scrolls you carry:" in " | ".join(t for t, _ in turn.lines)
    known = len(A.known_recipes(world, me))
    game.perform(pick(turn, "read_scroll"))
    assert len(A.known_recipes(world, me)) == known + 1
    assert any("Alchemists' Guild: a first-rank alchemist" in t for t, _ in sheet_lines(world, me))


def test_the_physician_treats_and_tells_of_famous_doctors(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    add_injury(body, "left arm", "cut", 3, world.time, "a test")
    save_body(world, me, body)
    turn = game.perform(Action("look"))
    assert "Visit the physician" in labels(turn)
    turn = game.perform(Action("clinic"))
    game.perform(pick(turn, "physician_treat"))
    turn = game.perform(Action("clinic"))
    turn = game.perform(pick(turn, "ask_doctor"))
    assert any("was last seen in" in t for t, _ in turn.lines)
    turn = game.perform(Action("clinic"))
    assert any("was last seen in" in t for t, _ in turn.lines)


def test_by_night_a_thief_waits_looks_and_steals(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    go(game, seat)
    while T.night(world):
        world.set_time(world.time + 1)
    turn = game.perform(Action("night"))
    turn = game.perform(pick(turn, "nightfall"))
    assert T.night(world)
    turn = game.perform(Action("night"))
    turn = game.perform(pick(turn, "survey"))
    assert any("Pill hall:" in t for t, _ in turn.lines)
    monkeypatch.setattr(T, "BOUNDS", (1.0, 1.0))
    turn = game.perform(Action("night"))
    steal = next(c.action for c in turn.all_choices if c.action.verb == "steal" and c.action.target[1] == "hall")
    game.perform(steal)
    assert any(world.entity(i).kind == "pill" for i in world.targets(me, "owns"))


def test_the_guardian_of_a_garden_comes_out_of_the_dark(game):
    import systems.lives as lives
    world = game.world
    sect, seat = the_sect(world)
    go(game, seat)
    while not T.night(world):
        world.set_time(world.time + 1)
    name = sorted(__import__("systems.pill_hall", fromlist=["x"]).garden(world, sect))[0]
    world.update_data(sect, garden={"at": lives.current_season(world), "herbs": {name: [4, 2]}})
    game.perform(Action("steal", (sect, "garden")))
    assert game.encounter is not None


def test_a_sick_npc_is_treated_through_the_talk_menu(game):
    world, me = game.world, game.player.id
    sick = someone(game, "sick")
    body = load_body(world, sick)
    add_injury(body, "torso", "cut", 2, world.time, "a test")
    save_body(world, sick, body)
    A.make_pill(world, me, A.recipe_entity(world, "wood_healing"), 1, 0.8)
    turn = game.perform(Action("talk", sick))
    assert "Alchemy and medicine..." in labels(turn)
    turn = game.perform(Action("remedies"))
    turn = game.perform(pick(turn, "heal"))
    assert PY.ailment(world, sick) is None


def test_bound_to_a_master_the_sheet_says_so_and_the_worms_kill_the_unfed(game):
    world, me = game.world, game.player.id
    master = someone(game, "master", occupation="bandit", realm="first-rate")
    C.bind(world, me, master)
    text = " | ".join(t for t, _ in sheet_lines(world, me))
    assert f"Bound to {world.entity(master).name} by a control pill" in text
    world.set_time(world.time + C.MONTH + (C.STARVE_DAYS + 1) * WATCHES_PER_DAY)
    game.perform(Action("look"))
    assert world.entity(me).data.get("dying") or world.entity(me).data.get("dead")


def test_a_beaten_foe_is_bound_from_the_scene(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    commit(world, [Event("duel_ended", (me, foe), game.place.id, {
        "result": "won", "mode": "duel", "verdict": "spare", "by": "player", "silver": 0, "crippled": None,
        "loot": [], "insight": 0.0, "life_and_death": False, "fragment": None, "purpose": None, "killed": False,
        "left_for_dead": False, "duel": None, "reason": "yielded"})])
    game._beaten = foe
    A.make_pill(world, me, A.recipe_entity(world, "control"), 4, 0.6)
    turn = game.perform(Action("look"))
    game.perform(pick(turn, "force_control"))
    assert C.bound(world, foe)["master"] == me
    A.make_pill(world, me, A.recipe_entity(world, "control"), 4, 0.6)
    turn = game.perform(Action("bound_menu"))
    game.perform(pick(turn, "feed_servant"))
    assert C.bound(world, foe)["fed_until"] > world.time + C.MONTH


def test_an_alchemy_duty_is_asked_of_the_hall_keeper(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    world.relate(me, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 0, "status": "member",
                                            "secret": False})
    go(game, seat)
    keeper = halls.keeper_at(world, sect, seat)
    game.perform(Action("talk", keeper))
    turn = game.perform(Action("faction_menu"))
    assert "Ask for an alchemy duty" in labels(turn)
    turn = game.perform(pick(turn, "alchemy_duty"))
    assert any("to the seat" in t for t, _ in turn.lines)


def test_typed_words_reach_the_alchemy_world(game):
    turn = game.perform(Action("look"))
    for word, verb in (("guild", "guild"), ("clinic", "clinic"), ("doctors", "ask_doctor"), ("night", "night"),
                       ("pill hall", "pill_hall"), ("bound", "bound_menu"), ("read", "read_scroll")):
        assert parse(word, turn.choices, turn.extra).verb == verb


def test_help_names_the_alchemy_world(game):
    assert any("guild | clinic | doctors" in t for t, _ in game.perform(Action("help")).lines)


def test_every_alchemy_world_deed_has_a_journal_line():
    for kind in ("pill_drawn", "garden_harvested", "secret_scroll_given", "guild_joined", "guild_exam",
                 "scroll_bought", "scroll_sold", "scroll_read", "recipe_taught", "secret_sold", "physician_treated",
                 "physician_cured", "body_read", "asked_doctor", "go_played", "doctor_cured", "waited_for_night",
                 "hall_surveyed", "hall_theft", "healed", "patient_brought", "contract_taken", "contract_poisoned",
                 "contract_paid", "contract_void", "npc_pill_bought", "service_rendered", "worms_forced",
                 "control_forced", "servant_fed", "worms_killed", "control_freed"):
        assert kind in SUMMARIES, kind


def test_rumours_of_the_alchemy_world_read_as_sentences(game):
    from narrate.gossip_text import rumour_text
    from systems.facts import make_variant
    world, me = game.world, game.player.id
    sect, _ = the_sect(world)
    ranked = make_variant("guild_rank", me, None)
    ranked.update(rank=5)
    assert rumour_text(world, ranked, me) == "You are now a fifth-rank alchemist."
    robbed = make_variant("robbed_hall", None, sect)
    robbed.update(what="garden")
    assert rumour_text(world, robbed, me) == f"Someone robbed the {world.entity(sect).name}'s herb garden in the night."
    assert rumour_text(world, make_variant("stole", me, sect), me) == f"You stole from the {world.entity(sect).name}."
    assert RT.price("calming") == 100 and G.title(1) == "a first-rank alchemist"
