import pytest

from engine.game import Game
from systems.beliefs import (
    CONF_DECAY, appears_as, confidence_phrase, identities, knowledge_of, knows_identity, known_people,
)
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event, Witness, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name="Bandit Ma", realm="mortal", occupation="bandit", traits=("greedy", "proud")):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": occupation, "traits": list(traits), "realm": realm, "surname": surname, "given": given,
        "gender": "man", "age": 30, "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def ended(game, opp, **changes):
    data = {"duel": None, "mode": "duel", "result": "won", "reason": "broken", "verdict": "rob", "by": "player",
            "silver": 0, "crippled": None, "loot": [], "insight": 1.0, "life_and_death": False,
            "fragment": None, "purpose": {}}
    data.update(changes)
    return Event("duel_ended", (game.player.id, opp), game.place.id, data, witnesses=(Witness(opp, "humiliated", 0.8),))


def test_robbing_someone_becomes_two_true_facts(game):
    opp = person(game)
    commit(game.world, [ended(game, opp)])
    facts = {f.predicate: f for f in game.world.facts()}
    assert set(facts) == {"defeated", "robbed"}
    robbed = facts["robbed"]
    assert (robbed.subject, robbed.object, robbed.weight, robbed.is_true) == (game.player.id, opp, 1.0, True)
    assert robbed.variant["place"] == game.place.name and robbed.variant["actor"] == game.player.id
    assert facts["defeated"].weight == 0.5


def test_a_realm_gap_makes_a_heavier_story(game):
    opp = person(game, realm="second-rate")
    commit(game.world, [ended(game, opp, verdict="spare")])
    defeated = game.world.facts(predicate="defeated")[0]
    assert defeated.weight == pytest.approx(0.5 + 0.75 * 2)
    assert defeated.variant["realm"] == "second-rate"
    assert game.world.facts(predicate="spared")[0].weight == 0.5


def test_witnesses_know_first_hand_and_the_town_talks(game):
    opp = person(game)
    onlooker = person(game, "Old Wu", occupation="innkeeper", traits=("kind", "honest"))
    commit(game.world, [Event("duel_ended", (game.player.id, opp), game.place.id,
                              ended(game, opp).data, witnesses=(Witness(onlooker, "witnessed_duel", 0.2),))])
    robbed = game.world.facts(predicate="robbed")[0]
    firsthand = {b.knower: b for b in game.world.believers(robbed.id)}
    for knower in (game.player.id, opp, onlooker):
        assert firsthand[knower].hops == 0 and firsthand[knower].confidence == 1.0
        assert firsthand[knower].channel == "witness"
    pool = firsthand[game.place.id]
    assert (pool.hops, pool.confidence, pool.channel) == (1, CONF_DECAY, "gossip")


def test_spars_and_tests_make_no_facts(game):
    opp = person(game)
    commit(game.world, [ended(game, opp, mode="spar", result="spar_won", verdict=None)])
    assert game.world.facts() == []


def test_losing_makes_the_winner_the_subject(game):
    opp = person(game)
    commit(game.world, [ended(game, opp, result="lost", by="opponent", verdict="rob")])
    robbed = game.world.facts(predicate="robbed")[0]
    assert (robbed.subject, robbed.object) == (opp, game.player.id)


def test_a_beast_is_never_the_subject(game):
    wolf = game.world.add_entity("person", "a grey wolf", {"beast": True, "realm": "mortal", "occupation": "grey wolf"})
    game.world.relate(wolf, game.place.id, "located_in")
    commit(game.world, [ended(game, wolf, result="lost", by="opponent", verdict="spare")])
    assert game.world.facts() == []


def test_town_gossip_reaches_townsfolk_one_retelling_further(game):
    opp = person(game)
    listener = person(game, "Old Wu", occupation="innkeeper", traits=("kind", "honest"))
    commit(game.world, [ended(game, opp)])
    heard = {f.predicate: b for b, f in knowledge_of(game.world, listener)}
    assert heard["robbed"].hops == 2
    assert heard["robbed"].confidence == pytest.approx(round(CONF_DECAY * CONF_DECAY, 3))
    assert heard["robbed"].source == game.place.id


def test_masked_deeds_are_credited_to_the_persona_until_someone_knows(game):
    opp = person(game)
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    event = ended(game, opp)
    event = Event(event.kind, event.actors, event.place, {**event.data, "as": persona}, witnesses=event.witnesses)
    [eid] = commit(game.world, [event])
    robbed = game.world.facts(predicate="robbed")[0]
    assert robbed.subject == persona and robbed.variant["masked"] is True
    entry = game.world.chronicle_entry(eid)
    assert appears_as(game.world, opp, entry, game.player.id) == persona
    assert appears_as(game.world, game.player.id, entry, game.player.id) == game.player.id
    assert knows_identity(game.world, game.player.id, persona)
    assert not knows_identity(game.world, opp, persona)
    record_fact(game.world, persona, "is", game.player.id, place=game.place.id,
                variant=make_variant("is", persona, game.player.id))
    assert knows_identity(game.world, opp, persona)  # the town pool now carries it
    assert appears_as(game.world, opp, entry, game.player.id) == game.player.id
    assert identities(game.world, opp, game.player.id) == {game.player.id, persona}


def test_confidence_words():
    assert confidence_phrase(0, 1.0) == "you saw it yourself"
    assert confidence_phrase(1, 0.85) == "from a witness"
    assert confidence_phrase(3, 0.6) == "hearsay"
    assert confidence_phrase(6, 0.3) == "doubtful"


def test_known_people_are_those_met_or_heard_of(game):
    stranger = person(game, "Far Away")
    met = next(p for p in game.world.sources(game.place.id, "located_in")
               if not game.world.entity(p).data.get("is_player") and p != stranger)
    from engine.game import Action
    game.perform(Action("talk", met))
    assert met in known_people(game.world, game.player.id)
    assert stranger not in known_people(game.world, game.player.id)
    record_fact(game.world, stranger, "robbed", met, place=game.place.id,
                variant=make_variant("robbed", stranger, met))
    fact = game.world.facts(predicate="robbed")[0]
    game.world.upsert_belief(game.player.id, fact.id, fact.variant, None, 0.5, 2, "told")
    assert stranger in known_people(game.world, game.player.id)
