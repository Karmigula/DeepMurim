import random

from narrate.base import Narrator
from narrate.brief import Brief, PersonBrief, PlaceBrief, event_brief, scene_brief
from narrate.procedural import Grammar, ProceduralNarrator
from narrate.proposals import Proposal, RejectAll
from world.db import World
from world.events import Event
from world.gen.materialize import ensure_town, populate

PLACE = PlaceBrief("Jade Town", "town", "the Misty Peaks", "mountains", "spring", "dusk")
YOU = PersonBrief("Hero", "you", (), "mortal", "self")
LI = PersonBrief("Li Wei", "innkeeper", ("proud", "greedy"), "mortal", "acquaintance")


def brief(kind, other=LI, **details):
    return Brief(kind, "Year 1, Spring day 3, dusk", PLACE, YOU, other, details, (), 42, f"t:{kind}")


def test_is_a_narrator():
    assert isinstance(ProceduralNarrator(), Narrator)


def test_grammar_expands_symbols_and_keeps_unknown_fields():
    grammar = Grammar({"k": {"lines": ["#a# {name} {missing}"]}, "symbols": {"a": ["#b#"], "b": ["hi"]}})
    assert grammar.expand("k", random.Random(1), {"name": "Mo"}) == "Hi Mo {missing}"


def test_deterministic_per_salt():
    narrator = ProceduralNarrator()
    b = brief("met")
    assert narrator.narrate(b) == narrator.narrate(b)
    assert "Li Wei" in narrator.narrate(b)[0][0]


def test_every_kind_renders_fully_from_a_brief_alone():
    narrator = ProceduralNarrator()
    cases = [
        brief("began", None),
        brief("met"),
        brief("conversed", times_ordinal="second", first_met_season="the spring of year 1"),
        brief("asked", topic="work"),
        brief("asked", topic="town"),
        brief("parted"),
        brief("travelled", None, dest="Jade Town", days="three days"),
        brief("scene", None),
    ]
    for b in cases:
        [(text, _)] = narrator.narrate(b)
        assert "#" not in text and "{" not in text, (b.kind, text)


def test_unknown_kind_falls_back():
    assert ProceduralNarrator().narrate(brief("mystery")) == [("[mystery]", "dim")]


def test_real_world_scene_and_opening(tmp_path):
    world = World.create(tmp_path / "t.world", 42)
    town = ensure_town(world, 0, 0, 0)
    player = world.add_entity("person", "Hero", {"is_player": True})
    world.relate(player, town, "located_in")
    populate(world, town)
    [(text, _)] = ProceduralNarrator().narrate(scene_brief(world, town, player, "look"))
    assert world.entity(town).name in text
    [(text, _)] = ProceduralNarrator().narrate(event_brief(world, 1, Event("began", (player,), town)))
    assert "Hero" in text
    world.close()


def test_reject_all():
    verdict = RejectAll().validate(None, Proposal("npc", {}))
    assert not verdict.accepted and verdict.reason
