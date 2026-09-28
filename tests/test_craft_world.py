import pytest

import systems.craft_world as CW
import systems.encounters as encounters
import systems.formations as FM
import systems.gear as gear
import systems.lives as lives
import systems.smithy as smithy
from debug.invariants import check_crafts
from engine.game import Game
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=20000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "mortal", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:craft:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_smiths_and_formation_masters_carry_a_seeded_skill(game):
    world = game.world
    smith, master, seller = (someone(game, "smith", occupation="blacksmith"),
                             someone(game, "master", occupation="fortune teller"), someone(game, "seller"))
    assert CW.SKILLS[0] <= CW.skill(world, smith) <= CW.SKILLS[1] and CW.skill(world, smith) == CW.skill(world, smith)
    assert CW.crafter(world, master) == "formation master" and CW.skill(world, seller) is None
    assert CW.title(world, smith).endswith(" smith")


def test_a_crafters_skill_rises_now_and_then_in_their_seasons(game, monkeypatch):
    world = game.world
    smith = someone(game, "riser", occupation="blacksmith", craft_skill=2)
    lives.lived_to(world, smith)
    monkeypatch.setattr(CW, "RISE_CHANCE", 1.0)
    world.set_time(world.time + 2 * lives.SEASON)
    lives.catch_up(world, smith)
    assert world.entity(smith).data["craft_skill"] == 4
    assert CW.season_events in lives.AGENDAS


def test_a_master_smith_lifts_the_towns_stall_a_grade(game):
    world, town = game.world, game.place.id
    base = smithy.cap(world, town)
    someone(game, "master smith", occupation="blacksmith", craft_skill=CW.MASTER_SMITH)
    assert smithy.cap(world, town) == min(4, base + 1)


def test_a_formation_master_sells_flags_and_the_manuals_their_skill_reaches(game):
    world, me, town = game.world, game.player.id, game.place.id
    novice = someone(game, "novice", occupation="fortune teller", craft_skill=1)
    grand = someone(game, "grand", occupation="fortune teller", craft_skill=5)
    assert all(FM.PATTERNS[k]["difficulty"] == 1 for k in CW.teaches(world, novice))
    assert set(CW.teaches(world, grand)) == set(FM.PATTERNS)
    commit(world, CW.flags_events(world, me, novice, town))
    assert FM.flags_of(world, me) == CW.FLAG_LOT
    assert CW.manual_block(world, me, novice, "killing") is not None
    commit(world, CW.manual_events(world, me, grand, "killing", town))
    assert FM.manuals_of(world, me)[0].data["pattern"] == "killing"
    assert silver_of(world, me) == 20000 - CW.FLAG_LOT * FM.FLAG_PRICE - FM.manual_price("killing")


def test_a_master_lays_a_pattern_on_commission_at_their_skills_strength(game):
    world, me, town = game.world, game.player.id, game.place.id
    master = someone(game, "layer", occupation="fortune teller", craft_skill=4)
    assert CW.commission_lay_block(world, me, master, "confusion", town) is None
    commit(world, CW.commission_lay_events(world, me, master, "confusion", town))
    [laid] = FM.laid(world, town)
    assert laid["owner"] == me and laid["strength"] == pytest.approx(0.9)
    assert "own sect" in CW.commission_lay_block(world, me, master, "veiled_garden", town)


def test_a_smith_forges_on_commission_ready_in_ten_days(game):
    world, me, town = game.world, game.player.id, game.place.id
    smith = someone(game, "forger", occupation="blacksmith", craft_skill=4)
    assert CW.commission_forge_block(world, me, smith, "weapon", "spear", town) is None
    price = CW.forge_price(world, smith, town, "weapon")
    commit(world, CW.commission_forge_events(world, me, smith, "weapon", "spear", town))
    assert silver_of(world, me) == 20000 - price and CW.ready(world, me, smith) is None
    assert "already" in CW.commission_forge_block(world, me, smith, "weapon", "spear", town)
    world.set_time(world.time + CW.FORGE_DAYS * 4)
    commit(world, CW.collect_events(world, me, smith, town))
    [spear] = [i for i in gear.gear_items(world, me) if i.data["form"] == "spear"]
    assert spear.data["grade"] == 3 and spear.data["maker"] == world.entity(smith).name
    assert CW.pending(world, me) == []


def test_the_rules_hold_a_craft_skill_to_1_5(game):
    world = game.world
    someone(game, "odd", occupation="blacksmith", craft_skill=9)
    assert "craft skill" in " | ".join(check_crafts(world))


def test_the_dead_have_seen_those_where_they_fell(game):
    """A death at a turn's end (5b's poison, 5c's worms) shows the scene it came in: its people are not strangers."""
    from debug.invariants import check_people
    from engine.actions import Turn
    from systems.mortality import death_events
    world, me = game.world, game.player.id
    stranger = someone(game, "witness")
    commit(world, death_events(world, me, "poisoned", None))
    turn = Turn([(f"Here: {world.entity(stranger).name} the tea seller.", "dim")], [], {}, "")
    assert check_people(game, turn) == []
