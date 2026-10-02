"""Phase 6c's minors (its final review's deferred list), each pinned by a test that failed first."""
import asyncio
import threading
import time

import pytest

import systems.encounters as encounters
from ai import deeds as D
from ai.backends import ClaudeCode
from ai.bridge import Job
from ai.fake import FakeClaude
from ai.narrate import Narration
from ai.typed import MAX_RECORDED, Typed
from ai.validate import Scene, accept
from app import App
from config import Config
from debug.invariants import check_ai
from engine.actions import Action, Choice
from engine.game import Game
from systems import talk
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import people_at


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def someone(game):
    return people_at(game.world, game.place.id, exclude=game.player.id)[0]


def scene(game, choices=(), salt="m", held=False):
    return Scene(game.world, game.player.id, game.place.id, list(choices), salt, held)


# --- talk wears out its welcome ------------------------------------------------------------------------------

def test_talked_past_their_patience_they_end_it_and_the_model_is_not_asked(tmp_path):
    fake = FakeClaude(*[None] * 40)
    app = App(Config(ai_mode="assist"), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=fake)
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    game = app.game
    npc = someone(game)
    app._show(game.perform(Action("talk", npc.id)))
    lines = [D.talked(game.player.id, npc.id, game.place.id, "Small talk.", "Hm.")
             for _ in range(D.TALK_PER_PATIENCE * talk.patience_of(npc))]
    commit(game.world, lines)
    calls = len(fake.calls)
    app.command = "And another thing."
    app.handle_key("return", "\r")
    assert app.typed.waiting is None and game.focus is None
    assert [job for job, _ in fake.calls[calls:] if job == "dialogue"] == []  # the model is not asked
    assert any(e.kind == "lost_patience" for e in game.world.chronicle_about(npc.id, limit=3))
    app.shutdown()


# --- Esc lets the backend's exchange go too ------------------------------------------------------------------

class ResultMessage:
    def __init__(self, prose):
        self.structured_output, self.result, self.is_error, self.errors = {"prose": prose}, "", False, None


class Slow:
    def __init__(self, options):
        self.queue = None

    async def connect(self):
        self.queue = asyncio.Queue()

    async def disconnect(self):
        pass

    async def query(self, prompt, session_id="default"):
        async def land():
            await asyncio.sleep(2.0 if prompt == "slow" else 0.05)
            await self.queue.put(ResultMessage(prompt))
        asyncio.ensure_future(land())

    async def receive_response(self):
        yield await self.queue.get()


def test_a_let_go_exchange_never_holds_up_the_next(game):
    schema = {"type": "object", "properties": {"prose": {"type": "string"}}, "required": ["prose"]}
    job = Job("intent", "claude-sonnet-5", 10.0, schema, "x")
    door = ClaudeCode(client_factory=Slow)
    first = threading.Thread(target=lambda: door.call(job, "slow"), daemon=True)
    first.start()
    time.sleep(0.3)
    door.cancel("intent")
    began = time.perf_counter()
    assert door.call(job, "quick") == {"prose": "quick"} and time.perf_counter() - began < 1.0
    door.close()


# --- held by a fight, the waves or a trial: only a choice or a feeling ------------------------------------------

def test_while_held_a_typed_line_may_only_choose_or_feel(game):
    npc = someone(game)
    done = accept(scene(game, held=True), [{"kind": "pay", "to": npc.name, "amount": 1}, {"kind": "time", "watches": 1},
                                           {"kind": "feeling", "who": npc.name, "feeling": "fear", "strength": 0.2}])
    assert [p["kind"] for p, _ in done.rejected] == ["pay", "time"] and len(done.events) == 1
    assert done.rejected[0][1] == "not now: you are held"
    assert not game.held()
    game.combat = object()
    assert game.held()
    game.combat = None


# --- the action is weighed after the changes ---------------------------------------------------------------

def test_an_action_the_changes_have_made_impossible_is_not_run(game, monkeypatch):
    start, rest = game.world.time, Choice("Rest a while", Action("rest"))
    asked = []
    monkeypatch.setattr(type(game), "_choices",  # offered before the changes, gone after them
                        lambda self: ([rest], []) if not asked.append(1) and len(asked) == 1 else ([], []))
    npc = someone(game)
    feel = accept(scene(game), [{"kind": "feeling", "who": npc.name, "feeling": "amused", "strength": 0.1}]).events
    turn = game.apply_proposals(feel, Action("rest"))
    assert game.world.time == start and ("That can no longer be done.", "dim") in turn.lines


# --- names are whole names ---------------------------------------------------------------------------------

def test_a_stranger_whose_name_holds_a_known_one_is_still_a_stranger(game):
    npc = someone(game)
    done = accept(scene(game), [{"kind": "deed", "text": f"You bested {npc.name} Wen at dice.", "tone": "bold"}])
    assert done.events == [] and "whom you do not know" in done.rejected[0][1]


def test_a_newcomer_never_shares_the_name_of_someone_here(game):
    new = {"kind": "minor_npc", "occupation": "tea seller", "traits": ["kind"]}
    first = accept(scene(game, salt="twin"), [new]).events[0]
    name = D.newcomer_name(game.world, first.data["path"])
    twin = game.world.add_entity("person", name, {"occupation": "monk"}, "test:twin")
    game.world.relate(twin, game.place.id, "located_in")
    commit(game.world, accept(scene(game, salt="twin"), [new]).events)
    names = [p.name for p in people_at(game.world, game.place.id)]
    assert len(names) == len(set(names))


def test_a_wielded_thing_does_not_hide_another_of_its_name(game):
    world, me, npc = game.world, game.player.id, someone(game)
    knives = [world.add_entity("gear", "Plain Knife", {"slot": "weapon"}, f"test:knife{i}") for i in range(2)]
    for knife in knives:
        world.relate(me, knife, "owns")
    world.relate(me, knives[0], "wields")
    done = accept(scene(game), [{"kind": "give", "to": npc.name, "item": "Plain Knife"}])
    assert done.events and done.events[0].data["item"] == knives[1]


# --- check_ai checks every kind --------------------------------------------------------------------------------

def test_check_ai_holds_deeds_tales_and_gifts_to_their_shape(game):
    me, npc, here = game.player.id, someone(game).id, game.place.id
    commit(game.world, [Event("ai_deed", (me,), here, {"text": "x" * 300, "tone": "sly", "ai": True, "proposal": {}}),
                        Event("ai_gave", (me, npc), here, {"item": "a knife", "ai": True, "proposal": {}})])
    problems = check_ai(game.world)
    assert any("deed past its limits" in p for p in problems) and any("gives no thing" in p for p in problems)


# --- the session log keeps a bounded prompt --------------------------------------------------------------------

def test_the_recorded_prompt_is_bounded(game, monkeypatch):
    monkeypatch.setattr("ai.typed.intent_prompt", lambda *a: "STATE:\n" + "x" * 50_000 + "\nTHE PLAYER TYPES: hi")
    t = Typed(Narration(FakeClaude({"prose": "Hi.", "proposals": []}), "assist"))
    t.start(game, "hi", [])
    for _ in range(300):
        got = t.poll()
        if got:
            break
        time.sleep(0.01)
    t.resolve(game, *got, [], "assist")
    assert len(t.last["prompt"]) <= MAX_RECORDED


# --- an innkeeper ----------------------------------------------------------------------------------------------

def test_a_newcomer_is_told_with_the_right_article(game):
    lines = game._commit([D.arrived(game.player.id, game.place.id, "test:inn", "innkeeper", ["kind"], "mortal", {})])
    assert "An innkeeper is here now." in [t for t, _ in lines]
