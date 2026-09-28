import pytest

import systems.arrays as AR
import systems.encounters as encounters
import systems.formations as FM
import systems.hall_theft as T
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.duel import fighter_for


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
    base = {"occupation": "tea seller", "traits": ["proud", "hot-tempered"], "realm": "second-rate", "age": 30,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:arrays:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def lay(game, key, owner=None, s=1.0, place=None):
    FM.place_formation(game.world, place or game.place.id, key, owner or game.player.id, s)


def test_a_killing_array_lifts_its_owner_and_a_confusion_array_weakens_everyone_else(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    mine, theirs = fighter_for(world, me, None).realm_mult, fighter_for(world, foe, None).realm_mult
    lay(game, "killing")
    assert fighter_for(world, me, None).realm_mult == pytest.approx(mine * (1 + AR.BATTLE))
    lay(game, "confusion")
    assert fighter_for(world, foe, None).realm_mult == pytest.approx(theirs * (1 - AR.BATTLE))
    assert fighter_for(world, me, None).realm_mult == pytest.approx(mine * (1 + AR.BATTLE))


def test_a_binding_array_holds_everyone_but_its_owner(game):
    world, me = game.world, game.player.id
    foe = someone(game, "runner")
    lay(game, "binding", owner=foe)
    assert AR.held(world, me) and not AR.held(world, foe)
    assert not encounters.flee_succeeds(world, me, foe)


def test_an_array_holds_until_the_next_dawn(game):
    world, me = game.world, game.player.id
    FM.learn(world, me, "killing")
    lay(game, "killing")
    [laid] = FM.laid(world, game.place.id)
    world.set_time(laid["until"])
    assert AR.fight_factor(world, me) == 1.0


def test_one_hidden_by_their_own_concealment_is_not_called_out(game):
    world, me = game.world, game.player.id
    foe = someone(game, "avenger")
    assert not AR.concealed(world, me, game.place.id)
    lay(game, "concealment")
    assert AR.concealed(world, me, game.place.id)
    assert encounters.challenge_from(world, me, game.place.id) is None
    other = someone(game, "other")
    assert not AR.concealed(world, other, game.place.id)  # it hides only the one who laid it


def test_a_seclusion_ward_speeds_cultivation_and_halves_deviation(game):
    import systems.cultivation as cultivation
    world, me, town = game.world, game.player.id, game.place.id
    before = cultivation.meditate_events(world, me, town, 7)[0].data["energy_gained"]
    lay(game, "seclusion", s=1.0)
    after = cultivation.meditate_events(world, me, town, 7)[0].data["energy_gained"]
    assert after == pytest.approx(before * (1 + AR.SECLUSION_GAIN), rel=0.01)
    assert AR.deviation_factor(world, me, town) == AR.SECLUSION_DEVIATION


def test_a_veiled_garden_or_a_great_sects_own_ward_cuts_a_thiefs_chance(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    own = AR.npc_ward(world, sect)
    assert 0 <= own <= 1 and AR.npc_ward(world, sect) == own
    world.update_data(me, realm="life-and-death")
    before = T.chance(world, me, sect)
    lay(game, "veiled_garden", s=1.0, place=seat)
    assert AR.theft_cut(world, sect) == pytest.approx(AR.WARD_CUT)
    assert T.chance(world, me, sect) <= before


def test_the_heavenly_gate_keeps_challengers_off_and_lifts_the_sects_own(game):
    world, me, town = game.world, game.player.id, game.place.id
    assert AR.gate_factor(world, town) == 1.0
    lay(game, "heavenly_gate", s=1.0)
    assert AR.gate_factor(world, town) == pytest.approx(1 - AR.GATE_CUT)
    sect = world.add_entity("faction", "Pine Cloud Hall", {"type": "player_sect", "tier": "minor", "seat": town,
                                                           "ranks": list(F.LADDERS["orthodox_sect"])})
    disciple = someone(game, "disciple")
    world.relate(disciple, sect, "member_of", 0, {"role": "disciple", "status": "member"})
    stranger = someone(game, "stranger")
    assert AR.fight_factor(world, disciple) == pytest.approx(1 + AR.GATE_FIGHT)
    assert AR.fight_factor(world, stranger) == 1.0


def test_a_place_without_formations_reads_nothing_more(game):
    assert AR.fight_factor(game.world, game.player.id) == 1.0 and not AR.held(game.world, game.player.id)
