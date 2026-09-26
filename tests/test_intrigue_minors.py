"""Phase 4h's deferred minors, each pinned."""
import gc
import random
import time

import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.frames as R
import systems.legitimacy as L
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.scheming as S
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from tests.intrigue import still
from tests.test_crisis_contest import a_crisis, sway_all
from tests.test_crisis_play import crisis_at_seat, to_stage
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
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(L, "MANUAL_CHANCE", 0.0)
    monkeypatch.setattr(S, "NPC_FIND", 0.0)


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def stand_at(world, me, town):
    world.unrelate(me, "located_in")
    world.relate(me, town, "located_in")


def counting(monkeypatch, module, name):
    calls = {"n": 0}
    original = getattr(module, name)

    def counted(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(module, name, counted)
    return calls


def asks(game, npc):
    return [c.label for c in game._conversation_extras(game.world.entity(npc))]


def test_an_exposed_plotter_is_remembered_on_the_faction_not_found_by_a_scan(game):
    world = game.world
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    commit(world, P.made_events(world, "forgery", "stain:1", elder, sect, seat, target=sect,
                                clues=[P.clue("seal", elder)]))
    [plot] = P.plots_of(world, sect, ("forgery",))
    commit(world, P.exposed_events(world, plot, None, seat))
    assert world.entity(sect).data.get("stained") == [elder]
    for i in range(1500):
        world.add_entity("plot", f"old {i}", {"type": "spy", "plotter": elder, "faction": sect, "state": "cold",
                                               "clues": [], "known_by": []}, f"test:old:{i}")
    gc.collect()
    start = time.process_time()
    for _ in range(10):
        assert P.exposed_plotters(world, sect) == {elder}
    assert (time.process_time() - start) / 10 < 0.001


def test_a_leaders_death_adds_no_lookup_of_their_sects(game, monkeypatch):
    world = game.world
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    calls = counting(monkeypatch, F, "memberships")
    commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    assert calls["n"] == 4  # 4a-4g's own; the poison, the manual and the outsider share 4g's (they added three)


def test_a_claimants_proofs_are_weighed_once_per_count_of_the_camps(game, monkeypatch):
    world = game.world
    sect, seat, keeper, proud = a_crisis(game)
    crisis = SC.crisis_of(SC.live(world, sect))
    calls = counting(monkeypatch, C, "proofs")
    before = C.camps(world, crisis)
    assert calls["n"] == len(crisis["claimants"])
    monkeypatch.undo()
    assert C.camps(world, crisis) == before


def test_a_conversation_reads_the_open_plots_once(game, monkeypatch):
    world, me = game.world, game.player.id
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    stand_at(world, me, seat)
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    commit(world, P.made_events(world, "forgery", "talk:1", elder, sect, seat, target=sect,
                                clues=[P.clue("seal", elder)]))
    calls = counting(monkeypatch, P, "open_plots")
    game._conversation_extras(world.entity(elder))
    assert calls["n"] <= 1


def test_the_night_is_asked_of_anyone_at_the_seat_not_only_the_witness(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(M, "MURDER_CHANCE", 1.0)
    monkeypatch.setattr(M, "EXAMINE_BASE", 1.0)
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    plots = P.plots_of(world, sect, ("murder",))
    if not plots:
        pytest.skip("no motive in this world")
    [plot] = plots
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "witness")
    bystander = next(p for p in halls.staff_at(world, sect, seat) if p not in (witness, plot.data["plotter"]))
    assert "Ask about the night the master died" in asks(game, witness)
    assert "Ask about the night the master died" in asks(game, bystander)  # the choice gives no one away


def test_a_gift_is_asked_about_only_by_one_who_suspects_a_puppet(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    patron = next(i for i in F.ensure_roster(world) if i != sect)
    commit(world, U.puppet_events(world, occurrence, patron, proud, f"puppet:{occurrence.id}"))
    [plot] = P.plots_of(world, sect, ("puppet",))
    world.update_data(plot.id, gifted=[other])
    assert "Ask about the gift they took" not in asks(game, other)
    commit(world, P.found_events(world, world.entity(plot.id), "envoy", me, seat))  # now you know of a puppet
    assert "Ask about the gift they took" in asks(game, other)
    assert "Ask about the gift they took" in asks(game, keeper)  # every voter may be asked


def test_a_spy_can_be_asked_after_in_peacetime(game):
    world, me = game.world, game.player.id
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    stand_at(world, me, seat)
    [keeper] = halls.staff_at(world, sect, seat, roles=("keeper",))
    commit(world, U.spy_events(world, sect, of_type(world, "demonic_cult"), keeper, "peace:spy"))
    [plot] = P.plots_of(world, sect, ("spy",))
    assert SC.live(world, sect) is None
    seen = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "night")
    game.perform(Action("talk", seen))
    game.perform(Action("ask_clue", (seen, "night")))
    assert P.suspicions(world, me, sect).get(keeper) == ["night"]


def test_the_leader_knows_the_supreme_art_whole_and_an_old_heir_is_taught_in_time(game):
    world = game.world
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.update_data(sect, tier="great")
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    L.supreme_art(world, sect)
    assert L.art_known(world, leader, sect) == 1.0
    [keeper] = halls.staff_at(world, sect, seat, roles=("keeper",))
    world.update_data(sect, heir=keeper, heir_since=None)  # named before 4h
    n = next(s for s in range(lives.current_season(world), lives.current_season(world) + 8)
             if s % 4 == C.NAMING_SEASON)
    commit(world, L.teaching_events(world, n))
    assert world.entity(sect).data["heir_since"] == n
    commit(world, L.teaching_events(world, n + 4 * ((L.HEIR_LEARNS + 3) // 4)))
    assert L.art_known(world, keeper, sect) >= L.ART_KNOWN


def test_exposing_a_failed_frame_clears_no_one(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(me, silver=500)
    monkeypatch.setattr(S, "frame_chance", lambda world, player: 0.0)
    game.perform(Action("frame_rival", (occurrence.id, proud)))
    [plot] = P.plots_of(world, sect, ("frame",))
    commit(world, P.exposed_events(world, plot, other, seat))
    assert not world.facts(predicate="cleared", subject=proud)


def test_a_murderer_found_out_on_the_seat_is_replaced_at_once(game):
    world = game.world
    sect, seat, keeper, proud = a_crisis(game)
    occurrence = SC.live(world, sect)
    commit(world, M.murder_events(world, sect, proud, keeper, None, seat, random.Random(1)))
    [plot] = P.plots_of(world, sect, ("murder",))
    sway_all(world, occurrence, keeper)
    to_stage(world, occurrence, seat, "active")
    assert C.role_in(world, keeper, sect) == "leader"
    commit(world, P.exposed_events(world, world.entity(plot.id), proud, seat))
    leaders = C.staff(world, sect, ("leader",))
    assert keeper not in leaders and (leaders or SC.live(world, sect) is not None)


def test_far_away_a_puppets_claim_weighs_one_more(game, monkeypatch):
    world = game.world
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    elders = halls.staff_at(world, sect, seat, roles=("elder",))
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    patron = next(i for i in F.ensure_roster(world) if i != sect)
    plot = world.add_entity("plot", "a far puppet", {"type": "puppet", "plotter": elders[1], "patron": patron,
                                                     "target": sect, "faction": sect, "serves": elders[0],
                                                     "state": "open", "clues": [], "known_by": []}, "test:far:puppet")
    weighed = []
    original = random.Random.choices

    def recording(self, population, weights=None, **kw):
        weighed.append(dict(zip(population, weights)))
        return original(self, population, weights=weights, **kw)
    monkeypatch.setattr(random.Random, "choices", recording)
    standing = [{"person": e, "kind": "elder"} for e in elders[:2]]
    for season, backed in ((998, False), (999, True)):
        if backed:
            world.set_meta("open_plots", P.open_plots(world) + [plot])  # backed far away: no crisis played here
        commit(world, [SC.Event("crisis_summarised", (), seat, {"faction": sect, "season": season, "cause": "close",
                                                                 "leader": leader, "claimants": standing})])
    before, after = [w for w in weighed if set(w) == set(elders[:2])]
    assert after[elders[0]] == before[elders[0]] + 1 and after[elders[1]] == before[elders[1]]
