"""Phase 5a's final review: the fixes, each pinned on the real path rather than a hand-made precondition."""
import pytest

import systems.armoury as A
import systems.duel as duel
import systems.encounters as encounters
import systems.famous as FW
import systems.gear as gear
import systems.provenance as provenance
import systems.spoils as SP
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.membership import left_events, set_membership
from world.events import Event, commit


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


def someone(game, tag, **data):
    base = {"occupation": "wandering swordsman", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:rev:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def the_sect(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    return sect, halls.seat_of(world, sect)


def join(world, person, sect, rank=1):
    world.relate(person, sect, "member_of", rank, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                   "secret": False})


def a_drawn_blade(game):
    world, me = game.world, game.player.id
    sect, seat = the_sect(world)
    join(world, me, sect)
    commit(world, A.draw_events(world, me, sect, "weapon", seat))
    return sect, seat, gear.item_in(world, me, "weapon").id


def test_your_own_carried_blade_breaks_into_a_broken_item(game, monkeypatch):
    monkeypatch.setattr(gear, "BREAK_CHANCE", 1.0)
    world, me = game.world, game.player.id
    if gear.weapon_of(world, me) is None:
        pytest.skip("a hand art")
    foe = someone(game, "foe", occupation="bandit")
    world.update_data(foe, gear={"weapon": 3, "armour": None})
    [started] = commit(world, duel.start_events(world, me, foe, game.place.id, "duel"))
    d = duel.Duel.from_event(started, world.chronicle_entry(started))
    events = duel.exchange_events(world, d, "strike")
    if events[0].data.get("broke") != "player":
        pytest.skip("they did not meet blade to blade")
    commit(world, events)
    item = gear.item_in(world, me, "weapon")
    assert item is not None and item.data["broken"] and item.data["owners"][0]["person"] == me
    assert gear.weapon_mult(world, me, item.data["form"]) == gear.UNARMED


def test_a_sect_knows_its_own_armoury_blade_without_a_tale(game):
    world, me = game.world, game.player.id
    sect, seat, item = a_drawn_blade(game)
    commit(world, left_events(world, me, sect, seat, "deserter"))
    member = someone(game, "member")
    join(world, member, sect)
    assert provenance.reactions(world, me, game.place.id, [member])["demands"] == member


def test_a_released_member_gives_the_armoury_back_its_blade(game):
    world, me = game.world, game.player.id
    sect, seat, item = a_drawn_blade(game)
    before = A.table(world, sect)
    commit(world, left_events(world, me, sect, seat, "released"))
    assert item not in world.targets(me, "owns") and not world.facts(predicate="stole", subject=me)
    grade = world.entity(item).data["grade"]
    assert A.table(world, sect)[grade] == before[grade] + 1


def test_an_expulsion_that_skips_the_leaving_event_is_still_theft(game):
    world, me = game.world, game.player.id
    sect, seat, item = a_drawn_blade(game)
    set_membership(world, me, sect, status="expelled")  # as a scheme or a murder laid bare expels directly
    assert world.entity(item).data["claimed_by"] == sect and world.facts(predicate="stole", subject=me)


def test_a_refused_demand_is_not_asked_again_while_you_stay(game):
    world, me = game.world, game.player.id
    sect, seat, item = a_drawn_blade(game)
    commit(world, left_events(world, me, sect, seat, "deserter"))
    member = someone(game, "member")
    join(world, member, sect)
    game.perform(Action("look"))
    if game.challenger is not None:  # a deserter's old sect-mates may call them out first
        game.perform(Action("answer_challenge", False))
    game.perform(Action("answer_demand", False))
    for _ in range(3):
        labels = [c.label for c in game.perform(Action("look")).all_choices]
        if game.challenger is not None:
            game.perform(Action("answer_challenge", False))
        assert not any(label.startswith("Refuse to give up") for label in labels)
    assert len(world.facts(predicate="kept_gear", subject=me)) == 1


def test_the_slain_can_be_stripped(game):
    world, me = game.world, game.player.id
    loser = someone(game, "slain")
    world.update_data(loser, gear={"weapon": 1, "armour": None, "form": "saber"})
    commit(world, [Event("died", (me, loser), game.place.id, {"cause": "killed"})])
    assert SP.take_block(world, me, loser, "weapon", game.place.id) is None
    commit(world, SP.take_events(world, me, loser, "weapon", game.place.id))
    assert any(i.data["owners"][0]["person"] == loser for i in gear.gear_items(world, me))


def test_a_famous_keeper_carries_no_second_blade(game):
    world = game.world
    keeper = someone(game, "keeper", realm="peak")
    FW.make_famous(world, "test:keeper", "sword", keeper, "made", "a test", game.place.id)
    assert gear.carried(world, keeper)["weapon"] is None  # the famous blade is all they carry


def test_you_are_told_when_a_blade_is_taken_from_you(game):
    world, me = game.world, game.player.id
    taker = someone(game, "taker")
    item = gear.make_item(world, "weapon", "sword", 1, me, "bought")
    lines = game._commit(gear.pass_events(world, me, taker, item, game.place.id, "won"))
    text = " ".join(t for t, _ in lines)
    assert "is yours" not in text and "from you" in text


def test_an_old_save_hero_still_carries_a_plain_blade(game):
    world, me = game.world, game.player.id
    form = duel.best_art(world, me).form
    world.update_data(me, gear=None)  # a hero from before phase 5a
    w = gear.weapon_of(world, me)
    if form in gear.WEAPON_FORMS:
        assert w is not None and w["grade"] == 0 and gear.weapon_mult(world, me, form) == 1.0
    else:
        assert w is None


def test_an_heir_keeps_their_own_blade_when_the_old_hero_carried_none(game):
    from systems import agendas
    from systems.succession import succession_events
    world, old = game.world, game.player.id
    heir = someone(game, "heir", age=20, realm="second-rate")
    agendas._pair(world, old, heir, "child")
    before = gear.seeded(world, heir)["weapon"]
    world.update_data(old, gear=None)
    commit(world, succession_events(world, old, heir))
    assert gear.carried(world, heir)["weapon"] == before


def test_no_one_is_declared_for_whom_you_never_heard_of(game, monkeypatch):
    import systems.succession_crisis as SC
    import systems.testament as T
    from tests.intrigue import still
    from tests.test_crisis_play import crisis_at_seat
    still(monkeypatch)  # a 4g crisis, as 4g's own tests stage it
    for knob in ("TRANSMIT_CHANCE", "EMERGE_CHANCE", "CAMP_FIND"):
        monkeypatch.setattr(T, knob, 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    stranger = world.add_entity("person", "Jin Unheard", {"occupation": "grand elder", "realm": "peak",
                                                          "traits": ["cunning"], "portrait": {"hair": 0, "face": 0, "robe": 0}},
                                "test:rev:unheard")
    world.relate(stranger, sect, "member_of", 4, {"role": "elder", "hall": None, "merit": 0, "status": "member",
                                                  "secret": False})
    crisis = SC.crisis_of(world.entity(occurrence.id))
    world.update_data(occurrence.id, data={**crisis, "claimants": crisis["claimants"] + [{"person": stranger,
                                                                                          "kind": "grand_elder"}]})
    labels = [c.label for c in game._general_extras()]
    assert "Declare for Jin Unheard" not in labels
    assert any(label.startswith("Declare for") for label in labels)  # the ones you know are still offered
