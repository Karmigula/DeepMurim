import statistics

import pytest

import systems.cultivation as cultivation
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.techniques import create_technique, martial_arts, teach
from systems.time import days_word
from world.body import add_injury
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=3, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def ids(game):
    return game.world, game.player.id, game.place.id


def edit_body(game, **changes):
    world, pid, _ = ids(game)
    body = load_body(world, pid)
    for key, value in changes.items():
        setattr(body, key, value)
    save_body(world, pid, body)
    return body


def run(game, events):
    commit(game.world, events)
    return load_body(game.world, game.player.id)


def test_days_word():
    assert [days_word(d) for d in (1, 7, 30, 90, 12)] == ["a day", "a week", "a month", "a season", "12 days"]


def test_meditation_builds_energy_and_senses_qi(game):
    world, pid, place = ids(game)
    [event] = cultivation.meditate_events(world, pid, place, 7)
    assert event.kind == "cultivated" and event.data["sensed_qi"] and event.data["energy_gained"] > 0
    body = run(game, [event])
    assert "sensed_qi" in body.flags and body.energy_years == pytest.approx(event.data["energy_gained"])
    assert world.time == 7 * 4


def test_seclusion_is_faster_per_day(game):
    world, pid, place = ids(game)
    week = cultivation.meditate_events(world, pid, place, 7)[0].data["energy_gained"] / 7
    month = cultivation.meditate_events(world, pid, place, 30)[0].data["energy_gained"] / 30
    assert month == pytest.approx(week * 1.2, rel=0.01)


def test_pacing_mortal_to_third_rate(tmp_path):
    days_needed = []
    for seed in range(50):
        g = Game.new(tmp_path / f"{seed}.world", "Hero", world_seed=seed, creation=CreationChoice("origin", "hunter"))
        world, pid, place = ids(g)
        days = 0
        while not load_body(world, pid).bottleneck and days < 1000:
            commit(world, cultivation.meditate_events(world, pid, place, 7))
            days += 7
        days_needed.append(days)
        g.close()
    assert 60 <= statistics.median(days_needed) <= 150, days_needed
    assert sorted(days_needed)[44] <= 250, days_needed  # 90th percentile


def test_bottleneck_and_breakthrough_success(game, monkeypatch):
    world, pid, place = ids(game)
    edit_body(game, energy_years=0.99, flags=["sensed_qi"])
    run(game, cultivation.meditate_events(world, pid, place, 30))
    body = load_body(world, pid)
    assert body.bottleneck and body.energy_years == 1.0
    monkeypatch.setattr(cultivation.realms, "breakthrough_chance", lambda b, met: 1.0)
    events = cultivation.breakthrough_events(world, pid, place)
    assert events[0].data["success"] and events[0].data["met"]
    body = run(game, events)
    assert body.realm == 1 and not body.bottleneck
    assert world.entity(pid).data["realm"] == "third-rate"


def test_breakthrough_failure_hurts(game, monkeypatch):
    world, pid, place = ids(game)
    edit_body(game, energy_years=1.0, bottleneck=True, flags=[])
    monkeypatch.setattr(cultivation.realms, "breakthrough_chance", lambda b, met: 0.0)
    events = cultivation.breakthrough_events(world, pid, place)
    event = events[0]
    assert not event.data["success"] and not event.data["met"] and event.data["damaged"]
    body = run(game, events)
    assert body.realm == 0 and body.energy_years == pytest.approx(0.95)
    assert all(body.meridians[m].state == "damaged" for m in event.data["damaged"])
    assert body.deviation == pytest.approx(30)


def test_no_breakthrough_without_bottleneck(game):
    assert cultivation.breakthrough_events(*ids(game)) == []


def test_practise_raises_mastery_to_the_completeness_cap(game):
    world, pid, place = ids(game)
    art = martial_arts(world, pid)[0]
    [event] = cultivation.practise_events(world, pid, place, art.technique.id)
    assert event.data["mastery_after"] > event.data["mastery_before"]
    run(game, [event])
    assert martial_arts(world, pid)[0].mastery == pytest.approx(event.data["mastery_after"])
    flawed = create_technique(world, "Broken Scroll Fist", dict(art.technique.data, form="fist"))
    teach(world, pid, flawed, completeness=0.3, known_completeness=1.0, source="manual", mastery=0.3)
    [event] = cultivation.practise_events(world, pid, place, flawed)
    assert event.data["stalled"] and event.data["mastery_after"] == pytest.approx(0.3)
    assert event.data["deviation_added"] >= 10.5


def test_deviation_strikes_at_the_limit(game):
    world, pid, place = ids(game)
    art = martial_arts(world, pid)[0]
    teach(world, pid, art.technique.id, completeness=0.05, mastery=0.05)
    edit_body(game, deviation=99.0)
    events = cultivation.practise_events(world, pid, place, art.technique.id)
    assert [e.kind for e in events] == ["practised", "deviation"]
    body = run(game, events)
    assert body.deviation == pytest.approx(40)
    assert any(body.meridians[m].state in ("damaged", "scarred") for m in events[1].data["damaged"])


def test_opening_a_meridian(game, monkeypatch):
    world, pid, place = ids(game)
    assert "need" in cultivation.why_not_open(load_body(world, pid), "Governing")
    edit_body(game, energy_years=2.5, realm=1,
              physique={"strength": 10, "agility": 10, "endurance": 10, "comprehension": 10})
    monkeypatch.setattr(cultivation, "FORCE_CHANCE", 0.0)
    weeks = 0
    while load_body(world, pid).meridians["Governing"].state == "blocked":
        run(game, cultivation.open_meridian_events(world, pid, place, "Governing"))
        weeks += 1
        assert weeks < 60
    body = load_body(world, pid)
    assert body.meridians["Governing"].flow == 0.3
    assert "already open" in cultivation.why_not_open(body, "Governing")


def test_forcing_a_meridian_can_damage_another(game, monkeypatch):
    world, pid, place = ids(game)
    edit_body(game, energy_years=2.5, realm=1)
    monkeypatch.setattr(cultivation, "FORCE_CHANCE", 1.0)
    [event] = cultivation.open_meridian_events(world, pid, place, "Conception")
    assert event.data["forced"] and event.data["forced_damage"]
    body = run(game, [event])
    assert body.meridians[event.data["forced_damage"]].state == "damaged"
    assert body.deviation == pytest.approx(15)


def test_rest_speeds_healing(game):
    world, pid, place = ids(game)
    body = load_body(world, pid)
    injury = add_injury(body, "left arm", "cut", 3, world.time, "a test")
    save_body(world, pid, body)
    body = run(game, cultivation.rest_events(world, pid, place))
    still = [i.heals_at for i in body.injuries if i.id == injury.id]
    assert not still or still[0] < injury.heals_at


def test_constitution_is_discovered_at_breakthrough(game, monkeypatch):
    world, pid, place = ids(game)
    edit_body(game, energy_years=1.0, bottleneck=True, flags=["sensed_qi"],
              constitution="Dragon Vein Body", constitution_known=False)
    monkeypatch.setattr(cultivation.realms, "breakthrough_chance", lambda b, met: 1.0)
    events = cultivation.breakthrough_events(world, pid, place)
    assert events[0].data["discovered"] == "Dragon Vein Body"
    assert run(game, events).constitution_known
