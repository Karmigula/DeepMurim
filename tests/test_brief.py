import pytest

from narrate.brief import MAX_FACTS, MAX_PROMPT, event_brief, scene_brief
from systems.talk import greet_events
from world.db import World
from world.events import Event, commit
from world.gen.materialize import ensure_town, populate


@pytest.fixture
def setup(tmp_path):
    world = World.create(tmp_path / "t.world", 42)
    town = ensure_town(world, 0, 0, 0)
    player = world.add_entity("person", "Hero", {"is_player": True, "realm": "mortal"})
    world.relate(player, town, "located_in")
    npc = populate(world, town)[0]
    yield world, town, player, npc
    world.close()


def greet(world, player, npc, town):
    events = greet_events(world, player, npc.id, town)
    [eid] = commit(world, events)
    return event_brief(world, eid, events[0])


def test_first_meeting_brief(setup):
    world, town, player, npc = setup
    brief = greet(world, player, npc, town)
    assert brief.kind == "met"
    assert brief.other.name == npc.name and brief.other.role == npc.data["occupation"]
    assert brief.other.toward_player == "stranger"
    assert brief.place.name == world.entity(town).name
    assert brief.player.name == "Hero"


def test_repeat_meeting_brief_carries_history(setup):
    world, town, player, npc = setup
    greet(world, player, npc, town)
    brief = greet(world, player, npc, town)
    assert brief.kind == "conversed"
    assert brief.other.toward_player == "acquaintance"
    assert brief.details["times_ordinal"] == "second"
    assert brief.details["first_met_season"] == "the spring of year 1"
    assert f"You first met {npc.name} in the spring of year 1." in brief.facts
    assert brief.facts[0].startswith("You first met")  # most salient first


def test_prompt_is_small_labelled_and_id_free(setup):
    world, town, player, npc = setup
    for _ in range(12):
        brief = greet(world, player, npc, town)
    prompt = brief.to_prompt()
    assert len(prompt) <= MAX_PROMPT and len(brief.facts) <= MAX_FACTS
    for label in ("EVENT:", "WHEN:", "WHERE:", "YOU:", "THEM:", "FACTS:"):
        assert label in prompt
    assert "{" not in prompt and "seed" not in prompt.lower() and "salt" not in prompt.lower()
    assert brief.other.toward_player == "familiar face"


def test_travel_and_scene_briefs(setup):
    world, town, player, _ = setup
    event = Event("travelled", (player,), town, {"to": [0, 0, 0], "watches": 12})
    brief = event_brief(world, 99, event)
    assert brief.details["dest"] == world.entity(town).name and brief.details["days"] == "three days"
    assert brief.other is None and "THEM:" not in brief.to_prompt()
    scene = scene_brief(world, town, player, "look")
    assert scene.kind == "scene" and scene.place.terrain == world.entity(town).data["terrain"]
    assert any(fact.startswith("Here:") for fact in scene.facts)
