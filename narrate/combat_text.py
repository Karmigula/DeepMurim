"""What the player is told about duels: only facts from the event data."""

from narrate.outcomes import cap, outcome, summary
from systems.combat_core import condition_of

YOU = {"strike": "strike", "feint": "feint", "guard": "guard", "probe": "probe for an opening"}
THEM = {"strike": "strikes", "feint": "feints", "guard": "guards", "probe": "probes for an opening"}
MODE_WORDS = {"duel": "a duel", "spar": "a friendly spar", "encounter": "a fight", "test": "a test of skill"}
GROUP = {"won": "won", "spar_won": "won", "passed": "won", "lost": "lost", "spar_lost": "lost", "failed": "lost"}


def _name(world, event) -> str:
    return world.entity(event.actors[1]).name


def _is_beast(world, event) -> bool:
    return bool(world.entity(event.actors[1]).data.get("beast"))


def _place_of(wound) -> str:
    return f"{wound[0]} meridian" if wound[1] == "meridian" else wound[0]


@outcome("duel_started")
def _started(world, event):
    d, name = event.data, _name(world, event)
    lines = [f"You face {name} in {MODE_WORDS[d['mode']]}."]
    lines.append(f"You will fight with the {d['technique_name']}." if d["technique_name"] else "You will fight bare-handed.")
    if d["opponent_technique_name"]:
        lines.append(f"{cap(name)} settles into the stance of the {d['opponent_technique_name']}.")
    return lines, {"mode": MODE_WORDS[d["mode"]]}


@outcome("exchange")
def _exchange(world, event):
    d, name = event.data, _name(world, event)
    lines = []
    if d["fled"] is True:
        lines.append("You break away and escape.")
    elif d["fled"] is False:
        lines.append(f"You try to flee, but {name} cuts you off.")
    elif d["gave_up"] == "yield":
        lines.append(f"{cap(name)} lowers their guard and yields.")
    elif d["gave_up"] == "flee":
        lines.append(f"{cap(name)} turns and flees.")
    else:
        lines.append(f"You {YOU[d['player_intent']]}; {name} {THEM[d['opponent_intent']]}.")
    beast = _is_beast(world, event)
    for blow in d["blows"][:2]:
        wound = blow["wound"]
        if blow["target"] == "opponent":
            art = d["player_technique_name"] or "bare hands"
            lines.append(f"Your {art} lands{' on their ' + _place_of(wound) if wound else ''}.")
        else:
            weapon = "claws" if beast else (d["opponent_technique_name"] or "blow")
            verb = "catch" if weapon == "claws" else "catches"
            lines.append(f"{cap(name)}'s {weapon} {verb} {'your ' + _place_of(wound) if wound else 'you'}.")
    mine, theirs = condition_of(d["harm_after"]["player"]), condition_of(d["harm_after"]["opponent"])
    lines.append(f"You are {mine}; {name} is {theirs}.")
    read = "player" in d["reveals"] and d["tendency"]
    if read and d["fragment"]:  # one line, so the four-line outcome limit never drops the fragment
        lines.append(f"You read their style (they favour {d['tendency']}) and glimpse something of the {d['fragment']['technique']}.")
    elif read:
        lines.append(f"You read their style: they favour {d['tendency']}.")
    elif d["fragment"]:
        lines.append(f"You glimpse something of the {d['fragment']['technique']}.")
    return lines, {"you": mine, "them": theirs}


@outcome("duel_ended")
def _ended(world, event):
    d, name = event.data, _name(world, event)
    result = d["result"]
    lines = {
        "won": [f"You have beaten {name}."], "lost": [f"{cap(name)} has beaten you."],
        "fled": ["You got away."], "escaped": [f"{cap(name)} got away."],
        "drawn": ["Neither of you can go on, and you part ways."],
        "spar_won": [f"You win the spar against {name}."], "spar_lost": [f"{cap(name)} wins the spar."],
        "spar_even": ["The spar ends even."], "passed": [f"You pass {name}'s test."],
        "failed": [f"You fail {name}'s test."],
    }[result]
    if d["by"] == "player":
        if d["verdict"] == "spare":
            lines.append("You let them go.")
        if d["verdict"] == "kill":
            lines.append(f"You kill {name}.")
        if d["silver"] or d["loot"]:
            loot = f" and {len(d['loot'])} manual{'s' if len(d['loot']) != 1 else ''}" if d["loot"] else ""
            lines.append(f"You take {d['silver']} silver{loot}.")
        if d["crippled"]:
            lines.append(f"You cripple {name}'s {_place_of(d['crippled'])} for good.")
    elif d["by"] == "opponent":
        if d["verdict"] == "spare":
            lines.append("They let you go.")
        if d["verdict"] == "leave_for_dead":
            lines.append("They leave you for dead.")
        if d["silver"]:
            lines.append(f"They take {d['silver']} silver from you.")
        if d["crippled"]:
            lines.append(f"They cripple your {_place_of(d['crippled'])} for good.")
    if d["life_and_death"]:
        lines.append("You have faced death and understood something about the martial way.")
    elif d["insight"]:
        lines.append("The fight taught you something.")
    if d["fragment"]:
        lines.append(f"You glimpsed a piece of the {d['fragment']['technique']}.")
    return lines, {"result": result, "grammar_key": f"duel_ended.{GROUP.get(result, 'even')}"}


@outcome("refused_duel", body_facts=False)
def _refused(world, event):
    if event.data.get("reason") == "afraid":
        return [f"{cap(_name(world, event))} backs away; they want no part of you."], {}
    what = "to spar" if event.data["mode"] == "spar" else "your challenge"
    return [f"{cap(_name(world, event))} refuses {what}."], {}


RESULT_WORDS = {
    "won": "Beat {other}.", "lost": "Was beaten by {other}.", "fled": "Fled from {other}.",
    "escaped": "{other} fled.", "drawn": "Fought {other} to exhaustion.",
    "spar_won": "Won a spar with {other}.", "spar_lost": "Lost a spar with {other}.",
    "spar_even": "Sparred evenly with {other}.", "passed": "Passed {other}'s test.", "failed": "Failed {other}'s test.",
}


@summary("duel_started")
def _started_line(world, entry, names, place, other):
    return f"Faced {other} in {MODE_WORDS[entry.data['mode']]}."


@summary("exchange")
def _exchange_line(world, entry, names, place, other):
    return f"Traded blows with {other}."


@summary("duel_ended")
def _ended_line(world, entry, names, place, other):
    if entry.data.get("killed"):
        return f"Killed {other}."
    return cap(RESULT_WORDS[entry.data["result"]].format(other=other))


@outcome("died", body_facts=False)
def _died(world, event):
    return [f"{cap(_name(world, event))} is dead."], {}


@summary("died")
def _died_line(world, entry, names, place, other):
    return f"{cap(other)} died by your hand."


@summary("refused_duel")
def _refused_line(world, entry, names, place, other):
    return f"{cap(other)} refused to fight."
