import time

import pytest

import systems.encounters as encounters
import systems.sky as sky
import systems.tournaments as T
import systems.wagers as wagers
import systems.world_events as W
from app import App
from config import Config
from engine.actions import Action
from engine.commands import parse
from engine.game import Game
from engine.lineage_page import lineage_lines
from engine.sheet import sheet_lines
from engine.tournament_page import bracket_lines, tournaments_lines
from narrate.outcomes import SUMMARIES
from systems import founding
from systems.beliefs import believe
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from world.events import commit
from world.gen.materialize import ensure_town
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


def texts(turn):
    return [t for t, _ in turn.lines]


def actions(turn):
    return [c.action for c in turn.all_choices]


def start(world, kind, town, data):
    commit(world, sky.start_events(world, kind, town, world.time, data))
    return W.index(world)[-1][W.ID]


def announced_assembly(game):
    import systems.events.grand_assembly as ga
    world, town = game.world, game.place.id
    occurrence = start(world, "grand_assembly", town, ga.start_data(world, town, 10, rng_for(1, "a")))
    world.set_time(world.entity(occurrence).data["ends"]["foretold"] + 1)
    return occurrence


def entered(game):
    body = load_body(game.world, game.player.id)
    body.realm = 2
    save_body(game.world, game.player.id, body)
    game.world.update_data(game.player.id, silver=500)
    occurrence = announced_assembly(game)
    game.perform(Action("register", occurrence))
    return occurrence


def to_day(game, occurrence, k):
    game.world.set_time(T.day_start(game.world.entity(occurrence), k))
    return game.perform(Action("look"))


def far_meet(world):
    import systems.events.dragon_phoenix as dp
    town = ensure_town(world, 3, 3, 0)
    return start(world, "dragon_phoenix", town, dp.start_data(world, town, 10, rng_for(1, "d"))), town


def hear_of(world, me, occurrence, town):
    variant = make_variant("phenomenon", town, None, place=place_name(world, town))
    variant.update(kind="dragon_phoenix", stage="foretold", reading=None)
    fact = record_fact(world, town, "phenomenon", None, place=town, variant=variant, spread=False,
                       extra={"occurrence": occurrence, "until": world.time + 40 * 4})
    believe(world, me, fact, variant, None, 0.7, 2, "gossip")


def test_the_tournaments_page_shows_what_you_have_seen_and_heard(game):
    world, me = game.world, game.player.id
    announced_assembly(game)
    far, town = far_meet(world)
    lines = texts(game.perform(Action("tournaments")))
    assert any("Grand Martial Assembly" in t and "registration open" in t and "not entered" in t for t in lines)
    assert not any("Dragon-Phoenix" in t for t in lines)  # nobody has told you of it
    hear_of(world, me, far, town)
    lines = texts(game.perform(Action("tournaments")))
    assert any("Dragon-Phoenix Meet" in t and world.entity(town).name in t for t in lines)


def test_f11_opens_the_tournaments_page(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Watcher", world_seed=5)
    app.handle_key("f11", "")
    assert any("Tournaments" in t for t, _ in app.last_turn.lines)


def test_the_bracket_as_you_know_it(game):
    world, me = game.world, game.player.id
    occurrence = announced_assembly(game)
    to_day(game, occurrence, 3)  # round 1 was fought on day 1
    lines = texts(game.perform(Action("bracket", occurrence)))
    assert any(t.startswith("Round 1, day 1") for t in lines) and sum(" wins" in t for t in lines) >= 8
    world.unrelate(me, "located_in")
    world.relate(me, ensure_town(world, 3, 3, 0), "located_in")  # far from the board, only what you heard
    away = [t for t, _ in bracket_lines(world, me, occurrence)]
    assert not any(" wins" in t for t in away)
    fact = world.facts(predicate="bested")[0]
    believe(world, me, fact.id, fact.variant, None, 0.7, 2, "gossip")
    away = [t for t, _ in bracket_lines(world, me, occurrence)]
    assert any("Heard" in t and world.entity(fact.subject).name in t for t in away)


def test_your_next_bout_is_named(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 1)
    call = T.player_call(world, me, game.place.id)
    lines = texts(game.perform(Action("bracket")))
    assert any("Your next bout" in t and world.entity(call[3]).name in t for t in lines)
    assert any("You: in round 1" in t for t in texts(game.perform(Action("tournaments"))))


def test_odds_and_a_typed_bet(game):
    world, me = game.world, game.player.id
    occurrence = announced_assembly(game)
    world.update_data(me, silver=500)
    to_day(game, occurrence, 1)
    assert any("odds board" in t for t in texts(game.perform(Action("odds"))))
    r, i, m = wagers.open_matches(world, occurrence)[0]
    action = parse(f"bet {world.entity(m['a']).name} 20", [])
    assert action == Action("bet_on", (world.entity(m["a"]).name.lower(), 20))
    game.perform(action)
    bet = world.entity(occurrence).data["data"]["bets"][-1]
    assert (bet["on"], bet["stake"], bet["round"], bet["match"]) == (m["a"], 20, r, i)
    assert any("Bet on whom" in t for t in texts(game.perform(Action("bet_on", ("nobody at all", 5)))))


def test_the_brief_names_the_round_and_the_favourite(game):
    occurrence = announced_assembly(game)
    game.perform(Action("look"))
    facts = " ".join(f for b in game.last_briefs if b.kind == "scene" for f in b.facts)
    assert "Grand Martial Assembly: registration is open" in facts
    to_day(game, occurrence, 1)
    facts = " ".join(f for b in game.last_briefs if b.kind == "scene" for f in b.facts)
    assert "round 1 today; the odds favour" in facts


def test_heralds_and_the_opening_day_are_told_once(game):
    occurrence = announced_assembly(game)
    assert any("Heralds cry" in t for t in texts(game.perform(Action("look"))))
    game.world.set_time(game.world.time + 1)
    assert not any("Heralds cry" in t for t in texts(game.perform(Action("look"))))
    assert any("opens today" in t for t in texts(to_day(game, occurrence, 1)))


def test_the_sheet_shows_titles_and_open_bets(game):
    world, me = game.world, game.player.id
    occurrence = announced_assembly(game)
    world.update_data(me, silver=500, titles=["Champion of the First Grand Martial Assembly"])
    to_day(game, occurrence, 1)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 20, me))
    text = " ".join(t for t, _ in sheet_lines(world, me))
    assert "Champion of the First Grand Martial Assembly" in text and "20 silver on" in text


