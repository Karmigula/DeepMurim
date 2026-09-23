"""Duels in the world (phase 2 spec §9): fighters built from bodies, and the
events a fight is made of.

The arithmetic lives in combat_core and the opponent's mind in opponent.
Every exchange is decided here, stored whole in its event, and only applied
by the effect, so replays, the journal and the narrator all agree exactly.
"""

from dataclasses import dataclass, field

from systems.attitude import afraid
from systems.beliefs import apparent_to
from systems.bodies import load_body, save_body
from systems.combat_core import (
    ALL_IN_DEVIATION, BROKEN, DAMAGE_BASE, FORM_STATS_EXTRA, INJURY_THRESHOLD, INTENTS, MAX_HARM, QI_COST,
    Fighter, affordable, flee_chance, limbs_for, power, resolve, wound,
)
from systems.items import manuals_of
from systems.opponent import choose_intent, choose_output, gives_up, intent_weights, tendency
from systems.purse import silver_of
from systems.realms import REALMS, STAGES, realm_index, stage_of
from systems.techniques import (
    FORM_STATS, FORMS, compatibility, create_technique, generate, grade_mult, martial_arts, teach, usable,
)
from systems.time import advance
from world.body import REGULAR, add_injury, unhealed
from world.events import Event, Witness, effect
from world.gen.materialize import people_at
from world.seed import rng_for
import systems.facts  # noqa: E402,F401  (deeds become facts)

MODES = ("duel", "spar", "encounter", "test")
GENTLE_MODES = ("spar", "test")
SPAR_EXCHANGES = 3
TEST_EXCHANGES = 3
MAX_EXCHANGES = 30
GENTLE_SCALE = 0.5
FRAGMENT_CHANCE_PROBE = 0.3
FRAGMENT_CHANCE_SPAR = 0.5
MAX_FRAGMENTS = 12
FORM_BY_OCCUPATION = {
    "wandering swordsman": "sword", "hunter": "spear", "monk": "palm", "constable": "saber",
    "beggar": "staff", "blacksmith": "fist", "bandit": "saber",
}
TEACHER_CHANCE = {"wandering swordsman": 0.6, "monk": 0.5, "hunter": 0.2}
LEGS = ("left leg", "right leg")
VERDICTS = ("spare", "rob", "cripple", "kill")
BEAST_VERDICTS = ("spare", "kill")
HATEFUL = frozenset({"hatred", "grief", "wronged"})  # a foe who feels this leaves you for dead


@dataclass
class Duel:
    duel_id: int
    player: int
    opponent: int
    place: int
    mode: str
    exchange: int = 0
    harm: dict = field(default_factory=lambda: {"player": 0.0, "opponent": 0.0})
    technique: int | None = None
    opponent_technique: int | None = None
    output: str = "steady"
    history: list = field(default_factory=list)
    openings: list = field(default_factory=list)
    stage: str = "fighting"
    witnesses: list = field(default_factory=list)
    purpose: dict = field(default_factory=dict)
    revealed: str | None = None

    @classmethod
    def from_event(cls, event_id: int, event) -> "Duel":
        data = event.data
        player, opponent = event.actors
        return cls(
            event_id, player, opponent, event.place, data["mode"],
            technique=data["technique"], opponent_technique=data["opponent_technique"],
            openings=[data["opening"]] if data.get("opening") else [],
            witnesses=list(data["witnesses"]), purpose=dict(data.get("purpose") or {}),
        )


# --- who fights with what -----------------------------------------------------------

def ensure_npc_arts(world, person_id: int):
    """Every NPC knows at least one art; some are teachers. Seeded, created once."""
    person = world.entity(person_id)
    data = person.data
    if data.get("is_player") or data.get("beast") or data.get("arts_ready"):
        return martial_arts(world, person_id)
    key = person.seed_path or f"entity:{person_id}"
    rng = rng_for(world.world_seed, f"{key}/arts")
    realm = realm_index(data.get("realm", "mortal"))
    occupation = data.get("occupation", "")
    teacher = rng.random() < TEACHER_CHANCE.get(occupation, 0.0)
    with world.transaction():
        for i in range(rng.randint(1, 2) if teacher else 1):
            form = FORM_BY_OCCUPATION[occupation] if i == 0 and occupation in FORM_BY_OCCUPATION else rng.choice(FORMS)
            name, art = generate(rng, "martial", form=form, grade=max(1, min(6, realm + 1)))
            technique = create_technique(world, name, art)
            teach(world, person_id, technique, source="lineage", mastery=round(min(1.0, rng.uniform(0.2, 0.5) + 0.1 * realm), 3))
        world.update_data(person_id, arts_ready=True, teacher=teacher)
    return martial_arts(world, person_id)


