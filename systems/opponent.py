"""How an NPC fights (phase 2 spec §9.4).

An opponent leans on its temper, then reads the player: each of your last
three moves raises the weight of its counter, and so does the move you have
tended to play after the one you just played. Predictable fighters lose.
"""

from systems.combat_core import INTENTS, affordable, condition_of

COUNTER = {"strike": "guard", "guard": "feint", "feint": "probe", "probe": "strike"}
RECENT_WEIGHT = 0.75
PATTERN_WEIGHT = 3.0
TRAIT_WEIGHTS = {
    "hot-tempered": {"strike": 3.0}, "proud": {"strike": 3.0},
    "cautious": {"guard": 2.0, "probe": 2.0}, "cunning": {"feint": 3.0},
}
BEAST_WEIGHTS = {"strike": 3.0, "feint": 0.5, "guard": 1.0, "probe": 0.5}
TENDENCY_WORDS = {"strike": "direct strikes", "feint": "feints and tricks", "guard": "a patient guard", "probe": "testing probes"}


def _base(traits, beast: bool) -> dict[str, float]:
    if beast:
        return dict(BEAST_WEIGHTS)
    weights = {i: 1.0 for i in INTENTS}
    for trait in traits:
        for intent, weight in TRAIT_WEIGHTS.get(trait, {}).items():
            weights[intent] = max(weights[intent], weight)
    return weights


def intent_weights(traits, player_history, beast: bool = False) -> dict[str, float]:
    weights = _base(traits, beast)
    history = [i for i in player_history if i in COUNTER]
    for intent in history[-3:]:
        weights[COUNTER[intent]] += RECENT_WEIGHT
    if len(history) >= 2:
        last = history[-1]
        follows = [history[k + 1] for k in range(len(history) - 1) if history[k] == last][-4:]
        for following in follows:
            weights[COUNTER[following]] += PATTERN_WEIGHT / len(follows)
    return weights


def choose_intent(rng, weights: dict[str, float]) -> str:
    roll = rng.random() * sum(weights[i] for i in INTENTS)
    for intent in INTENTS:
        roll -= weights[intent]
        if roll < 0:
            return intent
    return INTENTS[-1]


def tendency(traits, beast: bool = False) -> str:
    weights = _base(traits, beast)
    return TENDENCY_WORDS[max(INTENTS, key=lambda i: weights[i])]


def choose_output(traits, qi: float, own_harm: float, their_harm: float) -> str:
    if "hot-tempered" in traits and own_harm > their_harm + 20:
        return affordable("all-in", qi)
    return affordable("steady", qi)


def gives_up(rng, traits, occupation: str, harm: float, beast: bool = False) -> str | None:
    if condition_of(harm) != "badly hurt":
        return None
    if (occupation == "bandit" or beast) and rng.random() < 0.3:
        return "flee"
    if ("cautious" in traits or "kind" in traits) and rng.random() < 0.4:
        return "yield"
    return None
