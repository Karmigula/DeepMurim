"""Phase 5f review: every new outcome has its grammar, and a duel already joined is fought out before the waves."""

import glob
import tomllib

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.tribulations as TR
from engine.actions import Action
from engine.game import Game
from narrate.outcomes import OUTCOME_BUILDERS
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


def test_every_karmic_outcome_has_its_grammar():
    tables = set()
    for path in glob.glob("narrate/grammar/*.toml"):
        with open(path, "rb") as f:
            tables |= {k for k in tomllib.load(f) if k != "symbols"}
    for kind in ("fated_repaid", "fortune_read", "alms_given", "incense_burned", "misfortune", "commission_refunded",
                 "tribulation_gathers", "tribulation_wave", "tribulation_passed", "encounter.wronged"):
        assert kind in tables or kind.split(".")[0] not in OUTCOME_BUILDERS, kind


def test_a_duel_already_joined_is_fought_out_before_the_waves(game):
    world, me, here = game.world, game.player.id, game.place.id
    foe = world.add_entity("person", "Someone foe", {"occupation": "tea seller", "traits": ["proud"],
                                                     "realm": "mortal", "age": 30,
                                                     "portrait": {"hair": 0, "face": 0, "robe": 0}})
    world.relate(foe, here, "located_in")
    [started] = commit(world, duel.start_events(world, me, foe, here, "duel"))
    game.combat = duel.Duel.from_event(started, world.chronicle_entry(started))
    commit(world, TR.gather_events(world, me, here, 2, True, "notice"))
    turn = game._turn([])
    assert "Endure it" not in [c.label for c in turn.choices]
    assert any("Finish the fight first." in t for t, _ in game.perform(Action("wave", "endure")).lines)
    game.combat = None
    assert [c.label for c in game._turn([]).choices] == ["Endure it"]