def best_art(world, person_id: int):
    body = load_body(world, person_id)
    arts = [a for a in martial_arts(world, person_id) if usable(body, a.technique.data)]
    if not arts:
        return None
    return max(arts, key=lambda a: grade_mult(a.technique.data["grade"]) * (0.5 + a.mastery) * compatibility(body, a.technique.data))


def fighter_for(world, person_id: int, technique_id: int | None) -> Fighter:
    person = world.entity(person_id)
    body = load_body(world, person_id)
    beast = bool(person.data.get("beast"))
    art = None
    if not beast and technique_id is not None:
        art = next((a for a in martial_arts(world, person_id)
                    if a.technique.id == technique_id and usable(body, a.technique.data)), None)
    form = "claws" if beast else (art.form if art else "bare")
    stats = FORM_STATS.get(form) or FORM_STATS_EXTRA[form]
    stat = sum(body.physique[s] for s in stats) / len(stats)
    hurt = unhealed(body, world.time)
    limbs = limbs_for(form)
    return Fighter(
        name=person.name, realm_mult=REALMS[body.realm].multiplier, stage=STAGES.index(stage_of(body)),
        technique=art.name if art else None, form=form,
        grade_mult=grade_mult(art.technique.data["grade"]) if art else 1.0,
        mastery=art.mastery if art else 0.0,
        compat=compatibility(body, art.technique.data) if art else 1.0,
        body_fit=0.8 + 0.4 * (stat / 20),
        limb_injuries=sum(1 for i in hurt if i.location in limbs),
        leg_injuries=sum(1 for i in hurt if i.location in LEGS),
        agility=body.physique["agility"], qi=body.qi,
        traits=tuple(person.data.get("traits", ())), beast=beast,
        stance_favours=art.technique.data["stance"]["favours"] if art else None,
    )


def fragment_of(world, technique_id: int, rng) -> dict:
    technique = world.entity(technique_id)
    route = technique.data["route"]
    start = rng.randrange(max(1, len(route) - 1))
    return {"technique": technique.name, "form": technique.data["form"], "element": technique.data["element"],
            "segment": route[start:start + 2]}


# --- starting and refusing ----------------------------------------------------------

def accepts(world, npc_id: int, player_id: int, mode: str) -> bool:
    if afraid(world, npc_id, apparent_to(world, npc_id, player_id)):
        return False
    npc = world.entity(npc_id)
    traits = set(npc.data.get("traits", ()))
    rng = rng_for(world.world_seed, f"accept:{mode}:{npc_id}:{world.time}")
    if mode == "spar":
        return not (traits & {"cautious", "lazy"}) or rng.random() < 0.5
    if traits & {"proud", "hot-tempered"}:
        return True
    if realm_index(npc.data.get("realm", "mortal")) >= load_body(world, player_id).realm:
        return True
    return rng.random() < 0.5


def refusal_events(player: int, npc: int, place: int, mode: str, reason: str = "unwilling") -> list[Event]:
    return [Event("refused_duel", (player, npc), place, {"mode": mode, "reason": reason})]


def start_events(world, player: int, opponent: int, place: int, mode: str,
                 purpose: dict | None = None, opening: str | None = None) -> list[Event]:
    ensure_npc_arts(world, opponent)
    load_body(world, opponent)
    mine, theirs = best_art(world, player), best_art(world, opponent)
    witnesses = [p.id for p in people_at(world, place, exclude=player) if p.id != opponent]
    data = {
        "mode": mode, "technique": mine.technique.id if mine else None, "technique_name": mine.name if mine else None,
        "opponent_technique": theirs.technique.id if theirs else None,
        "opponent_technique_name": theirs.name if theirs else None,
        "witnesses": witnesses, "purpose": purpose or {}, "opening": opening,
    }
    return [Event("duel_started", (player, opponent), place, data)]


# --- one exchange --------------------------------------------------------------------

def _blow(target: str, damage: float, form: str, rng, gentle: bool) -> dict:
    hit = wound(form, damage, rng, spar=gentle)
    return {"target": target, "damage": round(damage, 2), "wound": list(hit) if hit else None}


