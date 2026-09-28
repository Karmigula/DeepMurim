"""Typed commands to Actions, matched against what the player can do right now.

The parser knows only global words and the current choices (shown and folded),
so every command the engine can take also has a number to press somewhere.
"""

import re

from engine.actions import Action, Choice

GLOBAL = {
    "look": Action("look"), "l": Action("look"), "journal": Action("journal"), "j": Action("journal"),
    "chronicle": Action("journal"), "help": Action("help"), "?": Action("help"),
    "bye": Action("farewell"), "farewell": Action("farewell"), "leave": Action("farewell"),
    "cultivate": Action("cultivate"), "meditate": Action("meditate"), "rest": Action("rest"),
    "breakthrough": Action("breakthrough"),
    "strike": Action("intent", "strike"), "feint": Action("intent", "feint"),
    "guard": Action("intent", "guard"), "probe": Action("intent", "probe"),
    "flee": Action("flee"), "run": Action("flee"), "yield": Action("yield_duel"), "surrender": Action("yield_duel"),
    "spare": Action("verdict", "spare"), "rob": Action("verdict", "rob"), "cripple": Action("verdict", "cripple"), "kill": Action("verdict", "kill"),
    "spar": Action("spar"), "challenge": Action("challenge"),
    "news": Action("news"), "rumours": Action("rumours"), "rumors": Action("rumours"), "gossip": Action("rumours"),
    "tell": Action("tell_menu"), "standing": Action("standing"), "factions": Action("standing"), "ledger": Action("ledger"), "lineage": Action("lineage"), "market": Action("market"), "prices": Action("prices"),
    "seek": Action("seek"), "swallow": Action("swallow"), "sky": Action("sky"),
    "rankings": Action("rankings"), "lists": Action("rankings"),
    "realms": Action("realms"), "secret realms": Action("realms"), "enter": Action("enter_realm"), "enter realm": Action("enter_realm"), "deeper": Action("delve_on"),
    "on": Action("delve_on"), "up": Action("delve_back"), "leave realm": Action("leave_realm"),
    "claim": Action("claim_seat"), "claim seat": Action("claim_seat"), "claim the seat": Action("claim_seat"),
    "search chambers": Action("search_chambers"), "search": Action("search_chambers"), "step down": Action("step_down"),
    "examine body": Action("examine_body"), "examine the body": Action("examine_body"),
    "gear": Action("inventory"), "inventory": Action("inventory"), "i": Action("inventory"),
    "smith": Action("smith"), "unwield": Action("put_away", "weapon"), "sheathe": Action("put_away", "weapon"),
    "alchemy": Action("alchemy"), "pills": Action("alchemy"), "gather": Action("gather"),
    "search for herbs": Action("gather"), "herbalist": Action("herbalist"), "seal": Action("seal"),
    "seal acupoints": Action("seal"), "force out": Action("force_out"), "force poison": Action("force_out"),
    "light furnace": Action("experiment"), "experiment": Action("experiment"), "empty furnace": Action("empty_furnace"),
    "guild": Action("guild"), "clinic": Action("clinic"), "physician": Action("clinic"), "doctors": Action("ask_doctor"),
    "ask after doctors": Action("ask_doctor"), "pill hall": Action("pill_hall"), "garden": Action("pill_hall"),
    "night": Action("night"), "nightfall": Action("nightfall"), "wait for night": Action("nightfall"),
    "bound": Action("bound_menu"), "read": Action("read_scroll"), "remedies": Action("remedies"),
    "crafts": Action("crafts"), "anvil": Action("anvil"), "forge": Action("anvil"), "meet": Action("meet"),
    "clear anvil": Action("clear_anvil"),
    "heart": Action("heart"), "respects": Action("pay_respects"), "face": Action("heart_trial", "face"),
    "bury": Action("heart_trial", "bury"), "turn back": Action("heart_trial", "turn_back"),
    "tournaments": Action("tournaments"), "tournament": Action("tournaments"), "bracket": Action("bracket"),
    "odds": Action("odds"), "bookmaker": Action("odds"), "register": Action("register"), "watch": Action("watch"),
    "wear mask": Action("wear_mask"), "mask": Action("wear_mask"), "put on mask": Action("wear_mask"),
    "remove mask": Action("remove_mask"), "unmask": Action("remove_mask"), "take off mask": Action("remove_mask"),
}
PREFIX_VERBS = {
    "talk": "talk", "speak": "talk", "go": "travel", "travel": "travel", "walk": "travel", "ask": ("ask", "ask_about", "news"),
    "meditate": "meditate", "practise": "practise", "practice": "practise", "train": "practise",
    "open": "open_meridian", "use": "use", "declare": "declare_for", "accuse": "accuse",
    "wield": "wield", "wear": "wield", "inspect": "inspect", "buy": ("buy_gear", "buy_herb"), "sell": "sell_gear",
    "taste": "taste", "refine": "refine", "add": "add_herb", "temper": "bathe",
    "read": "read_scroll", "draw": "draw_pill", "harvest": "harvest", "steal": "steal", "treat": ("heal", "physician_treat"),
    "feed": "feed_servant", "lay": "lay_formation", "forge": "forge", "swear": "swear_oath",
}
FILLER = {"to", "about", "with", "the"}
WORD = re.compile(r"[a-z0-9']+")
BET = re.compile(r"bet (?:on )?([a-z' -]+?) (\d+)")  # bet <fighter> <silver> (phase 4e)


def _words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def parse(text: str, choices: list[Choice], extra: list[Choice] = ()) -> Action | None:
    """Numbers index the visible `choices`; words also search `extra` (folded-away choices)."""
    cleaned = " ".join(text.split())[:200]
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered.isascii() and lowered.isdigit():
        n = int(lowered)
        return choices[n - 1].action if 1 <= n <= len(choices) else Action("unknown", cleaned)
    if lowered in GLOBAL:
        return GLOBAL[lowered]
    bet = BET.fullmatch(lowered)
    if bet:
        return Action("bet_on", (bet.group(1), int(bet.group(2))))
    head, _, rest = lowered.partition(" ")
    verbs = PREFIX_VERBS.get(head)
    verbs = (verbs,) if isinstance(verbs, str) else verbs
    wanted = [w for w in _words(rest) if w not in FILLER]
    if verbs is None or not wanted:
        return Action("unknown", cleaned)
    pool = [c for c in [*choices, *extra] if c.action.verb in verbs]
    pool = list({c.action: c for c in pool}.values())  # a choice may be both visible and extra
    exact = [c for c in pool if all(w in _words(c.label) for w in wanted)]
    prefix = [c for c in pool if all(any(lw.startswith(w) for lw in _words(c.label)) for w in wanted)]
    for matches in (exact, prefix):
        if len(matches) == 1:
            return matches[0].action
        if len(matches) > 1:
            return Action("ambiguous", tuple(matches))
    return Action("unknown", cleaned)
