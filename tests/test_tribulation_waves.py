import pytest

import systems.demons as D
import systems.encounters as encounters
import systems.formations as FM
import systems.karma as K
import systems.realms as realms
import systems.tribulation_waves as TW
import systems.tribulations as TR
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from systems.bodies import load_body, save_body
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


def text(turn):
    return " | ".join(t for t, _ in turn.lines)


def gather(game, realm=3, minor=False):
    commit(game.world, TR.gather_events(game.world, game.player.id, game.place.id, realm, minor, "breakthrough"))


def at_the_bottleneck(game, realm):
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years, body.bottleneck = realm, realms.REALMS[realm + 1].threshold, True
    save_body(game.world, game.player.id, body)


def pill(game, grade):
    item = game.world.add_entity("pill", f"a grade-{grade} pill", {"effect": "qi", "grade": grade, "purity": 0.5})
    game.world.relate(game.player.id, item, "owns")
    return item


def test_a_breakthrough_to_first_rate_brings_the_waves_and_holds_the_player(game, monkeypatch):
    monkeypatch.setattr(realms, "breakthrough_chance", lambda body, met: 1.0)
    at_the_bottleneck(game, 2)
    turn = game.perform(Action("breakthrough"))
    assert "Clouds gather" in text(turn) and "The first wave of 2: heaven's lightning gathers." in text(turn)
    assert [c.label for c in turn.choices] == ["Endure it"]
    assert "Heaven's tribulation is upon you." in text(game.perform(Action("look")))


def test_a_breakthrough_to_second_rate_brings_a_minor_one(game, monkeypatch):
    monkeypatch.setattr(realms, "breakthrough_chance", lambda body, met: 1.0)
    at_the_bottleneck(game, 1)
    body = load_body(game.world, game.player.id)
    body.meridians["Governing"].state = "open"
    save_body(game.world, game.player.id, body)
    turn = game.perform(Action("breakthrough"))
    assert TR.pending(game.world, game.player.id)["minor"] and "Even this gate is watched." in text(turn)
    assert game.world.facts(predicate="tribulation") == []


def test_enduring_every_wave_comes_through_clean_with_insight_and_merit(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TW, "BOUNDS", (1.0, 1.0))
    body = load_body(world, me)
    body.realm = 3
    save_body(world, me, body)
    gather(game)
    insight = load_body(world, me).insight
    game.perform(Action("wave", "endure"))
    turn = game.perform(parse("endure", [], []))
    assert "You come through heaven's tribulation whole." in text(turn) and TR.pending(world, me) is None
    assert load_body(world, me).insight == insight + 30 and K.karma_of(world, me)["merit"] == TW.CLEAN_MERIT


def test_a_failed_lightning_wave_scars_and_heavenly_fire_cripples(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TW, "BOUNDS", (0.0, 0.0))
    body = load_body(world, me)
    body.realm, body.meridians["Lung"].state = 5, "open"
    save_body(world, me, body)
    gather(game, realm=5)
    for _ in range(4):
        turn = game.perform(Action("wave", "endure"))
    assert "heaven has taken something with it" in text(turn)
    body = load_body(world, me)
    assert any(i.kind == "internal" for i in body.injuries) and body.meridians["Lung"].state == "damaged"


def test_a_strong_enough_pill_turns_a_wave_aside(game):
    world, me = game.world, game.player.id
    gather(game)
    weak, strong = pill(game, 1), pill(game, 2)
    turn = game._turn([])
    assert [c.label for c in turn.choices] == ["Endure it", "Swallow a grade-2 pill against it"]
    turn = game.perform(Action("wave", ("spend", strong)))
    assert "breaks around you like water on stone" in text(turn) and world.entity(strong).data.get("used")
    assert TW.wave_block(world, me, game.place.id, "spend", weak) == "You have no pill strong enough."


def test_a_tribulation_array_shelters_three_waves_at_full_strength(game):
    world, me, here = game.world, game.player.id, game.place.id
    body = load_body(world, me)
    body.realm = 5
    save_body(world, me, body)
    FM.place_formation(world, here, TW.ARRAY, me, 1.0)
    gather(game, realm=5)  # four waves: the array takes three
    for _ in range(3):
        turn = game.perform(Action("wave", "shelter"))
    assert "Shelter under the tribulation array" not in [c.label for c in turn.choices]
    assert TW.wave_block(world, me, here, "shelter") == "No tribulation array shelters you here."


def test_the_demon_comes_as_a_wave_and_is_faced(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(D, "FACE_BOUNDS", (1.0, 1.0))
    monkeypatch.setattr(TW, "BOUNDS", (1.0, 1.0))
    D.add_demon(world, me, "fear", None, 2)
    gather(game)
    game.perform(Action("wave", "endure"))
    turn = game._turn([])
    assert [c.label for c in turn.choices] == ["Face it", "Bury it"]
    turn = game.perform(parse("face", [], []))
    assert "You look the fear of death in the face" in text(turn) and D.demons(world, me) == []


def test_the_heaviest_sinner_can_die_in_the_last_wave(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TW, "BOUNDS", (0.0, 0.0))
    K.write(world, me, sin=450.0)
    body = load_body(world, me)
    body.realm = 3
    save_body(world, me, body)
    gather(game, realm=3)
    t = TR.pending(world, me)
    assert len(t["waves"]) == 6
    for _ in range(6):
        events = TW.wave_events(world, me, game.place.id, "endure")
        commit(world, events)
    assert events[-1].kind == "died" and events[-2].data["died"]