def exchange_events(world, d: Duel, intent: str) -> list[Event]:
    n = d.exchange + 1
    rng = rng_for(world.world_seed, f"duel:{d.duel_id}:{n}")
    me = fighter_for(world, d.player, d.technique)
    them = fighter_for(world, d.opponent, d.opponent_technique)
    opponent = world.entity(d.opponent)
    gentle = d.mode in GENTLE_MODES
    scale = GENTLE_SCALE if gentle else 1.0
    data = {
        "duel": d.duel_id, "n": n, "player_intent": intent, "opponent_intent": None,
        "player_output": None, "opponent_output": None, "player_output_choice": d.output,
        "player_technique": d.technique, "player_technique_name": me.technique,
        "opponent_technique_name": them.technique, "blows": [], "openings": [], "reveals": [], "recover": [],
        "tendency": None, "qi_spent": {"player": 0, "opponent": 0}, "deviation_added": 0.0,
        "fled": None, "gave_up": None, "fragment": None, "stage": "fighting",
    }
    harm = dict(d.harm)
    if intent == "flee":
        data["fled"] = rng.random() < flee_chance(me, them, harm["player"])
        if not data["fled"]:
            chaser = power(them, "strike", "steady", harm["opponent"], False)
            runner = power(me, "guard", "steady", harm["player"], False)
            damage = DAMAGE_BASE * (chaser / max(runner, 1e-6)) ** 0.8 * rng.uniform(0.8, 1.2) * scale
            data["blows"].append(_blow("player", damage, them.form, rng, gentle))
    else:
        quitting = None if gentle else gives_up(rng, them.traits, opponent.data.get("occupation", ""), harm["opponent"], them.beast)
        if quitting:
            data["gave_up"] = quitting
        else:
            their_intent = choose_intent(rng, intent_weights(them.traits, d.history, them.beast))
            my_output = affordable(d.output, me.qi)
            their_output = choose_output(them.traits, them.qi, harm["opponent"], harm["player"])
            mine = power(me, intent, my_output, harm["player"], "player" in d.openings)
            theirs = power(them, their_intent, their_output, harm["opponent"], "opponent" in d.openings)
            result = resolve(intent, their_intent, mine, theirs, rng, scale)
            side = {"a": "player", "b": "opponent"}
            for blow in result.blows:
                form = them.form if blow.target == "a" else me.form
                data["blows"].append(_blow(side[blow.target], blow.damage, form, rng, gentle))
            data.update(
                opponent_intent=their_intent, player_output=my_output, opponent_output=their_output,
                openings=[side[s] for s in result.openings], reveals=[side[s] for s in result.reveals],
                recover=[side[s] for s in result.recover],
                qi_spent={"player": QI_COST[my_output], "opponent": QI_COST[their_output]},
                deviation_added=float(ALL_IN_DEVIATION) if my_output == "all-in" else 0.0,
            )
            if "player" in data["reveals"]:
                data["tendency"] = tendency(them.traits, them.beast)
                if d.opponent_technique is not None and rng.random() < FRAGMENT_CHANCE_PROBE:
                    data["fragment"] = fragment_of(world, d.opponent_technique, rng)
    for blow in data["blows"]:
        harm[blow["target"]] = min(MAX_HARM, harm[blow["target"]] + blow["damage"])
    data["harm_after"] = {side: round(value, 2) for side, value in harm.items()}
    ending = _ending(d, data, n)
    if ending == "verdict":
        data["stage"] = "verdict"
    events = [Event("exchange", (d.player, d.opponent), d.place, data, weight=0.2)]
    if isinstance(ending, tuple):
        events.append(_end_event(world, d, ending[0], ending[1], rng, data["harm_after"], n))
    return events


def _ending(d: Duel, data: dict, n: int):
    if data["fled"]:
        return ("fled", "fled")
    if data["gave_up"] == "flee":
        return ("escaped", "fled")
    mine, theirs = data["harm_after"]["player"], data["harm_after"]["opponent"]
    if d.mode == "spar":
        if any(b["damage"] >= INJURY_THRESHOLD for b in data["blows"]) or n >= SPAR_EXCHANGES:
            result = "spar_won" if theirs > mine else "spar_lost" if mine > theirs else "spar_even"
            return (result, "point" if n < SPAR_EXCHANGES else "limit")
        return None
    if d.mode == "test":
        if mine >= BROKEN:
            return ("failed", "broken")
        return ("passed", "limit") if n >= TEST_EXCHANGES else None
    if mine >= BROKEN:
        return ("lost", "broken")
    if theirs >= BROKEN or data["gave_up"] == "yield":
        return "verdict"
    return ("drawn", "exhausted") if n >= MAX_EXCHANGES else None