def test_an_ancestors_titles_are_on_the_lineage_page(game):
    world, me, town = game.world, game.player.id, game.place.id
    grandfather = founding.make_person(world, "test:grandfather", town, occupation="monk", age=80,
                                       realm="first-rate")
    world.update_data(grandfather, dead=True, death={"cause": "age", "age": 80, "place": town},
                      titles=["Champion of the Second Grand Martial Assembly"])
    world.unrelate(grandfather, "located_in")
    world.update_data(me, ancestors=[grandfather])
    assert any("Champion of the Second Grand Martial Assembly" in t for t, _ in lineage_lines(world, me))


def test_every_tournament_event_you_take_part_in_has_a_journal_line(game):
    for kind in ("registered", "bond_refunded", "match_resolved", "tournament_won", "disqualified",
                 "lei_tai_challenged", "lei_tai_held", "bet_placed", "bet_settled", "watched", "noticed",
                 "defended", "asked_bookmaker", "exposed", "contest_rewarded", "contest_summarized"):
        assert kind in SUMMARIES, kind
    entered(game)
    assert any("Entered the Grand Martial Assembly" in t for t in texts(game.perform(Action("journal"))))


def test_typed_register_and_watch_find_the_tournament_here(game):
    world = game.world
    body = load_body(world, game.player.id)
    body.realm = 2
    save_body(world, game.player.id, body)
    world.update_data(game.player.id, silver=500)
    occurrence = announced_assembly(game)
    game.perform(parse("register", []))
    assert game.player.id in world.entity(occurrence).data["data"]["registered"]
    to_day(game, occurrence, 1)
    assert any("You watch" in t for t in texts(game.perform(parse("watch", []))))


def test_a_crowded_tournament_day_folds_under_more(game):
    world = game.world
    occurrence = entered(game)
    turn = to_day(game, occurrence, 1)
    assert len(turn.choices) <= 9
    assert {Action("watch", occurrence), Action("bookmaker", occurrence), Action("bout", occurrence)} <= set(actions(turn))


def test_a_posted_bracket_names_only_what_the_rules_allow(game):
    from debug.invariants import check_people
    world, me = game.world, game.player.id
    occurrence = entered(game)
    turn = to_day(game, occurrence, 1)
    assert check_people(game, turn) == []  # the herald's call names a stranger from the posted draw
    assert check_people(game, game.perform(Action("bracket", occurrence))) == []
    world.unrelate(me, "located_in")
    world.relate(me, ensure_town(world, 3, 3, 0), "located_in")
    world.update_data(occurrence, data={**world.entity(occurrence).data["data"], "registered": [], "entrants": []})
    from engine.tournament_page import posted_names
    assert posted_names(world, me) == set()  # away, and not in it: the board names no one to you


def test_the_pages_are_quick(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 9)  # the whole bracket is settled: every line has a result
    tournaments_lines(world, me)
    bracket_lines(world, me, occurrence)
    start_ = time.process_time()
    tournaments_lines(world, me)
    bracket_lines(world, me, occurrence)
    assert time.process_time() - start_ < 0.03
