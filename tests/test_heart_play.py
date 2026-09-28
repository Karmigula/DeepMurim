import pytest

import systems.blade_spirits as BS
import systems.daos as DA
import systems.demons as D
import systems.encounters as encounters
import systems.gear as gear
import systems.heart as HT
import systems.oaths as O
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.sheet import sheet_lines
from narrate.gossip_text import rumour_text
from narrate.outcomes import SUMMARIES
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.facts import make_variant
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=1000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "mortal", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:hplay:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def text(turn):
    return " | ".join(t for t, _ in turn.lines)


def shown(turn):
    return [c.label for c in turn.choices]


def test_the_heart_page_tells_the_heart_in_words(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    D.add_demon(world, me, "grudge", foe, 2)
    HT.write(world, me, daos={"spear": 0.3})
    page = text(game.perform(Action("heart")))
    assert "Your dao heart is steady; your way is unaligned." in page
    assert "A grudge against Someone foe (heavy)" in page and "The Dao of the Spear: grasped" in page
    assert "0.3" not in page and "60" not in page  # words, never numbers
    assert any("Dao heart steady; way unaligned; the Dao of the Spear (grasped)" in t for t, _ in sheet_lines(world, me))


def test_an_untouched_heart_keeps_off_the_sheet(game):
    assert ("Heart:", "heading") not in sheet_lines(game.world, game.player.id)  # the sheet fits a 40-row screen


def test_an_oath_is_sworn_from_the_heart_page_by_number_or_by_word(game):
    world, me = game.world, game.player.id
    turn = game.perform(Action("heart"))
    turn = game.perform(next(c.action for c in turn.choices if c.label == "Swear an oath..."))
    assert "Swear to kill no one for a season" in shown(turn)
    game.perform(next(c.action for c in turn.choices if c.label == "Swear to kill no one for a season"))
    assert [o["kind"] for o in O.oaths(world, me)] == ["abstinence"]
    foe = someone(game, "foe")
    D.add_demon(world, me, "grudge", foe, 1)
    turn = game.perform(Action("heart"))
    action = parse("swear vengeance someone foe", turn.choices, turn.extra)
    assert action == Action("swear_oath", ("vengeance", foe))
    turn = game.perform(action)
    assert "You swear on your dao heart: vengeance on Someone foe." in text(turn)


def at_the_gate(game):
    body = load_body(game.world, game.player.id)
    body.realm, body.bottleneck, body.energy_years = 1, True, 5.0
    body.flags.append("sensed_qi")
    body.meridians["Governing"].state = "open"
    save_body(game.world, game.player.id, body)


def test_a_demon_rises_at_the_breakthrough_and_is_faced(game, monkeypatch):
    world, me = game.world, game.player.id
    at_the_gate(game)
    D.add_demon(world, me, "fear", None, 2)
    turn = game.perform(Action("breakthrough"))
    assert "As your qi presses at the gate, the fear of death rises before you." in text(turn)
    assert shown(turn)[:3] == ["Face it", "Bury it and break through", "Turn back"]
    turn = game.perform(Action("heart_trial", "turn_back"))
    assert "You turn back from the gate. The fear of death waits." in text(turn) and D.demons(world, me)
    monkeypatch.setattr(D, "FACE_BOUNDS", (1.0, 1.0))
    game.perform(Action("breakthrough"))
    turn = game.perform(parse("face", [], []))
    assert "You look the fear of death in the face, and it lets you go." in text(turn)
    assert D.demons(world, me) == [] and any(e.kind == "breakthrough" for e in world.chronicle_about(me, limit=5))


def test_a_breakthrough_with_no_demon_is_as_before(game):
    at_the_gate(game)
    turn = game.perform(Action("breakthrough"))
    assert "rises before you" not in text(turn)
    assert any(e.kind == "breakthrough" for e in game.world.chronicle_about(game.player.id, limit=5))


def test_respects_are_paid_at_a_grave_from_the_scene(game):
    world, me, here = game.world, game.player.id, game.place.id
    wife = someone(game, "wife")
    world.relate(me, wife, "kin_of", data={"role": "spouse"})
    commit(world, [Event("died", (wife, wife), here, {"cause": "illness", "world": True})])
    turn = game.perform(Action("look"))
    respects = next(c for c in turn.all_choices if c.label == "Pay your respects to Someone wife")
    turn = game.perform(respects.action)
    assert "You kneel at Someone wife's grave." in text(turn) and D.demons(world, me) == []


def test_amends_and_a_blades_reading_are_asked_in_conversation(game):
    world, me, here = game.world, game.player.id, game.place.id
    foe, widow = someone(game, "foe"), someone(game, "widow", occupation="blacksmith", craft_skill=4)
    world.relate(widow, foe, "kin_of", data={"role": "spouse"})
    D.add_demon(world, me, "guilt", foe, 2)
    item = gear.make_item(world, "weapon", "spear", 2, me, "bought")
    commit(world, gear.wield_events(world, me, item, here))
    game.perform(Action("talk", widow))
    turn = game.perform(Action("heart_talk"))
    assert shown(turn)[:2] == [f"Make amends ({D.AMENDS} silver)", f"Have them look at {world.entity(item).name}"]
    turn = game.perform(Action("make_amends", widow))
    assert "It undoes nothing, but it is something." in text(turn)
    game.perform(Action("heart_talk"))
    turn = game.perform(Action("read_blade", widow))
    assert "Nothing sleeps in it." in text(turn) and BS.spirit_of(world, item) is None


def test_typed_words_and_help_reach_the_heart(game):
    turn = game.perform(Action("look"))
    for word, verb in (("heart", "heart"), ("face", "heart_trial"), ("bury", "heart_trial"),
                       ("turn back", "heart_trial"), ("respects", "pay_respects")):
        assert parse(word, turn.choices, turn.extra).verb == verb
    assert any("heart | swear" in t for t, _ in game.perform(Action("help")).lines)


def test_every_heart_deed_has_a_journal_line():
    for kind in ("heart_trial", "demon_stirred", "paid_respects", "amends_made", "epiphany", "oath_sworn", "oath_kept",
                 "oath_broken", "spirit_woke", "spirit_felt", "blade_whispered", "blade_read", "heart_madness",
                 "madness_passed"):
        assert kind in SUMMARIES, kind


def test_oaths_and_madness_are_told_as_rumours(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    v = make_variant("oath_broken", foe, me)
    v["oath"] = "protection"
    assert rumour_text(world, v, me) == "Someone foe broke an oath sworn on their dao heart to protect you."
    v = make_variant("went_mad", foe, None, place="Crimson Town")
    assert rumour_text(world, v, me) == "Someone foe went mad with their demons in Crimson Town."
    assert DA.dao(world, me, "spear") == 0.0