def apply_record(d: Duel, data: dict) -> None:
    """Advance the in-memory duel by one recorded exchange (also used to rebuild after a load)."""
    d.exchange = data["n"]
    d.harm = dict(data["harm_after"])
    d.openings = list(data["openings"])
    d.technique = data["player_technique"]
    d.output = data["player_output_choice"]
    d.stage = data["stage"]
    if data["player_intent"] in INTENTS:
        d.history.append(data["player_intent"])
    if data.get("tendency"):
        d.revealed = data["tendency"]


def active_duel(world, player_id: int) -> Duel | None:
    entries = world.chronicle_about(player_id, limit=80)  # newest first
    for entry in entries:
        if entry.kind == "duel_ended":
            return None
        if entry.kind == "duel_started":
            d = Duel.from_event(entry.id, entry)
            for later in reversed(entries):
                if later.kind == "exchange" and later.data.get("duel") == entry.id:
                    apply_record(d, later.data)
            return d
    return None


# --- endings --------------------------------------------------------------------------

def _cripple(rng) -> list:
    options = [["right arm", "fracture"], ["left arm", "fracture"], ["right leg", "fracture"],
               ["left leg", "fracture"], [rng.choice(REGULAR), "meridian"]]
    return rng.choice(options)


def npc_verdict(rng, opponent, player_silver: int, hateful: bool = False) -> tuple[str, int, list | None]:
    if opponent.data.get("beast"):
        return "spare", 0, None  # a beast only wants you gone
    traits = set(opponent.data.get("traits", ()))
    ruthless = opponent.data.get("occupation") == "bandit" or {"cunning", "greedy"} <= traits
    greedy = ruthless or "greedy" in traits
    amount = int(player_silver * rng.uniform(0.3, 1.0)) if greedy else 0
    if hateful:
        return "leave_for_dead", amount, None  # a grudge wants you broken (phase 3a spec 6.2)
    crippled = _cripple(rng) if ruthless and rng.random() < 0.25 else None
    return ("cripple" if crippled else "rob" if amount else "spare"), amount, crippled


def _end_event(world, d: Duel, result: str, reason: str, rng, harm: dict, exchanges: int,
               verdict: str | None = None) -> Event:
    opponent = world.entity(d.opponent)
    body = load_body(world, d.player)
    gap = realm_index(opponent.data.get("realm", "mortal")) - body.realm
    data = {
        "duel": d.duel_id, "mode": d.mode, "result": result, "reason": reason, "verdict": verdict, "by": None,
        "silver": 0, "crippled": None, "loot": [], "insight": 0.0, "life_and_death": False,
        "fragment": None, "purpose": d.purpose, "killed": False, "left_for_dead": False,
    }
    witnesses = []
    if result == "lost":
        hateful = any(m.feeling in HATEFUL for m in world.memories(d.opponent, about=d.player))
        chosen, amount, crippled = npc_verdict(rng, opponent, silver_of(world, d.player), hateful)
        data.update(verdict=chosen, by="opponent", silver=amount, crippled=crippled,
                    insight=5.0 * gap if gap > 0 else 0.0, left_for_dead=chosen == "leave_for_dead")
        feeling = "respect" if exchanges >= 4 or gap <= 0 else "contempt"
        witnesses.append(Witness(d.opponent, feeling, 0.5))
    elif result == "won":
        data["by"] = "player"
        if verdict in ("rob", "kill"):
            data["silver"] = silver_of(world, d.opponent)
            data["loot"] = [m.item.id for m in manuals_of(world, d.opponent)]
        if verdict == "cripple":
            data["crippled"] = _cripple(rng)
        data["insight"] = 5.0 * gap if gap > 0 else 1.0
        data["life_and_death"] = harm["player"] >= 60 or gap > 0
        feeling, weight, lasting = {
            "spare": ("grateful" if gap < 0 else "humiliated", 0.6, False),
            "rob": ("humiliated", 0.8, False),
            "cripple": ("hatred", 1.0, True),
            "kill": ("hatred", 1.0, True),
        }[verdict]
        witnesses.append(Witness(d.opponent, feeling, weight, lasting))
        data["killed"] = verdict == "kill"
    elif result.startswith("spar_"):
        data["insight"] = 3.0
        if d.opponent_technique is not None and rng.random() < FRAGMENT_CHANCE_SPAR:
            data["fragment"] = fragment_of(world, d.opponent_technique, rng)
        witnesses.append(Witness(d.opponent, "sparred", 0.3))
    elif result in ("passed", "failed"):
        witnesses.append(Witness(d.opponent, "respect" if result == "passed" else "contempt", 0.3))
    elif result == "fled":
        witnesses.append(Witness(d.opponent, "contempt", 0.4))
    witnesses += [Witness(w, "witnessed_duel", 0.2) for w in d.witnesses]
    return Event("duel_ended", (d.player, d.opponent), d.place, data, witnesses=tuple(witnesses))


