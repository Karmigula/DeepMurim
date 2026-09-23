import random
import statistics

from systems.combat_core import INTENTS, Fighter
from systems.duel_sim import simulate
from systems.opponent import (
    COUNTER, PATTERN_WEIGHT, RECENT_WEIGHT, choose_intent, choose_output, gives_up, intent_weights, tendency,
)


def fighter(realm_mult=1.0, traits=("curious", "honest")):
    return Fighter("F", realm_mult, 0, "Palm", "palm", 1.0, 0.5, 1.0, 1.0, 0, 0, 10, 30.0, traits)


def random_player(rng, history):
    return rng.choice(INTENTS)


def always(intent):
    return lambda rng, history: intent


def rate(player, npc, strategy, n, seed=0):
    rng = random.Random(seed)
    results = [simulate(player, npc, strategy, rng) for _ in range(n)]
    return sum(r == "player" for r, _ in results) / n, statistics.mean(length for _, length in results)


def test_weights_follow_temper_habit_and_pattern():
    assert intent_weights(("hot-tempered",), [])["strike"] == 3.0
    assert intent_weights(("cunning",), [])["feint"] == 3.0
    after_strikes = intent_weights((), ["strike", "strike", "strike"])
    assert after_strikes["guard"] > 1 + 3 * RECENT_WEIGHT  # habit plus the strike-follows-strike pattern
    cycle = intent_weights((), ["strike", "feint", "guard", "probe", "strike"])
    assert cycle[COUNTER["feint"]] >= 1 + PATTERN_WEIGHT  # after a strike, this player feints
    assert intent_weights((), [], beast=True)["strike"] == 3.0


def test_choices():
    rng = random.Random(3)
    picks = [choose_intent(rng, {"strike": 1.0, "feint": 0.0, "guard": 0.0, "probe": 0.0}) for _ in range(20)]
    assert set(picks) == {"strike"}
    assert choose_output(("hot-tempered",), 30, 60, 10) == "all-in"
    assert choose_output(("hot-tempered",), 7, 60, 10) == "full"
    assert choose_output(("calm",), 30, 60, 10) == "steady"
    assert tendency(("cunning",)) == "feints and tricks" and tendency((), beast=True) == "direct strikes"


def test_giving_up_only_when_badly_hurt():
    rng = random.Random(1)
    assert gives_up(rng, ("cautious",), "tea seller", 20) is None
    outcomes = {gives_up(random.Random(s), ("cautious",), "tea seller", 70) for s in range(40)}
    assert outcomes == {None, "yield"}
    assert {gives_up(random.Random(s), (), "bandit", 70) for s in range(40)} == {None, "flee"}


def test_one_realm_gap_nearly_always_wins():
    weak, strong = fighter(1.0), fighter(3.0)
    assert rate(weak, strong, random_player, 200)[0] <= 0.05
    assert rate(strong, weak, random_player, 200)[0] >= 0.95


def test_equal_fighters_are_a_coin_toss_of_a_few_exchanges():
    win, length = rate(fighter(), fighter(), random_player, 400)
    assert 0.35 <= win <= 0.65
    assert 3 <= length <= 8


def test_no_fixed_strategy_dominates():
    for intent in INTENTS:
        assert rate(fighter(), fighter(), always(intent), 300)[0] <= 0.70, intent


def test_predictable_patterns_are_read():
    cycle = rate(fighter(), fighter(), lambda rng, h: INTENTS[len(h) % 4], 300)[0]
    alternate = rate(fighter(), fighter(), lambda rng, h: ("strike", "feint")[len(h) % 2], 300)[0]
    assert cycle <= 0.65 and alternate <= 0.65
