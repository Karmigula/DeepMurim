import pytest

import systems.blade_spirits as BS
import systems.encounters as encounters
import systems.gear as gear
import systems.heart as HT
import systems.lives as lives
from debug.invariants import check_spirits
from engine.game import Game
from systems.creation import CreationChoice
from systems.duel import Duel, fighter_for, verdict_events
from systems.famous import famous_weapons, make_famous
from systems.techniques import martial_arts
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


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["proud"], "realm": "mortal", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:spirit:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def spear(game, grade=2, **extra):
    item = gear.make_item(game.world, "weapon", "spear", grade, game.player.id, "bought", **extra)
    commit(game.world, gear.wield_events(game.world, game.player.id, item, game.place.id))
    return item


def kill(game, n, tag="v"):
    for i in range(n):
        victim = someone(game, f"{tag}{i}")
        commit(game.world, [Event("died", (game.player.id, victim), game.place.id, {"cause": "killed"})])


def test_a_blade_counts_its_kills_and_a_spirit_wakes_at_twelve(game):
    world = game.world
    item = spear(game)
    kill(game, 11)
    assert world.entity(item).data["kills"] == 11 and BS.spirit_of(world, item) is None
    kill(game, 1, "w")
    spirit = BS.spirit_of(world, item)
    assert spirit["nature"] == "loyal" and spirit["master"] == game.player.id and spirit["bond"] == 0.0


def test_a_named_masterwork_wakes_at_six_and_a_poor_blade_never(game):
    world, me = game.world, game.player.id
    poor = spear(game, grade=1)
    kill(game, 13, "p")
    assert BS.spirit_of(world, poor) is None
    named = spear(game, grade=3, forged_by=me, famous=True)
    kill(game, 6, "n")
    assert BS.spirit_of(world, named) is not None


def test_a_ruthless_hand_wakes_a_bloodthirsty_spirit(game):
    world, me = game.world, game.player.id
    HT.write(world, me, lean=-40.0)
    item = spear(game)
    kill(game, 12)
    assert BS.spirit_of(world, item)["nature"] == "bloodthirsty"


def test_a_loyal_spirit_binds_to_its_master_and_lends_them_strength(game):
    world, me = game.world, game.player.id
    item = spear(game)
    kill(game, 12)
    art = martial_arts(world, me)[0].technique.id  # the hunter's spear art
    plain = BS.blade_factor(world, me, "spear")
    kill(game, 5, "b")
    assert BS.spirit_of(world, item)["bond"] == 0.5 and plain == 1.0
    assert BS.blade_factor(world, me, "spear") == 1.05 and BS.blade_factor(world, me, "sword") == 1.0
    before = fighter_for(world, me, art).weapon_mult
    world.update_data(item, spirit={**BS.spirit_of(world, item), "master": 999})
    assert fighter_for(world, me, art).weapon_mult == pytest.approx(before / 1.05)


def test_a_bloodthirsty_blade_will_not_be_sheathed_dry_in_a_troubled_hand(game):
    world, me = game.world, game.player.id
    HT.write(world, me, lean=-40.0)
    spear(game)
    kill(game, 12)
    foe = someone(game, "foe")
    duel = Duel(1, me, foe, game.place.id, "duel", stage="verdict", harm={"player": 0.0, "opponent": 90.0})
    assert BS.blade_factor(world, me, "spear") == BS.THIRST and verdict_events(world, duel, "spare")
    HT.write(world, me, steady=20.0)
    assert BS.refuses_spare(world, me) and verdict_events(world, duel, "spare") == []
    assert verdict_events(world, duel, "kill")


def test_a_cursed_famous_blade_hungers_from_its_making(game):
    world = game.world
    keeper = someone(game, "keeper")
    for n in range(15):
        make_famous(world, f"test:curse:{n}", "sword", keeper, "made", "a test", game.place.id)
    cursed = [i for i in famous_weapons(world) if BS.cursed(world, world.entity(i))]
    assert cursed and len(cursed) < len(famous_weapons(world))
    assert BS.spirit_of(world, cursed[0]) | {"known_by": []} == {
        "nature": "bloodthirsty", "bond": 0.0, "master": None, "known_by": [], "cursed": True}


def test_a_season_in_hand_makes_the_spirit_felt_and_an_unfed_thirst_whispers(game):
    world, me = game.world, game.player.id
    HT.write(world, me, lean=-40.0)
    item = spear(game)
    kill(game, 12)
    assert not BS.known(world, me, item)
    world.set_time(world.time + lives.SEASON + 1)
    events = BS.season_hook(world, 0)
    assert [e.kind for e in events] == ["spirit_felt", "blade_whispered"]
    commit(world, events)
    assert BS.known(world, me, item) and HT.steady(world, me) == 55.0


def test_a_skilled_smith_reads_a_blade(game):
    world, me, here = game.world, game.player.id, game.place.id
    item = spear(game)
    kill(game, 12)
    novice = someone(game, "novice", occupation="blacksmith", craft_skill=2)
    master = someone(game, "master", occupation="blacksmith", craft_skill=4)
    assert BS.tell_block(world, me, novice, item) == "They cannot read a blade's heart."
    assert BS.tell_block(world, me, master, item) is None
    commit(world, BS.tell_events(world, me, master, item, here))
    assert BS.known(world, me, item)


def test_a_broken_blade_loses_its_spirit(game):
    world = game.world
    item = spear(game)
    kill(game, 12)
    world.update_data(item, broken=True)
    assert BS.spirit_of(world, item) is None


def test_check_spirits_flags_a_malformed_spirit(game):
    world = game.world
    item = spear(game)
    kill(game, 12)
    assert check_spirits(world) == []
    world.update_data(item, spirit={"nature": "sleepy", "bond": 2.0, "master": None, "known_by": []})
    assert "spirit" in " | ".join(check_spirits(world))
