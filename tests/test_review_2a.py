"""Findings from the phase 2a final review: the game must never tell the player something false."""

import pytest

import systems.cultivation as cultivation
from engine.game import Action, Game
from narrate.brief import event_brief
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.techniques import create_technique, teach
from world.body import add_injury
from world.events import commit

NEUTRAL_FIST = {
    "category": "martial", "form": "fist", "route": ["Lung", "Heart"], "element": "neutral", "grade": 1,
    "stance": {"name": "Iron Gate Stance", "favours": "guard"}, "power": 1.0, "speed": 1.0, "defence": 1.0,
    "creator": None, "origin": "seeded",
}
AVERAGE = {"strength": 10, "agility": 10, "endurance": 10, "comprehension": 10}


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=3, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def edit_body(game, **changes):
    body = load_body(game.world, game.player.id)
    for key, value in changes.items():
        setattr(body, key, value)
    for name in ("Lung", "Heart"):
        body.meridians[name].state = "open"
    save_body(game.world, game.player.id, body)


def fist(game, completeness, mastery):
    tech = create_technique(game.world, "Plain Fist", dict(NEUTRAL_FIST))
    teach(game.world, game.player.id, tech, completeness=completeness, mastery=mastery)
    return tech


def briefs(game, events):
    ids = commit(game.world, events)
    return [event_brief(game.world, i, e) for i, e in zip(ids, events)]


def test_deviation_counts_the_fading_during_the_action(game):
    edit_body(game, deviation=90.0, physique=dict(AVERAGE))
    tech = fist(game, completeness=0.3, mastery=0.3)  # at its cap: +10.5 for the week
    events = cultivation.practise_events(game.world, game.player.id, game.place.id, tech)
    assert [e.kind for e in events] == ["practised"]  # 90 - 3.5 faded + 10.5 = 97, below 100


def test_rest_doubles_healing_speed_rather_than_halving_what_is_left(game):
    world, pid = game.world, game.player.id
    body = load_body(world, pid)
    injury = add_injury(body, "right leg", "fracture", 5, world.time, "a fall")
    save_body(world, pid, body)
    commit(world, cultivation.rest_events(world, pid, game.place.id, 7))
    after = next(i for i in load_body(world, pid).injuries if i.id == injury.id)
    assert after.heals_at == injury.heals_at - 7 * 4  # a week of rest heals two weeks' worth


def test_a_mastered_art_is_not_stalled(game):
    edit_body(game, deviation=0.0, physique=dict(AVERAGE))
    tech = fist(game, completeness=1.0, mastery=1.0)
    [event] = cultivation.practise_events(game.world, game.player.id, game.place.id, tech)
    assert event.data["mastered"] and not event.data["stalled"] and event.data["deviation_added"] < 10.5
    [brief] = briefs(game, [event])
    assert any("taken all" in line for line in brief.outcome)
    assert not any("stalled" in line for line in brief.outcome)


def test_deviation_after_a_failed_breakthrough_reports_scarring_truthfully(game, monkeypatch):
    edit_body(game, energy_years=1.0, bottleneck=True, deviation=99.0, flags=["sensed_qi"])
    monkeypatch.setattr(cultivation.realms, "breakthrough_chance", lambda b, met: 0.0)
    events = cultivation.breakthrough_events(game.world, game.player.id, game.place.id)
    assert [e.kind for e in events] == ["breakthrough", "deviation"]
    changes = events[1].data["changes"]
    assert changes and all(after == "scarred" for _, _, after in changes)
    breakthrough, deviation = briefs(game, events)
    body = load_body(game.world, game.player.id)
    assert all(body.meridians[name].state == "scarred" for name, _, _ in changes)
    assert any("scarred for good" in line for line in deviation.outcome)


def test_no_energy_loss_is_claimed_when_the_floor_holds(game):
    edit_body(game, realm=1, energy_years=1.0, deviation=99.0, physique=dict(AVERAGE))
    tech = fist(game, completeness=0.3, mastery=0.3)
    events = cultivation.practise_events(game.world, game.player.id, game.place.id, tech)
    assert [e.kind for e in events] == ["practised", "deviation"]
    _, deviation = briefs(game, events)
    assert not any("lost some" in line for line in deviation.outcome)
    assert load_body(game.world, game.player.id).energy_years == pytest.approx(1.0)


def test_cultivate_menu_warns_when_breakthrough_is_not_ready(game):
    edit_body(game, energy_years=1.0, bottleneck=True, flags=[])
    lines = [text for text, _ in game.perform(Action("cultivate")).lines]
    assert any("You must first sense the qi within you." in line for line in lines)
