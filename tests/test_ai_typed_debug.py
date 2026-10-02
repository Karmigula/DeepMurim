import json
import random
import time
from pathlib import Path

import pytest

import systems.encounters as encounters
from ai.fake import FakeClaude
from ai.validate import KINDS, Scene, accept
from app import App
from config import Config
from debug.invariants import check_world
from engine.game import Game
from systems.creation import CreationChoice
from world.gen.materialize import people_at


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def make_app(tmp_path, *replies, mode="assist"):
    script = list(replies)

    def by_job(job, prompt):  # prose calls fail (the engine's words stand); typed lines take the script
        return None if job.name == "narrate" or not script else script.pop(0)
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=FakeClaude(*[by_job] * 50))
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    return app


def type_and_wait(app, text):
    app.command = text
    app.handle_key("return", "\r")
    for _ in range(500):
        if app.typed.waiting is None:
            return
        app.poll()
        time.sleep(0.01)
    raise AssertionError("no answer came")


def test_the_overlay_tells_the_last_typed_line_and_each_verdict(tmp_path):
    app = make_app(tmp_path, {"prose": "You wait, and spend 900 silver.", "proposals": [
        {"kind": "time", "watches": 1}, {"kind": "pay", "to": "Nobody", "amount": 900}]})
    type_and_wait(app, "I wait a watch.")
    text = "\n".join(t for t, _ in app.debug_lines())
    assert "typed (intent" in text and "I wait a watch." in text and "accepted: time" in text
    assert "rejected pay: they are not here" in text and "paragraph refused: it states 900" in text
    app.shutdown()


def test_the_session_log_keeps_the_typed_exchange_for_bug_reports(tmp_path):
    app = make_app(tmp_path, {"prose": "You wait.", "proposals": [{"kind": "time", "watches": 1}]})
    type_and_wait(app, "I wait a watch.")
    folder = app.bug_report()
    records = [json.loads(line) for line in (folder / "session.jsonl").read_text(encoding="utf-8").splitlines()]
    typed = [r for r in records if r.get("kind") == "ai" and r.get("job") == "intent"]
    assert typed and "THE PLAYER TYPES" in typed[-1]["prompt"] and typed[-1]["accepted"] == [{"kind": "time",
                                                                                               "watches": 1}]
    app.shutdown()


def test_help_tells_how_to_type_what_you_do(tmp_path):
    app = make_app(tmp_path, mode="off")
    app.submit("help")
    assert any("type what you do" in t for t, _ in app.log)
    app.shutdown()


def test_the_fork_guide_tells_how_to_add_a_proposal_kind():
    guide = (Path(__file__).parent.parent / "docs" / "world-events.md").read_text(encoding="utf-8")
    assert "## 18. Typed actions and free talk (phase 6c)" in guide and "**Adding a proposal kind:**" in guide


# --- fuzz (spec 14.9): random proposals, valid and not, never break the world --------------------------------

NAMES = ["Nobody Here", "", None, 7]
FIELDS = {"amount": [1, 2, 0, -5, 10 ** 9, "ten", True], "watches": [1, 3, 0, 9, 2.5], "strength": [0.1, 0.5, 0.9, -1],
          "severity": [1, 2, 3, 0], "feeling": ["grateful", "fear", "glee"], "tone": ["kind", "cruel", "sly"],
          "location": ["head", "left arm", "tail"], "injury": ["cut", "bruise", "hex"],
          "occupation": ["tea seller", "monk", "astronaut"], "traits": [["kind"], ["kind", "proud"], ["evil"], []],
          "realm": ["mortal", "third-rate", "immortal"], "handle": ["b0000000000", "nonsense"],
          "text": ["You helped carry water.", "You bested Mo Tianlong.", "x" * 300], "item": ["a sword", ""],
          "choice": ["Rest a while", "Fly"]}


def random_proposal(rng, here):
    p = {"kind": rng.choice(list(KINDS) + ["fly", None])}
    for key in rng.sample(sorted(FIELDS), rng.randint(0, 6)):
        p[key] = rng.choice(FIELDS[key])
    for key in ("to", "who"):
        if rng.random() < 0.7:
            p[key] = rng.choice(here + NAMES)
    return p


def test_random_proposals_never_break_a_rule_or_the_game(tmp_path):
    rng = random.Random(6)
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    game.start()
    try:
        for round_ in range(120):
            here = [p.name for p in people_at(game.world, game.place.id, exclude=game.player.id)][:6]
            proposals = [random_proposal(rng, here) for _ in range(rng.randint(0, 7))]
            if rng.random() < 0.1:
                proposals = rng.choice([None, "nonsense", [1, "two"], {"kind": "time"}])
            done = accept(Scene(game.world, game.player.id, game.place.id, [], f"fuzz{round_}"), proposals)
            game.apply_proposals(done.events, None)
            if round_ % 30 == 29:
                assert check_world(game.world) == []
        assert check_world(game.world) == []
    finally:
        game.close()


def test_random_replies_through_the_app_never_break_it(tmp_path):
    rng = random.Random(7)
    replies = []
    for _ in range(12):
        replies.append(rng.choice([None, "nonsense", {"prose": 5}, {"proposals": []},
                                   {"prose": "You stand a while.", "proposals": [
                                       random_proposal(rng, []) for _ in range(rng.randint(0, 5))]}]))
    app = make_app(tmp_path, *replies)
    for i in range(12):
        type_and_wait(app, f"I try something odd, number {chr(97 + i)}.")
        assert app.state == "game" and app.crash_count == 0
    assert app.violations == []
    app.shutdown()
