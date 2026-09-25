"""Phase 4e final-review minors, each pinned by a test."""

import pytest

import systems.arena as arena
import systems.encounters as encounters
import systems.intrigue as intrigue
import systems.sky as sky
import systems.tournaments as T
import systems.wagers as wagers
import systems.world_events as W
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    for kind in ("grand_assembly", "dragon_phoenix"):
        monkeypatch.setitem(intrigue.CHANCES, kind, ())  # no dark plots unless a test asks for one


def actions(turn):
    return [c.action for c in turn.all_choices]


def start(world, kind, town, data):
    commit(world, sky.start_events(world, kind, town, world.time, data))
    return W.index(world)[-1][W.ID]


def assembly(game):
    import systems.events.grand_assembly as ga
    return start(game.world, "grand_assembly", game.place.id, ga.start_data(game.world, game.place.id, 10, rng_for(1, "a")))


def meet(game):
    import systems.events.dragon_phoenix as dp
    return start(game.world, "dragon_phoenix", game.place.id, dp.start_data(game.world, game.place.id, 10, rng_for(1, "d")))


def to_day(game, occurrence, k):
    game.world.set_time(T.day_start(game.world.entity(occurrence), k))
    sky.observe(game.world, game.place.id)


def announced(game, occurrence):
    game.world.set_time(game.world.entity(occurrence).data["ends"]["foretold"] + 1)


def second_rate(game, silver=500):
    body = load_body(game.world, game.player.id)
    body.realm = 2
    save_body(game.world, game.player.id, body)
    game.world.update_data(game.player.id, silver=silver)


def test_losers_of_a_watched_bout_remember_it(game):
    world, me = game.world, game.player.id
    occurrence = assembly(game)
    to_day(game, occurrence, 1)
    [resolved, watched] = arena.watch_events(world, occurrence, me)
    commit(world, [resolved, watched])
    d = resolved.data
    assert any(mem.event.actors and mem.event.actors[0] == d["winner"] for mem in world.memories(d["loser"]))


def test_betting_against_yourself_is_a_scandal_only_if_someone_saw(game):
    world, me = game.world, game.player.id
    occurrence = assembly(game)
    to_day(game, occurrence, 1)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    world.update_data(me, silver=500)
    bet = wagers.bet_events(world, occurrence, r, i, m["b"], 20, me)[0]
    assert bet.data["witnessed"]  # a crowded town saw it
    commit(world, [Event("bet_placed", bet.actors, bet.place, {**bet.data, "witnessed": False})])
    commit(world, [T.match_event(world.entity(occurrence), r, i, m["b"], me, "bout", 1)])  # as if you had fought and lost
    assert not world.facts(predicate="fixed")


def test_an_elder_takes_no_champion_who_already_has_a_master(game, monkeypatch):
    import systems.agendas as agendas
    import systems.events.sect_contest as sc
    monkeypatch.setattr(sc, "NOTICE_CHANCE", 1.0)
    world, town = game.world, game.place.id
    seat = next(s for s in sc.places(world, 10, rng_for(1, "p")) if sc.eligible(world, s, 10))
    occurrence = start(world, "sect_contest", seat, sc.start_data(world, seat, 10, rng_for(1, "s")))
    faction = world.entity(occurrence).data["data"]["faction"]
    champion = next(p for p in sc._disciples(world, faction) if float(world.entity(p).data.get("age", 30)) <= 30)
    old_master = founding.make_person(world, "test:old master", town, occupation="monk", age=60, realm="first-rate")
    agendas._pair(world, old_master, champion, "disciple")
    assert not [e for e in sc.rewards(world, world.entity(occurrence), champion) if e.kind == "apprenticed"]


def test_a_registrant_dropped_at_the_draw_has_their_bond_back(game):
    world, me = game.world, game.player.id
    second_rate(game, silver=150)
    occurrence = assembly(game)
    announced(game, occurrence)
    game.perform(Action("register", occurrence))
    assert silver_of(world, me) == 150 - T.BONDS["grand_assembly"]
    body = load_body(world, me)
    body.realm, body.energy_years = 1, 1.0  # a failed breakthrough cost them the realm the Assembly asks
    save_body(world, me, body)
    to_day(game, occurrence, 1)
    assert me not in world.entity(occurrence).data["data"]["entrants"] and silver_of(world, me) == 150


def test_two_tournaments_in_one_city_are_both_open_to_you(game):
    world = game.world
    second_rate(game)
    first = assembly(game)
    world.set_time(world.time + 32 * 4)  # the Meet is cried later, so both take names at once
    second = meet(game)
    world.set_time(world.entity(second).data["ends"]["foretold"] + 1)
    assert T.stage(world, first) == T.stage(world, second) == "announced"
    found = actions(game.perform(Action("look")))
    assert Action("register", first) in found and Action("register", second) in found


def test_registration_asks_no_sect_its_opinion_when_you_can_pay_the_bond(game, monkeypatch):
    world, me = game.world, game.player.id
    second_rate(game)
    occurrence = assembly(game)
    announced(game, occurrence)

    def asked(*args):
        raise AssertionError("every staffed sect was asked what it thinks of you")
    monkeypatch.setattr(T, "sponsor_of", asked)
    assert T.register_block(world, occurrence, me) is None


def test_the_brief_says_the_odds_favour_you(game, monkeypatch):
    from narrate.tournament_text import tournament_facts
    world, me = game.world, game.player.id
    second_rate(game)
    occurrence = assembly(game)
    announced(game, occurrence)
    game.perform(Action("register", occurrence))
    to_day(game, occurrence, 1)
    monkeypatch.setattr(T, "strengths", lambda world, town, people: {p: (9999.0 if p == me else 1.0) for p in people})
    assert any("the odds favour you" in f for f in tournament_facts(world, game.place.id, me))


def test_a_replayed_final_can_be_watched_and_bet_on(game, monkeypatch):
    monkeypatch.setitem(intrigue.CHANCES, "grand_assembly", (("raid", 1.0),))
    monkeypatch.setattr(intrigue, "RAID_DEATH", 0.0)
    world = game.world
    world.update_data(game.player.id, silver=500)
    occurrence = assembly(game)
    to_day(game, occurrence, 1)
    to_day(game, occurrence, 8)  # the raid
    world.set_time(T.day_start(world.entity(occurrence), 9))  # the replay, in the aftermath
    found = actions(game.perform(Action("look")))
    assert Action("watch", occurrence) in found and Action("bookmaker", occurrence) in found


def test_the_raids_cultist_is_gone_the_day_after(game, monkeypatch):
    monkeypatch.setitem(intrigue.CHANCES, "grand_assembly", (("raid", 1.0),))
    monkeypatch.setattr(intrigue, "RAID_DEATH", 0.0)
    world = game.world
    occurrence = assembly(game)
    to_day(game, occurrence, 1)
    to_day(game, occurrence, 8)
    cultist = world.entity(occurrence).data["data"]["intrigue"]["cultist"]
    assert cultist is not None and world.targets(cultist, "located_in")
    to_day(game, occurrence, 9)
    assert not world.targets(cultist, "located_in") and not T.alive(world, cultist)