def verdict_events(world, d: Duel, choice: str) -> list[Event]:
    beast = bool(world.entity(d.opponent).data.get("beast"))
    if d.stage != "verdict" or choice not in (BEAST_VERDICTS if beast else VERDICTS):
        return []
    if choice == "kill" and d.mode not in ("duel", "encounter"):
        return []
    rng = rng_for(world.world_seed, f"duel:{d.duel_id}:verdict")
    reason = "broken" if d.harm["opponent"] >= BROKEN else "yielded"
    events = [_end_event(world, d, "won", reason, rng, d.harm, d.exchange, verdict=choice)]
    if choice == "kill":
        events.append(Event("died", (d.player, d.opponent), d.place, {"cause": "killed"}))
    return events


def yield_events(world, d: Duel) -> list[Event]:
    rng = rng_for(world.world_seed, f"duel:{d.duel_id}:yield")
    result = {"spar": "spar_lost", "test": "failed"}.get(d.mode, "lost")
    return [_end_event(world, d, result, "yielded", rng, d.harm, d.exchange)]


# --- effects -----------------------------------------------------------------------------

def _add_fragment(world, player: int, fragment: dict) -> None:
    fragments = list(world.entity(player).data.get("fragments", [])) + [fragment]
    world.update_data(player, fragments=fragments[-MAX_FRAGMENTS:])


@effect("exchange")
def _exchange(world, event: Event) -> None:
    data = event.data
    ids = dict(zip(("player", "opponent"), event.actors))
    people = {side: world.entity(pid) for side, pid in ids.items()}
    arts = {"player": data["player_technique_name"], "opponent": data["opponent_technique_name"]}
    bodies = {side: load_body(world, pid) for side, pid in ids.items()}
    for blow in data["blows"]:
        if blow["wound"]:
            location, kind, severity = blow["wound"]
            hitter = "opponent" if blow["target"] == "player" else "player"
            weapon = "claws" if people[hitter].data.get("beast") else (arts[hitter] or "bare hands")
            add_injury(bodies[blow["target"]], location, kind, severity, world.time, f"{people[hitter].name}'s {weapon}")
    for side, body in bodies.items():
        body.qi = max(0.0, body.qi - data["qi_spent"][side]) + (2.0 if side in data["recover"] else 0.0)
    bodies["player"].deviation = min(100.0, bodies["player"].deviation + data["deviation_added"])
    for side, body in bodies.items():
        save_body(world, ids[side], body)
    if data["fragment"]:
        _add_fragment(world, ids["player"], data["fragment"])


@effect("duel_ended")
def _ended(world, event: Event) -> None:
    data = event.data
    player, opponent = event.actors
    if data["silver"]:
        payer, payee = (player, opponent) if data["by"] == "opponent" else (opponent, player)
        amount = min(data["silver"], silver_of(world, payer))
        world.update_data(payer, silver=silver_of(world, payer) - amount)
        world.update_data(payee, silver=silver_of(world, payee) + amount)
    if data["crippled"]:
        victim, culprit = (player, opponent) if data["by"] == "opponent" else (opponent, player)
        body = load_body(world, victim)
        location, kind = data["crippled"]
        add_injury(body, location, kind, 5, world.time, f"being crippled by {world.entity(culprit).name}", permanent=True)
        save_body(world, victim, body)
    if data.get("left_for_dead"):
        body = load_body(world, player)
        add_injury(body, "torso", "internal", 4, world.time, f"being left for dead by {world.entity(opponent).name}")
        save_body(world, player, body)
    for item in data["loot"]:
        world.unrelate(opponent, "owns", item)
        world.relate(player, item, "owns")
    if data["insight"] or data["life_and_death"]:
        body = load_body(world, player)
        body.insight += data["insight"]
        if data["life_and_death"] and "life_and_death_insight" not in body.flags:
            body.flags.append("life_and_death_insight")
        save_body(world, player, body)
    if data["fragment"]:
        _add_fragment(world, player, data["fragment"])
    advance(world, 1)
