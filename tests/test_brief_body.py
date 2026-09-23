import pytest

import systems.cultivation as cultivation
from engine.game import Game
from engine.journal import summarize
from narrate.brief import MAX_PROMPT, event_brief, player_facts
from narrate.procedural import ProceduralNarrator
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import add_injury
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=3, creation=CreationChoice("origin", "scion"))
    yield g
    g.close()


def commit_and_brief(game, events):
    ids = commit(game.world, events)
    return [event_brief(game.world, i, e) for i, e in zip(ids, events)]


def test_opening_tells_origin_and_arts(game):
    text = " ".join(t for t, _ in game.start().lines)
    assert "Fallen clan scion" in text and "You know the" in text


def test_meditation_brief_has_outcome_and_realm(game):
    [brief] = commit_and_brief(game, cultivation.meditate_events(game.world, game.player.id, game.place.id, 7))
    assert brief.player.realm == "Mortal"
    assert brief.outcome[0].startswith("You meditated for a week")
    assert any("sensed the qi" in o for o in brief.outcome)
    prompt = brief.to_prompt()
    assert "OUTCOME:" in prompt and len(prompt) <= MAX_PROMPT


def test_player_facts_rank_permanent_injuries_first(game):
    world, pid = game.world, game.player.id
    body = load_body(world, pid)
    add_injury(body, "left arm", "cut", 2, world.time, "a training accident")
    add_injury(body, "right leg", "fracture", 5, world.time, "Peng Haoming's staff", permanent=True)
    body.deviation = 70
    save_body(world, pid, body)
    facts = player_facts(world, pid)
    assert facts[0] == "Your right leg never healed from Peng Haoming's staff."
    assert any("left arm" in f and "to heal" in f for f in facts)
    assert any("unruly" in f for f in facts)
    assert facts[-1].startswith("You are still a mortal")


def test_hidden_truths_never_reach_the_prompt(game):
    world, pid, place = game.world, game.player.id, game.place.id
    body = load_body(world, pid)
    body.constitution, body.constitution_known = "Nine Yin Body", False
    save_body(world, pid, body)
    [brief] = commit_and_brief(game, cultivation.meditate_events(world, pid, place, 7))
    prompt = brief.to_prompt()
    assert "Nine Yin" not in prompt and "0.8" not in prompt and "80%" not in prompt


def test_breakthrough_narration(game, monkeypatch):
    world, pid, place = game.world, game.player.id, game.place.id
    body = load_body(world, pid)
    body.energy_years, body.bottleneck = 1.0, True
    body.flags.append("sensed_qi")
    save_body(world, pid, body)
    monkeypatch.setattr(cultivation.realms, "breakthrough_chance", lambda b, met: 1.0)
    [brief] = commit_and_brief(game, cultivation.breakthrough_events(world, pid, place))
    assert brief.details["success"] == "yes" and "You broke through to Third-rate!" in brief.outcome
    lines = ProceduralNarrator().narrate(brief)
    assert lines[0][1] != "dim" and ("You broke through to Third-rate!", "dim") in lines


def test_journal_summaries(game):
    world, pid, place = game.world, game.player.id, game.place.id
    commit(world, cultivation.meditate_events(world, pid, place, 30))
    assert summarize(world, world.chronicle_about(pid, limit=1)[0]).endswith("Meditated for a month.")


def test_awakened_old_save_is_narrated(tmp_path):
    path = tmp_path / "old.world"
    game = Game.new(path, "Hero", world_seed=5)
    pid = game.player.id
    game.world._conn.execute("update entities set data = json_remove(data, '$.body') where id = ?", (pid,))
    game.world._conn.execute("delete from relations where a = ? and kind = 'knows'", (pid,))
    game.close()
    game = Game.load(path)
    assert "take stock" in " ".join(t for t, _ in game.start().lines).lower()
    game.close()
