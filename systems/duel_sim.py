"""Headless duels for balance testing (phase 2 spec §9.5). No database, no events."""

from systems.combat_core import BROKEN, MAX_HARM, QI_COST, Fighter, affordable, power, resolve
from systems.opponent import choose_intent, choose_output, intent_weights


def simulate(player: Fighter, npc: Fighter, strategy, rng, max_exchanges: int = 40) -> tuple[str, int]:
    harm = {"a": 0.0, "b": 0.0}
    qi = {"a": player.qi, "b": npc.qi}
    openings: set[str] = set()
    history: list[str] = []
    for n in range(1, max_exchanges + 1):
        mine = strategy(rng, history)
        theirs = choose_intent(rng, intent_weights(npc.traits, history, npc.beast))
        my_output = affordable("steady", qi["a"])
        their_output = choose_output(npc.traits, qi["b"], harm["b"], harm["a"])
        qi["a"] = max(0.0, qi["a"] - QI_COST[my_output])
        qi["b"] = max(0.0, qi["b"] - QI_COST[their_output])
        mine_power = power(player, mine, my_output, harm["a"], "a" in openings)
        their_power = power(npc, theirs, their_output, harm["b"], "b" in openings)
        result = resolve(mine, theirs, mine_power, their_power, rng)
        openings = set(result.openings)
        for side in result.recover:
            qi[side] += 2
        for blow in result.blows:
            harm[blow.target] = min(MAX_HARM, harm[blow.target] + blow.damage)
        history.append(mine)
        if harm["a"] >= BROKEN and harm["b"] >= BROKEN:
            return "draw", n
        if harm["b"] >= BROKEN:
            return "player", n
        if harm["a"] >= BROKEN:
            return "npc", n
    return "draw", max_exchanges
