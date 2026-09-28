import pytest

import systems.encounters as encounters
import systems.karma as K
import systems.karma_world as KW
import systems.threads as TH
import systems.tribulations as TR
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from narrate.gossip_text import rumour_text
from narrate.outcomes import SUMMARIES
from systems.creation import CreationChoice
from systems.facts import make_variant
from systems.purse import silver_of


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
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:kplay:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def text(turn):
    return " | ".join(t for t, _ in turn.lines)


def test_the_temple_takes_alms_and_incense(game):
    world, me = game.world, game.player.id
    someone(game, "abbot", occupation="monk")
    turn = game.perform(Action("look"))
    assert "Visit the temple" in [c.label for c in turn.all_choices]
    turn = game.perform(Action("temple"))
    assert [c.label for c in turn.choices][:4] == ["Give 10 silver in alms", "Give 50 silver in alms",
                                                   "Give 200 silver in alms", "Burn incense"]
    turn = game.perform(parse("alms", [], []))
    assert "You give 50 silver in alms." in text(turn) and K.karma_of(world, me)["merit"] == 5
    assert "watch the smoke climb" in text(game.perform(Action("incense")))


def test_a_fortune_teller_reads_karma_in_words_and_names_the_threads(game):
    world, me = game.world, game.player.id
    teller, friend = someone(game, "teller", occupation="fortune teller"), someone(game, "friend")
    K.write(world, me, merit=60.0, sin=10.0)
    TH.add_thread(world, me, friend, "spared")
    game.perform(Action("talk", teller))
    turn = game.perform(Action("fortune", teller))
    assert "Your merit outweighs your sins." in text(turn)
    assert "A thread runs to Someone friend: you spared them." in text(turn)
    assert silver_of(world, me) == 950 and "60" not in text(turn)


def test_heaven_taking_notice_is_told_as_it_comes(game):
    world, me = game.world, game.player.id
    K.write(world, me, sin=300.0)
    world.set_time(world.time + 400)
    turn = game.perform(Action("rest"))
    assert "Heaven has taken notice of what you have done." in text(turn)
    assert "The first wave of" in text(turn) and TR.pending(world, me)["minor"]


def test_a_misfortune_is_told_as_it_comes(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(KW, "MISFORTUNE_CHANCE", 1.0)
    monkeypatch.setattr(TR, "NOTICE_SIN", 10 ** 6)
    K.write(world, me, sin=300.0)
    world.set_time(world.time + 400)  # into the next season
    turn = game.perform(Action("rest"))
    assert "and you never felt the hand" in text(turn) or "Your leg takes the fall" in text(turn)


def test_typed_words_and_help_reach_karma(game):
    turn = game.perform(Action("look"))
    for word, verb in (("temple", "temple"), ("alms", "alms"), ("incense", "incense"), ("fortune", "fortune"),
                       ("endure", "wave"), ("shelter", "wave")):
        assert parse(word, turn.choices, turn.extra).verb == verb
    assert any("temple | alms" in t for t, _ in game.perform(Action("help")).lines)


def test_every_karmic_deed_has_a_journal_line():
    for kind in ("fated_repaid", "fortune_read", "alms_given", "incense_burned", "misfortune", "commission_refunded",
                 "tribulation_gathers", "tribulation_wave", "tribulation_passed"):
        assert kind in SUMMARIES, kind


def test_the_struck_down_and_the_fallen_are_told_as_rumours(game):
    world, me = game.world, game.player.id
    fiend = someone(game, "fiend")
    v = make_variant("struck_down", fiend, None, place="Crimson Town")
    assert rumour_text(world, v, me) == "Someone fiend was struck down by heaven in Crimson Town."
    v = make_variant("fell_to_tribulation", fiend, None, place="Crimson Town")
    assert rumour_text(world, v, me) == "Someone fiend fell to the heavenly tribulation in Crimson Town."
