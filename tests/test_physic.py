import pytest

import systems.alchemy as A
import systems.encounters as encounters
import systems.herbs as H
import systems.lives as lives
import systems.physic as PY
import systems.toxins as X
from engine.game import Game
from systems import factions as F
from systems.attitude import attitude
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.law import SCHEMES
from systems.purse import silver_of
from world.body import add_injury
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=5000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:physic:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def hurt(world, person, severity=3, permanent=False):
    body = load_body(world, person)
    injury = add_injury(body, "left arm", "cut", severity, world.time, "a test", permanent=permanent)
    save_body(world, person, body)
    return injury.id


# --- the town physician ---------------------------------------------------------------------------------------

def test_the_physician_hastens_a_wound_threefold_for_silver(game):
    world, me, town = game.world, game.player.id, game.place.id
    injury = hurt(world, me, 3)
    left = next(i for i in load_body(world, me).injuries if i.id == injury).heals_at - world.time
    assert world.entity_by_seed(PY.physician_path(town)) is None
    assert PY.treat_block(world, me, injury, town) is None
    assert world.entity_by_seed(PY.physician_path(town)) is None  # asking makes no one
    commit(world, PY.treat_events(world, me, injury, town))
    after = next(i for i in load_body(world, me).injuries if i.id == injury).heals_at - world.time
    assert after == max(1, left // PY.FASTER)
    assert silver_of(world, me) == 5000 - PY.treat_price(3)
    doctor = world.entity_by_seed(PY.physician_path(town))
    assert doctor.data["occupation"] == "physician" and town in world.targets(doctor.id, "located_in")
    assert silver_of(world, doctor.id) >= PY.treat_price(3)  # paid, and met


def test_a_permanent_wound_is_beyond_the_physician(game):
    world, me, town = game.world, game.player.id, game.place.id
    injury = hurt(world, me, 5, permanent=True)
    assert PY.treat_block(world, me, injury, town) is not None


def test_the_physician_cures_a_weak_poison_but_not_a_strong_one(game):
    world, me, town = game.world, game.player.id, game.place.id
    X.poison(world, me, 2, 20, "a hidden needle")
    assert PY.cure_block(world, me, town) is None
    commit(world, PY.cure_events(world, me, town))
    assert not load_body(world, me).poisons and silver_of(world, me) == 5000 - PY.cure_price(2)
    X.poison(world, me, 5, 20, "a hidden needle")
    assert "no poison of yours" in PY.cure_block(world, me, town)


def test_reading_the_body_names_its_poisons(game):
    world, me, town = game.world, game.player.id, game.place.id
    X.poison(world, me, 3, 20, "a hidden needle")
    assert not load_body(world, me).poisons[0]["named"]
    commit(world, PY.read_events(world, me, town))
    assert load_body(world, me).poisons[0]["named"] and silver_of(world, me) == 5000 - PY.READ_PRICE


# --- famous doctors ---------------------------------------------------------------------------------------------

def test_a_doctor_wanders_their_block_and_is_made_on_the_first_ask(game):
    world, me, town = game.world, game.player.id, game.place.id
    here = world.entity(town).data
    block = PY.block_of(here["x"], here["y"])
    spec = PY.doctor_spec(world, block)
    assert spec == PY.doctor_spec(world, block) and spec["whim"] in PY.WHIMS
    assert spec["title"].startswith("the ") and " Doctor of " in spec["title"]
    assert world.entity_by_seed(PY.doctor_path(block)) is None
    commit(world, PY.ask_events(world, me, town))
    doctor = world.entity_by_seed(PY.doctor_path(block))
    assert doctor.name == spec["name"] and doctor.data["doctor"]["whim"] == spec["whim"]
    x, y, i = PY.seen_at(world, block, lives.current_season(world))
    where = world.targets(doctor.id, "located_in")[0]
    assert (world.entity(where).data["x"], world.entity(where).data["y"], world.entity(where).data["index"]) == (x, y, i)
    seen = world.entity(me).data["doctors_seen"][PY.doctor_path(list(block))]
    assert seen["season"] == lives.current_season(world)
    from systems.beliefs import known_people
    assert doctor.id in known_people(world, me)  # heard of, so named


def a_doctor(game, whim):
    world = game.world
    doctor = someone(game, f"doctor-{whim}", occupation="famous doctor", realm="first-rate",
                     doctor={"title": "the Test Doctor", "whim": whim, "home": [0, 0], "block": [0, 0]})
    return doctor


def test_a_doctor_cures_what_no_physician_can_on_their_terms(game):
    world, me, town = game.world, game.player.id, game.place.id
    doctor = a_doctor(game, "gold")
    X.poison(world, me, 5, 40, "a hidden needle")
    hurt(world, me, 5, permanent=True)
    body = load_body(world, me)
    body.meridians["Lung"].state = "severed"
    save_body(world, me, body)
    assert set(PY.doctor_cures(world, me)) >= {"poison", "meridian", "injury"}
    assert PY.terms_block(world, me, doctor, town) is None
    for what in ("poison", "meridian", "injury"):
        commit(world, PY.doctor_events(world, me, doctor, what, town))
    body = load_body(world, me)
    assert not body.poisons and body.meridians["Lung"].state == "open"
    assert not any(i.permanent for i in body.injuries)
    assert silver_of(world, me) == 5000 - 3 * PY.DOCTOR_GOLD


def test_the_whims_of_doctors(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    task = a_doctor(game, "task")
    assert "thousand-year" in PY.terms_block(world, me, task, town)
    H.make_herb(world, "ginseng", 3, me)
    assert PY.terms_block(world, me, task, town) is None
    righteous = a_doctor(game, "righteous")
    assert PY.terms_block(world, me, righteous, town) is None
    cult = next(f for f in F.ensure_roster(world) if world.entity(f).data["type"] == "demonic_cult")
    world.relate(me, cult, "member_of", 0, {"role": "member", "status": "member"})
    assert "orthodox" in PY.terms_block(world, me, righteous, town)
    odd = a_doctor(game, "eccentric")
    assert "go" in PY.terms_block(world, me, odd, town)
    body = load_body(world, me)
    body.physique["comprehension"] = 20
    save_body(world, me, body)
    commit(world, PY.go_events(world, me, odd, town))
    assert PY.terms_block(world, me, odd, town) is None


# --- the player as healer ---------------------------------------------------------------------------------------

def test_a_healing_pill_treats_the_wounded_and_they_are_grateful(game):
    world, me, town = game.world, game.player.id, game.place.id
    sick = someone(game, "sick")
    assert PY.heal_block(world, me, sick, town) == "Nothing ails them."
    hurt(world, sick, 3)
    assert "nothing fit" in PY.heal_block(world, me, sick, town)
    pill = A.make_pill(world, me, A.recipe_entity(world, "wood_healing"), 1, 0.8)
    assert PY.heal_block(world, me, sick, town) is None
    commit(world, PY.heal_events(world, me, sick, town))
    assert PY.ailment(world, sick) is None and pill not in world.targets(me, "owns")
    assert any(m.feeling == "grateful" for m in world.memories(sick, about=me))
    [fact] = world.facts(predicate="healed")
    assert fact.subject == me and fact.object == sick


def test_an_antidote_must_be_as_strong_as_the_poison(game):
    world, me, town = game.world, game.player.id, game.place.id
    sick = someone(game, "poisoned")
    X.poison(world, sick, 3, 40, "a bad well")
    A.make_pill(world, me, A.recipe_entity(world, "metal_antidote"), 2, 0.8)
    assert "nothing fit" in PY.heal_block(world, me, sick, town)
    A.make_pill(world, me, A.recipe_entity(world, "metal_antidote"), 3, 0.8)
    commit(world, PY.heal_events(world, me, sick, town))
    assert PY.ailment(world, sick) is None and sick not in (world.get_meta("poisoned") or [])


def test_herbs_treat_on_a_roll_of_the_alchemy_level(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    sick = someone(game, "herbs")
    hurt(world, sick, 2)
    for _ in range(2):
        H.make_herb(world, "willow bark", 0, me)
    assert "nothing fit" in PY.heal_block(world, me, sick, town)  # herbs one does not know are no remedy
    H.learn(world, me, ["willow bark"])
    monkeypatch.setattr(PY, "HEAL_BOUNDS", (0.0, 0.0))
    commit(world, PY.heal_events(world, me, sick, town))
    assert PY.ailment(world, sick) == "wound" and not H.herbs_of(world, me)


def test_five_healings_make_a_towns_healer_who_is_brought_the_sick(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    for n in range(PY.HEALER_AT):
        sick = someone(game, f"patient{n}")
        hurt(world, sick, 1)
        A.make_pill(world, me, A.recipe_entity(world, "wood_healing"), 1, 0.8)
        commit(world, PY.heal_events(world, me, sick, town))
    assert PY.healer_of(world, me) == [town]
    monkeypatch.setattr(PY, "PATIENT_CHANCE", 1.0)
    [brought] = PY.patient_events(world, me, town)
    commit(world, [brought])
    patient = world.entity(me).data["patient"]
    assert PY.ailment(world, patient) is not None and town in world.targets(patient, "located_in")


def test_the_hostile_will_not_be_treated(game):
    from world.events import Event, Witness
    world, me, town = game.world, game.player.id, game.place.id
    sick = someone(game, "hater")
    hurt(world, sick, 2)
    A.make_pill(world, me, A.recipe_entity(world, "wood_healing"), 1, 0.8)
    commit(world, [Event("slight", (me, sick), town, {}, witnesses=(Witness(sick, "hatred", 1.0),))])
    assert "will not" in PY.heal_block(world, me, sick, town)


# --- poison for hire ----------------------------------------------------------------------------------------------

def a_client(game, monkeypatch):
    world, me = game.world, game.player.id
    client = someone(game, "client", occupation="bandit", traits=["cunning", "greedy"])
    mark = someone(game, "mark")
    monkeypatch.setattr(PY, "CONTRACT_OFFER", 1.0)
    return client, mark


def test_only_the_unorthodox_who_know_you_poison_offer_a_contract(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    client, mark = a_client(game, monkeypatch)
    assert PY.contract_offer(world, client, me) is None
    from systems.beliefs import believe
    fact = record_fact(world, me, "poison_body", None, place=town, variant=make_variant("poison_body", me, None))
    believe(world, client, fact, make_variant("poison_body", me, None), None, 1.0, 0, "witness")
    offer = PY.contract_offer(world, client, me)
    assert offer["client"] == client and offer["target"] != client
    honest = someone(game, "honest")
    believe(world, honest, fact, make_variant("poison_body", me, None), None, 1.0, 0, "witness")
    assert PY.contract_offer(world, honest, me) is None


def test_a_hired_poisoning_kills_with_a_strong_poison_and_is_paid_for(game, monkeypatch):
    from systems.scheming import buy_poison_events  # noqa: F401  (the vial's effect)
    world, me, town = game.world, game.player.id, game.place.id
    client, mark = a_client(game, monkeypatch)
    offer = {"client": client, "target": mark, "silver": 200}
    commit(world, PY.contract_events(world, me, offer, town))
    assert "no poison" in PY.contract_poison_block(world, me, mark, town)
    vial = world.add_entity("treasure", "a vial of black lotus", {"kind": "poison", "value": 50, "used": False})
    world.relate(me, vial, "owns")
    assert PY.fee_block(world, me, client) == "The job is not done."
    assert PY.contract_poison_block(world, me, mark, town) is None
    monkeypatch.setattr(PY, "FIND_CHANCE", 1.0)
    commit(world, PY.contract_poison_events(world, me, mark, town))
    assert world.entity(mark).data.get("dead")
    assert world.facts(predicate="poisoned_for_hire") and "poisoned_for_hire" in SCHEMES  # traced: a crime
    world.update_data(client, silver=500)
    assert PY.fee_block(world, me, client) is None
    commit(world, PY.fee_events(world, me, client, town))
    assert silver_of(world, me) == 5200 and world.entity(me).data["contract"] is None


def test_a_contract_lapses_with_its_deadline(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    client, mark = a_client(game, monkeypatch)
    commit(world, PY.contract_events(world, me, {"client": client, "target": mark, "silver": 100}, town))
    assert not PY.contract_lapsed(world, me)
    world.set_time(world.time + PY.CONTRACT_DAYS * 4 + 1)
    assert PY.contract_lapsed(world, me)
    commit(world, PY.void_events(world, me, town))
    assert world.entity(me).data["contract"] is None


def test_those_who_hear_of_a_healing_think_better_of_the_healer(game):
    world, me, town = game.world, game.player.id, game.place.id
    sick = someone(game, "healed")
    hurt(world, sick, 2)
    onlooker = someone(game, "onlooker")
    before = attitude(world, onlooker, me).score
    A.make_pill(world, me, A.recipe_entity(world, "wood_healing"), 1, 0.8)
    commit(world, PY.heal_events(world, me, sick, town))
    assert attitude(world, onlooker, me).score > before
