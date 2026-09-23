import pytest

import systems.encounters as encounters
import systems.learning as learning
from engine.game import Action, Game
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event, Witness, commit
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("curious", "lazy"), realm="mortal", occupation="innkeeper", town=None):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": occupation, "traits": list(traits), "realm": realm, "surname": surname, "given": given,
        "gender": "man", "age": 40, "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, town or game.place.id, "located_in")
    return pid


def grieving(game, name="Wang Da", traits=("curious", "lazy")):
    """Someone whose brother the player killed, and who knows it."""
    npc = person(game, name, traits=traits)
    victim = game.world.add_entity("person", "Wang Li", {"dead": True, "realm": "mortal"})
    game.world.relate(victim, game.place.id, "buried_at")
    game.world.relate(npc, victim, "kin_of", data={"role": "sibling"})
    with game.world.transaction():
        eid = game.world.append_chronicle("died", (game.player.id, victim), game.place.id, {"cause": "killed"}, 1.0)
        game.world.add_memory(npc, eid, "grief", 1.0, True)
    return npc


def deed(game, actor, predicate, target, **story):
    return record_fact(game.world, actor, predicate, target, place=game.place.id,
                       variant=make_variant(predicate, actor, target, place=game.place.name, **story))


def renowned(game):
    for name in ("Ma Bo", "Ma Da", "Ma San"):
        deed(game, game.player.id, "killed", person(game, name, occupation="bandit"), form="fist")


def north(game):
    return next(c.action for c in game.start().all_choices if c.action.verb == "travel" and "north" in c.label)


def test_an_avenger_in_town_calls_you_out(game, monkeypatch):
    monkeypatch.setattr(encounters, "AVENGER_CHANCE", 1.0)
    npc = grieving(game)
    game.perform(Action("look"))
    assert game.challenger == npc


def test_an_avenger_hunts_you_on_the_road(game, monkeypatch):
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "AVENGER_ROAD_CHANCE", 1.0)
    road = north(game)  # before the avenger exists: in town they would call you out on look
    npc = grieving(game)
    turn = game.perform(road)
    assert game.encounter == {"person": npc, "kind": "avenger", "toll": 0}
    assert any('"You killed my sibling."' in text for text, _ in turn.lines)
    assert "road" in {c.action.verb for c in turn.choices}
    game.perform(Action("road", "talk"))
    assert game.combat is not None and game.combat.opponent == npc


def test_the_afraid_refuse_to_fight(game):
    weak = person(game, "Hu Mei")
    deed(game, game.player.id, "killed", person(game, "Wang Li", realm="third-rate"), realm="third-rate")
    game.perform(Action("talk", weak))
    turn = game.perform(Action("challenge", weak))
    assert game.combat is None
    assert "Hu Mei backs away; they want no part of you." in [text for text, _ in turn.lines]


def test_hostile_people_neither_teach_nor_sell(game):
    npc = person(game, "Old Wu", occupation="merchant")
    commit(game.world, [Event("insulted", (game.player.id, npc), game.place.id, {},
                              witnesses=(Witness(npc, "hatred", 1.0),))])
    assert not learning.will_deal(game.world, npc, game.player.id)
    turn = game.perform(Action("talk", npc))
    assert not {"learn_menu", "browse"} & {c.action.verb for c in turn.all_choices}
    assert game.perform(Action("browse")).lines[-1][1] == "system"


def test_the_honest_will_not_teach_a_ruthless_name(game):
    teacher = person(game, "Old Wu", traits=("honest", "greedy"))
    deed(game, game.player.id, "robbed", person(game, "Hu Mei"))
    assert learning.will_deal(game.world, teacher, game.player.id)
    assert not learning.will_teach(game.world, teacher, game.player.id, game.place.id)
    greedy = person(game, "Ma Bo", traits=("greedy", "lazy"))
    assert learning.will_teach(game.world, greedy, game.player.id, game.place.id)


def test_bandits_back_off_from_a_renowned_fighter(game):
    renowned(game)
    game.world.update_data(game.player.id, realm="third-rate")
    region = encounters.region_of(game.world, game.place.id)
    bandit = encounters.make_roamer(game.world, region, "bandit", 0, 0.1)
    game.world.update_data(bandit, realm="mortal")
    assert encounters.backs_off(game.world, bandit, game.player.id, game.place.id)
    events = encounters.encounter_events(game.player.id, bandit, game.place.id, "bandit", 5) + \
        encounters.resolved_events(game.player.id, bandit, game.place.id, "backed_off", "bandit")
    lines = game._commit(events)
    assert encounters.pending_encounter(game.world, game.player.id) is None
    assert any("thinks better of it" in text for text, _ in lines)
    game.world.update_data(bandit, realm="first-rate")
    assert not encounters.backs_off(game.world, bandit, game.player.id, game.place.id)


def test_a_proud_stronger_rival_calls_out_the_renowned(game, monkeypatch):
    monkeypatch.setattr(encounters, "RIVAL_CHANCE", 1.0)
    renowned(game)
    person(game, "Iron Gu", traits=("proud", "lazy"), realm="second-rate")
    picked = game.world.entity(encounters.challenge_from(game.world, game.player.id, game.place.id))
    assert "proud" in picked.data["traits"] and picked.data["realm"] != "mortal"


def test_grudges_are_answered_on_arrival_too(game, monkeypatch):
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 1.0)
    road = north(game)
    town = ensure_town(game.world, *road.target)
    hothead = person(game, "Hot Wu", traits=("hot-tempered", "lazy"), town=town)
    commit(game.world, [Event("parted", (game.player.id, hothead), town, {},
                              witnesses=(Witness(hothead, "annoyed", 0.5),))])
    game.perform(road)
    assert game.challenger == hothead
