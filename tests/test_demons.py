import pytest

import systems.demons as D
import systems.encounters as encounters
import systems.heart as HT
import systems.lives as lives
import systems.travel as travel
from debug.invariants import check_heart
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.cultivation import breakthrough_events, meditate_events
from systems.purse import silver_of
from world.events import Event, commit


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


def someone(game, tag):
    pid = game.world.add_entity("person", f"Someone {tag}", {"occupation": "tea seller", "traits": ["proud"],
                                                              "realm": "mortal", "age": 40}, seed_path=f"test:demon:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def duel(game, foe, **data):
    D._from_duel(game.world, Event("duel_ended", (game.player.id, foe), game.place.id, data), 0)


def at_the_gate(game):
    """A Third-rate body at its bottleneck, the way to Second-rate open."""
    body = load_body(game.world, game.player.id)
    body.realm, body.bottleneck, body.energy_years = 1, True, 5.0
    body.flags.append("sensed_qi")
    body.meridians["Governing"].state = "open"
    save_body(game.world, game.player.id, body)


def kinds(game):
    return sorted((d["kind"], d["weight"]) for d in D.demons(game.world, game.player.id))


def test_a_demon_for_the_same_cause_grows_and_the_lightest_goes_past_five(game):
    world, me = game.world, game.player.id
    D.add_demon(world, me, "grudge", 7, 1)
    D.add_demon(world, me, "grudge", 7, 1)
    assert kinds(game) == [("grudge", 2)]
    for whom in range(8, 13):
        D.add_demon(world, me, "guilt", whom, 3)
    assert len(D.demons(world, me)) == 5 and ("grudge", 2) not in kinds(game)


def test_a_beating_leaves_a_grudge_and_the_edge_of_death_a_fear_both_spent_by_winning(game):
    foe = someone(game, "foe")
    duel(game, foe, result="lost", by="opponent", verdict="rob")
    assert kinds(game) == [("grudge", 1)]
    duel(game, foe, result="lost", by="opponent", verdict="leave_for_dead", left_for_dead=True)
    assert kinds(game) == [("fear", 2), ("grudge", 3)]
    duel(game, foe, result="won", by="player", verdict="spare", reason="broken", life_and_death=True)
    assert kinds(game) == []


def test_killing_the_yielded_weighs_as_guilt_eased_by_amends_and_healing(game):
    world, me = game.world, game.player.id
    foe, widow = someone(game, "foe"), someone(game, "widow")
    world.relate(widow, foe, "kin_of", data={"role": "spouse"})
    duel(game, foe, result="won", by="player", verdict="kill", reason="yielded")
    assert kinds(game) == [("guilt", 2)]
    assert D.amends_block(world, me, someone(game, "stranger")) == "You owe them nothing."
    commit(world, D.amends_events(world, me, widow, game.place.id))
    assert kinds(game) == [("guilt", 1)] and silver_of(world, me) == 900 and silver_of(world, widow) >= 100
    D._from_healing(world, Event("healed", (me, widow), game.place.id, {}), 0)
    assert kinds(game) == []


def test_grief_for_the_dead_close_to_you_is_eased_at_their_grave_or_by_the_years(game):
    world, me, here = game.world, game.player.id, game.place.id
    wife, brother = someone(game, "wife"), someone(game, "brother")
    world.relate(me, wife, "kin_of", data={"role": "spouse"})
    world.relate(me, brother, "kin_of", data={"role": "sworn_sibling"})
    commit(world, [Event("died", (wife, wife), here, {"cause": "illness", "world": True}),
                   Event("died", (brother, brother), here, {"cause": "illness", "world": True})])
    assert kinds(game) == [("grief", 2), ("grief", 3)]
    elsewhere = next(r.dest for r in travel.routes_from(world, game.place))
    assert D.respects_block(world, me, wife, elsewhere) == "They do not lie here."  # the dead lie where they fell
    commit(world, D.respects_events(world, me, wife, here))
    assert kinds(game) == [("grief", 2)]
    world.set_time(world.time + D.GRIEF_YEARS * 4 * lives.SEASON)
    D.season_hook(world, 0)
    assert kinds(game) == []


def test_deserting_a_sect_weighs_as_guilt(game):
    world, me = game.world, game.player.id
    D._from_betrayal(world, Event("deserted", (me,), game.place.id, {"faction": 5, "status": "deserter"}), 0)
    assert D.demons(world, me)[0] | {"since": 0} == {"kind": "guilt", "whom": 5, "weight": 2, "since": 0}


def test_the_heaviest_demon_rises_only_at_the_gate_of_second_rate_or_beyond(game):
    world, me = game.world, game.player.id
    D.add_demon(world, me, "fear", None, 1)
    D.add_demon(world, me, "grudge", 7, 2)
    assert D.rising(world, me) is None
    at_the_gate(game)
    assert D.rising(world, me)["kind"] == "grudge"


def test_a_demon_faced_is_laid_to_rest_and_one_that_wins_fails_the_breakthrough(game, monkeypatch):
    world, me, here = game.world, game.player.id, game.place.id
    at_the_gate(game)
    D.add_demon(world, me, "grudge", 7, 2)
    D.add_demon(world, me, "fear", None, 1)
    monkeypatch.setattr(D, "FACE_BOUNDS", (1.0, 1.0))
    events = D.trial_events(world, me, here, "face")
    assert [e.kind for e in events] == ["heart_trial", "breakthrough"] and events[0].data["success"]
    insight = load_body(world, me).insight
    commit(world, events[:1])
    assert kinds(game) == [("fear", 1)] and HT.steady(world, me) == 70.0
    assert load_body(world, me).insight == insight + 10
    monkeypatch.setattr(D, "FACE_BOUNDS", (0.0, 0.0))
    events = D.trial_events(world, me, here, "face")
    assert not events[0].data["success"] and not events[1].data["success"]
    deviation = load_body(world, me).deviation
    commit(world, events[:1])
    assert load_body(world, me).deviation == pytest.approx(min(100.0, deviation + 20))


def test_a_buried_demon_grows_and_weighs_on_the_breakthrough_and_turning_back_costs_nothing(game):
    world, me, here = game.world, game.player.id, game.place.id
    at_the_gate(game)
    D.add_demon(world, me, "guilt", 7, 1)
    plain = breakthrough_events(world, me, here)[0].data["chance"]
    events = D.trial_events(world, me, here, "bury")
    assert events[1].data["chance"] == pytest.approx(max(0.0, plain - 0.1))
    commit(world, events[:1])
    assert kinds(game) == [("guilt", 2)] and HT.steady(world, me) == 55.0
    assert [e.kind for e in D.trial_events(world, me, here, "turn_back")] == ["heart_trial"]


def test_a_shaken_heart_stirs_its_demon_at_meditation(game, monkeypatch):
    world, me, here = game.world, game.player.id, game.place.id
    monkeypatch.setattr(D, "STIR_CHANCE", 1.0)
    HT.write(world, me, steady=10.0)
    D.add_demon(world, me, "grief", 3, 1)
    before = load_body(world, me).deviation
    commit(world, meditate_events(world, me, here, 7))
    assert any(e.kind == "demon_stirred" for e in world.chronicle_about(me, limit=5))
    assert load_body(world, me).deviation >= before + 10 - 1


def test_check_heart_flags_too_many_demons_or_a_stranger(game):
    world, me = game.world, game.player.id
    D.add_demon(world, me, "grief", 3, 1)
    assert check_heart(world) == []
    HT.write(world, me, demons=[{"kind": "envy", "whom": None, "weight": 4, "since": 0}] * 6)
    assert "demon" in " | ".join(check_heart(world))
