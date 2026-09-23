import pytest

import systems.duel as duel
import systems.encounters as encounters
from engine.commands import parse
from engine.game import Action, Game
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.kin import avengers_for, ensure_kin, kin_of
from systems.realms import realm_index
from world.events import Event, Witness, commit
from world.gen.materialize import people_at, region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("curious", "lazy"), realm="mortal", seed=None):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": "innkeeper", "traits": list(traits), "realm": realm, "surname": surname, "given": given,
        "gender": "man", "age": 40, "portrait": {"hair": 0, "face": 0, "robe": 0}}, seed)
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def at_mercy(game, npc):
    [sid] = commit(game.world, duel.start_events(game.world, game.player.id, npc, game.place.id, "duel"))
    d = duel.Duel.from_event(sid, game.world.chronicle_entry(sid))
    d.stage, d.harm = "verdict", {"player": 10.0, "opponent": 90.0}
    return d


def test_killing_leaves_a_body_a_fact_and_a_grieving_family(game):
    victim = person(game, "Wang Li")
    events = duel.verdict_events(game.world, at_mercy(game, victim), "kill")
    assert [e.kind for e in events] == ["duel_ended", "died"]
    commit(game.world, events)
    assert game.world.entity(victim).data["dead"]
    assert game.world.targets(victim, "located_in") == []
    assert game.world.targets(victim, "buried_at") == [game.place.id]
    assert victim not in [p.id for p in people_at(game.world, game.place.id)]
    killed = game.world.facts(predicate="killed")[0]
    assert (killed.subject, killed.object, killed.weight) == (game.player.id, victim, 3.0)
    family = kin_of(game.world, victim)
    assert 1 <= len(family) <= 3
    for relative, _role in family:
        memories = game.world.memories(relative)
        assert any(m.feeling == "grief" and m.indelible for m in memories)
        assert any(m.inherited_from == victim and m.feeling == "hatred" for m in memories)
        assert [b.channel for b in game.world.beliefs(relative) if b.fact_id == killed.id] == ["kin"]
    assert set(avengers_for(game.world, game.player.id)) == {r for r, _ in family}


def test_kin_are_seeded_and_share_a_surname_by_blood(game, tmp_path):
    victim = person(game, "Wang Li", seed="test/wang")
    family = ensure_kin(game.world, victim)
    for relative, role in family:
        entity = game.world.entity(relative)
        if role in ("sibling", "parent", "child"):
            assert entity.data["surname"] == "Wang"
        if role == "master":
            assert realm_index(entity.data["realm"]) >= 1
        assert (victim, {"sibling": "sibling", "parent": "child", "child": "parent",
                         "master": "disciple", "disciple": "master"}[role]) in kin_of(game.world, relative)
    assert ensure_kin(game.world, victim) == family
    other = Game.new(tmp_path / "h.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    twin = person(other, "Wang Li", seed="test/wang")
    assert [other.world.entity(r).name for r, _ in ensure_kin(other.world, twin)] == \
        [game.world.entity(r).name for r, _ in family]
    other.close()


def test_a_hateful_foe_leaves_you_for_dead(game):
    foe = person(game, "Iron Gu", traits=("proud", "honest"), realm="first-rate")
    commit(game.world, [Event("insulted", (game.player.id, foe), game.place.id, {},
                              witnesses=(Witness(foe, "hatred", 1.0),))])
    d = at_mercy(game, foe)
    d.stage = "fighting"
    [end] = duel.yield_events(game.world, d)
    assert end.data["verdict"] == "leave_for_dead" and end.data["left_for_dead"]
    commit(game.world, [end])
    body = load_body(game.world, game.player.id)
    assert any(i.location == "torso" and i.kind == "internal" and i.severity == 4 for i in body.injuries)
    assert game.world.facts(predicate="left_for_dead")[0].subject == foe


def test_sparing_an_avenger_calls_off_the_hunt_for_a_season(game):
    victim = person(game, "Wang Li")
    commit(game.world, duel.verdict_events(game.world, at_mercy(game, victim), "kill"))
    avenger = avengers_for(game.world, game.player.id)[0]
    game.world.unrelate(avenger, "located_in")
    game.world.relate(avenger, game.place.id, "located_in")
    commit(game.world, duel.verdict_events(game.world, at_mercy(game, avenger), "spare"))
    assert avenger not in avengers_for(game.world, game.player.id)
    game.world.set_time(game.world.time + 361)
    assert avenger in avengers_for(game.world, game.player.id)


def test_a_masked_killer_is_not_hunted_by_those_who_do_not_know(game):
    victim = person(game, "Wang Li")
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    events = [Event(e.kind, e.actors, e.place, {**e.data, "as": persona}, witnesses=e.witnesses)
              for e in duel.verdict_events(game.world, at_mercy(game, victim), "kill")]
    commit(game.world, events)
    assert game.world.facts(predicate="killed")[0].subject == persona
    assert kin_of(game.world, victim)
    assert avengers_for(game.world, game.player.id) == []


def test_beasts_can_be_killed_but_not_robbed(game):
    wolf = game.world.add_entity("person", "a grey wolf", {"beast": True, "realm": "mortal", "occupation": "grey wolf",
                                                          "traits": ["hot-tempered"]})
    game.world.relate(wolf, game.place.id, "located_in")
    d = at_mercy(game, wolf)
    assert duel.verdict_events(game.world, d, "rob") == []
    commit(game.world, duel.verdict_events(game.world, d, "kill"))
    assert game.world.entity(wolf).data["dead"]
    assert game.world.facts(predicate="killed")[0].weight == 0.5
    assert kin_of(game.world, wolf) == []


def test_a_dead_roamer_is_never_met_again(game):
    region = region_of(game.world, game.place.id)
    first = encounters.make_roamer(game.world, region, "bandit", 0, 0.1)
    commit(game.world, [Event("died", (game.player.id, first), game.place.id, {"cause": "killed"})])
    assert encounters.roamers(game.world, region.id) == []
    slot = encounters._free_roamer_slot(game.world, region)
    assert slot == 1
    assert encounters.make_roamer(game.world, region, "bandit", slot, 0.1) != first


def test_the_verdict_menu_offers_kill_and_the_word_works(game):
    victim = person(game, "Wang Li", traits=("proud", "honest"))
    game.perform(Action("challenge", victim))
    game.combat.stage, game.combat.harm = "verdict", {"player": 0.0, "opponent": 90.0}
    turn = game.perform(Action("look"))
    assert Action("verdict", "kill") in [c.action for c in turn.choices]
    turn = game.perform(Action("verdict", "kill"))
    assert "You kill Wang Li." in [text for text, _ in turn.lines]
    assert game.world.entity(victim).data["dead"]
    assert parse("kill", [], []) == Action("verdict", "kill")
    assert any("Killed Wang Li." in text for text, _ in game.perform(Action("journal")).lines)
