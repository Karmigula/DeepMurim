import gc
import hashlib
import json
import re
import sys
import time

import anyio
import pytest

import systems.encounters as encounters
from ai.mcp_config import SERVER, config, write_config
from engine.actions import Action
from engine.game import Game
from mcp_server import tools as T
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.db import World
from world.gen.materialize import people_at


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


def view_of(game) -> T.View:
    return T.View(World.open_readonly(game.world.path))


def someone_far(game, tag="far"):
    return game.world.add_entity("person", f"Gu {tag.title()}", {"occupation": "monk", "traits": ["kind"],
                                                                 "realm": "second-rate", "age": 40,
                                                                 "portrait": {"hair": 0, "face": 0, "robe": 0}},
                                 f"test:mcp:{tag}")


def heard(game, subject, predicate="killed", target=None):
    world = game.world
    variant = make_variant(predicate, subject, target, place="Somewhere")
    fact = record_fact(world, subject, predicate, target, place=None, variant=variant, spread=False)
    believe(world, game.player.id, fact, variant, None, 0.9, 1, "test")
    return fact


def test_the_sheet_and_the_place_are_the_players_own(game):
    view = view_of(game)
    assert "Realm: Mortal" in T.sheet(view)
    place = T.place(view)
    assert place.startswith(game.place.name) and "Here:" in place


def test_people_are_those_here_and_those_heard_of_never_a_stranger(game):
    view = view_of(game)
    here = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    assert f"{here.name}, {here.data['occupation']}, here" in T.known_people(view)
    far = someone_far(game)
    assert T.person(view_of(game), "Gu Far") == T.UNKNOWN  # never heard of: no lookup of the truth
    heard(game, far)
    view = view_of(game)
    assert "Gu Far, monk, elsewhere" in T.known_people(view)
    assert T.person(view, "gu far").startswith("Gu Far: monk; kind; second-rate")
    assert "said of them:" in T.person(view, "Gu Far")


def test_memories_and_beliefs_are_theirs_with_opaque_handles(game):
    here = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    game.perform(Action("talk", here.id))
    view = view_of(game)
    assert T.memories_of(view, here.name).startswith("curious: ") and "Met " in T.memories_of(view, here.name)
    far = someone_far(game, "story")
    fact = heard(game, far)
    variant = game.world.facts("killed", subject=far)[0].data["variant"]
    believe(game.world, here.id, fact, variant, None, 0.8, 1, "test")
    beliefs = T.beliefs_of(view_of(game), here.name, "killed")
    handle = "b" + hashlib.sha256(f"{game.world.world_seed}:{here.id}:{fact}".encode()).hexdigest()[:10]
    assert beliefs.startswith(f"[{handle}]") and "Gu Story" in beliefs
    assert T.beliefs_of(view_of(game), here.name, "dragons") == "They hold nothing on that."
    assert T.memories_of(view_of(game), "Nobody At All") == T.UNKNOWN


def test_rumours_chronicle_and_factions(game):
    heard(game, someone_far(game, "rumour"))
    game.perform(Action("rest", 1))
    view = view_of(game)
    assert "Gu Rumour" in T.rumours(view, "gu")
    assert "rest" in T.chronicle(view, "rest").lower()
    assert T.chronicle(view, "zzz") == "Nothing of the kind."
    assert isinstance(T.factions(view), str)


def test_no_answer_carries_an_id_and_none_writes(game):
    heard(game, someone_far(game, "quiet"))
    path = game.world.path
    game.world._conn.execute("pragma wal_checkpoint(truncate)")
    before = path.read_bytes()
    view = view_of(game)
    name = people_at(game.world, game.place.id, exclude=game.player.id)[0].name
    answers = [T.sheet(view), T.known_people(view), T.person(view, name), T.memories_of(view, name),
               T.beliefs_of(view, name, ""), T.rumours(view, ""), T.chronicle(view, "", 10), T.factions(view),
               T.place(view)]
    for answer in answers:
        assert not re.search(r"#\d", answer), answer[:80]
    view.world.close()
    assert path.read_bytes() == before


def test_a_read_that_would_write_is_told_not_known(game):
    view = view_of(game)

    def writes(v):
        v.world.set_meta("touched", 1)
    assert T._safe(writes)(view) == "That is not known."


def test_each_tool_is_quick(game):
    for n in range(200):
        heard(game, someone_far(game, f"crowd{n}"))
    view = view_of(game)
    name = people_at(game.world, game.place.id, exclude=game.player.id)[0].name
    calls = [lambda: T.sheet(view), lambda: T.known_people(view), lambda: T.person(view, "Gu Crowd7"),
             lambda: T.memories_of(view, name), lambda: T.beliefs_of(view, name, ""), lambda: T.rumours(view, "gu"),
             lambda: T.chronicle(view, "", 10), lambda: T.factions(view), lambda: T.place(view)]
    for call in calls:
        call()
        gc.collect()
        start = time.perf_counter()
        for _ in range(5):
            call()
        assert (time.perf_counter() - start) / 5 < 0.03, call


def test_the_config_runs_this_python_on_this_save(game, tmp_path):
    path = write_config(game.world.path, tmp_path / "session")
    data = json.loads(path.read_text(encoding="utf-8"))
    server = data["mcpServers"]["deepmurim"]
    assert server["command"] == sys.executable and server["args"] == [str(SERVER), str(game.world.path.resolve())]
    assert config(game.world.path) == data


def test_the_server_answers_over_stdio(game):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    game.world._conn.execute("pragma wal_checkpoint(truncate)")
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER), str(game.world.path)])

    async def session():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                names = sorted(t.name for t in (await client.list_tools()).tools)
                answer = await client.call_tool("place", {})
                return names, answer.content[0].text
    names, text = anyio.run(session)
    assert names == sorted(t.__name__ for t in T.TOOLS)
    assert text.startswith(game.place.name)
