"""Cultivation actions (phase 2 spec §6).

Each builder computes the whole outcome from seeded randomness and puts it in
the Event's data; the effect advances time, then applies exactly that. So a
replay, the journal and the narrator's brief all see the same result.
"""

import systems.world_events as W
from systems import realms
from systems.bodies import load_body, save_body
from systems.techniques import compatibility, grade_mult, heart_method, known_arts, mastery_stage, practise_gain, set_known_completeness, set_mastery
from systems.time import advance
from world.body import EXTRAORDINARY, REGULAR, WATCHES_PER_DAY, add_injury, clone, max_qi, settle, unhealed
from world.events import Event, effect
from world.seed import rng_for

BASE_RATE = 0.015
MEDITATE_OPTIONS = {"day": 1, "week": 7, "month": 30, "season": 90}
SECLUSION_DAYS = 30
SENSE_QI_DAYS = 7
PRACTISE_DAYS = 7
OPEN_DAYS = 7
REST_DAYS = 7
BREAKTHROUGH_DAYS = 1
FORCE_CHANCE = 0.03
DEVIATION_LIMIT = 100
DEVIATION_AFTER = 40
CONSTITUTION_RATE = {"Dragon Vein Body": 1.25, "Myriad Poison Body": 1.1}
CONSTITUTION_ELEMENT = {"Nine Yin Body": "yin", "Pure Yang Body": "yang"}
CONSTITUTION_FORM = {"Heavenly Sword Bones": "sword"}
OPPOSITE = {"yin": "yang", "yang": "yin"}


def _rng(world, pid: int, what: str):
    return rng_for(world.world_seed, f"cultivate:{what}:{pid}:{world.time}")


def route_flow(body, route) -> float:
    flows = [body.meridians[m].flow if body.meridians[m].state in ("open", "scarred") else 0.0 for m in route]
    return sum(flows) / len(flows) if flows else 0.0


def energy_rate(body, heart_data: dict | None, days: int, now: int) -> float:
    """Years of internal energy gained per day of meditation."""
    if heart_data is None:
        grade, flow = 0.5, route_flow(body, REGULAR)  # crude breathing, no method
    else:
        grade, flow = grade_mult(heart_data["grade"]), route_flow(body, heart_data["route"])
    rate = BASE_RATE * grade * (body.physique["comprehension"] / 10) * (0.5 + body.purity) * flow
    if days >= SECLUSION_DAYS:
        rate *= 1.2
    if any(i.kind == "internal" for i in unhealed(body, now)):
        rate *= 0.5
    rate *= CONSTITUTION_RATE.get(body.constitution, 1.0)
    if heart_data is not None and CONSTITUTION_ELEMENT.get(body.constitution) == heart_data["element"]:
        rate *= 1.5
    return rate


def _deviation_from(body, data: dict, days: int) -> float:
    extra = days * max(0.0, 0.5 - compatibility(body, data)) * 2
    element = CONSTITUTION_ELEMENT.get(body.constitution)
    if element and data["element"] == OPPOSITE[element]:
        extra += days * 0.5
    return round(extra, 3)


def _discovers(body, trigger: str, data: dict | None = None, mastery_after: float = 0.0) -> str | None:
    if body.constitution is None or body.constitution_known:
        return None
    if trigger in ("breakthrough", "deviation"):
        return body.constitution
    if trigger == "practise" and mastery_after >= 0.34 and data is not None:
        if CONSTITUTION_FORM.get(body.constitution) == data["form"] or CONSTITUTION_ELEMENT.get(body.constitution) == data["element"]:
            return body.constitution
    return None


def _at_end(body, now: int, days: float):
    """The body as it will be when an action of `days` ends, before the action's own changes."""
    return settle(body, now + round(days * WATCHES_PER_DAY))


def _deviation_event(world, pid: int, place: int, end, added: float, route, cause: str, reveal: int | None = None) -> list[Event]:
    """`end` is the body as it will stand once the triggering action is applied (see _at_end)."""
    if end.deviation + added < DEVIATION_LIMIT:
        return []
    rng = _rng(world, pid, "deviation")
    candidates = [m for m in route if m in end.meridians and end.meridians[m].state in ("open", "damaged")]
    damaged = rng.sample(candidates, min(len(candidates), rng.randint(1, 2))) if candidates else []
    changes = [[m, end.meridians[m].state, "damaged" if end.meridians[m].state == "open" else "scarred"] for m in damaged]
    before = end.energy_years
    after = max(realms.REALMS[end.realm].threshold, before * 0.9)
    data = {"cause": cause, "damaged": damaged, "changes": changes,
            "energy_before": round(before, 6), "energy_after": round(after, 6), "energy_lost": round(before - after, 6),
            "discovered": _discovers(end, "deviation"), "reveal": reveal}
    return [Event("deviation", (pid,), place, data)]


def _floor_energy(body) -> None:
    """Keep energy inside the current realm and recompute the bottleneck."""
    body.energy_years = max(realms.REALMS[body.realm].threshold, body.energy_years)
    realms.add_energy(body, 0.0)


# --- meditation ---------------------------------------------------------------

def meditate_events(world, pid: int, place: int, days: int) -> list[Event]:
    body = load_body(world, pid)
    heart = heart_method(world, pid)
    heart_data = heart.technique.data if heart else None
    trial = clone(body)
    gained = realms.add_energy(trial, energy_rate(body, heart_data, days, world.time) * days
                               * W.factor(world, place, "cultivation"))  # a qi tide (phase 4d)
    deviation = _deviation_from(body, heart_data, days) if heart_data else 0.0
    data = {
        "days": days, "energy_gained": round(gained, 6),
        "sensed_qi": "sensed_qi" not in body.flags and body.meditated_days + days >= SENSE_QI_DAYS,
        "stage_before": realms.stage_of(body), "stage_after": realms.stage_of(trial),
        "reached_bottleneck": trial.bottleneck and not body.bottleneck,
        "deviation_added": deviation, "method": heart.name if heart else None,
    }
    route = heart_data["route"] if heart_data else list(REGULAR)
    cause = f"cultivating the {heart.name} against your body's grain" if heart else "breathing without a method"
    end = _at_end(body, world.time, days)
    realms.add_energy(end, gained)
    return [Event("cultivated", (pid,), place, data)] + _deviation_event(world, pid, place, end, deviation, route, cause)


@effect("cultivated")
def _cultivated(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    advance(world, data["days"] * WATCHES_PER_DAY)
    body = load_body(world, pid)
    realms.add_energy(body, data["energy_gained"])
    if data["sensed_qi"] and "sensed_qi" not in body.flags:
        body.flags.append("sensed_qi")
    body.meditated_days += data["days"]
    body.deviation = min(100.0, body.deviation + data["deviation_added"])
    body.qi = max_qi(body)
    save_body(world, pid, body)


# --- practice -----------------------------------------------------------------

def practise_events(world, pid: int, place: int, technique_id: int, days: int = PRACTISE_DAYS) -> list[Event]:
    body = load_body(world, pid)
    known = next((a for a in known_arts(world, pid) if a.technique.id == technique_id), None)
    if known is None or known.category != "martial":
        return []
    art = known.technique.data
    compat = compatibility(body, art)
    gain = practise_gain(days, body.physique["comprehension"], compat, art["grade"])
    if CONSTITUTION_FORM.get(body.constitution) == art["form"]:
        gain *= 1.5
    gain *= W.factor(world, place, "practice")  # a dao resonance (phase 4d)
    mastered = known.mastery >= 1.0 - 1e-9  # everything the art holds is learned
    at_cap = not mastered and known.mastery >= known.completeness - 1e-9  # a flawed art stops short
    after = min(known.completeness, known.mastery + gain)
    deviation = _deviation_from(body, art, days) + (days * 1.5 if at_cap else 0.0)
    data = {
        "technique": known.name, "technique_id": technique_id, "days": days,
        "mastery_before": round(known.mastery, 6), "mastery_after": round(after, 6),
        "stage_before": mastery_stage(known.mastery), "stage_after": mastery_stage(after),
        "compat": compat, "stalled": at_cap, "mastered": mastered, "deviation_added": round(deviation, 3),
        "insight_gained": round(days * 0.05 * body.physique["comprehension"] / 10, 4),
        "discovered": _discovers(body, "practise", art, after),
    }
    manual_lie = at_cap and known.source == "manual" and known.known_completeness > known.completeness + 1e-9
    if manual_lie:
        cause = f"following a manual of the {known.name} whose instructions are wrong"
    elif at_cap:
        cause = f"forcing the {known.name} beyond what it can give"
    else:
        cause = f"practising the {known.name} against your body's grain"
    end = _at_end(body, world.time, days)
    end.constitution_known = end.constitution_known or bool(data["discovered"])
    reveal = technique_id if manual_lie else None
    return [Event("practised", (pid,), place, data)] + _deviation_event(world, pid, place, end, deviation, art["route"], cause, reveal)


@effect("practised")
def _practised(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    advance(world, data["days"] * WATCHES_PER_DAY)
    set_mastery(world, pid, data["technique_id"], data["mastery_after"])
    body = load_body(world, pid)
    body.insight += data["insight_gained"]
    body.deviation = min(100.0, body.deviation + data["deviation_added"])
    if data["discovered"]:
        body.constitution_known = True
    save_body(world, pid, body)


# --- opening extraordinary meridians --------------------------------------------

def opening_requirement(body) -> float:
    return 2 + 3 * sum(1 for m in EXTRAORDINARY if body.meridians[m].state == "open")


def why_not_open(body, name: str) -> str | None:
    if name not in EXTRAORDINARY:
        return f"{name} is not an extraordinary meridian."
    if body.meridians[name].state != "blocked":
        return f"Your {name} meridian is already {body.meridians[name].state}."
    need = opening_requirement(body)
    if body.energy_years < need:
        return f"You need {realms.energy_words(need)} before you can force open another extraordinary meridian."
    return None


def open_meridian_events(world, pid: int, place: int, name: str, days: int = OPEN_DAYS) -> list[Event]:
    body = load_body(world, pid)
    if why_not_open(body, name):
        return []
    rng = _rng(world, pid, "open")
    before = body.meridians[name].opening
    after = min(1.0, before + days * 0.01 * body.physique["comprehension"] / 10)
    forced = rng.random() < FORCE_CHANCE
    victims = [m for m in REGULAR if body.meridians[m].state == "open"]
    victim = rng.choice(victims) if forced and victims else None
    deviation = 15.0 if forced else 0.0
    data = {
        "meridian": name, "days": days, "progress_before": round(before, 6), "progress_after": round(after, 6),
        "opened": after >= 1.0, "forced": forced, "forced_damage": victim, "deviation_added": deviation,
    }
    end = _at_end(body, world.time, days)
    if victim and end.meridians[victim].state == "open":
        end.meridians[victim].state = "damaged"
    return [Event("opening_meridian", (pid,), place, data)] + _deviation_event(
        world, pid, place, end, deviation, list(REGULAR), "forcing qi into a sealed meridian")


@effect("opening_meridian")
def _opening(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    advance(world, data["days"] * WATCHES_PER_DAY)
    body = load_body(world, pid)
    meridian = body.meridians[data["meridian"]]
    meridian.opening = data["progress_after"]
    if data["opened"]:
        meridian.state, meridian.flow, meridian.opening = "open", 0.3, 1.0
    if data["forced_damage"]:
        add_injury(body, data["forced_damage"], "meridian", 2, world.time, f"forcing open the {data['meridian']} meridian")
    body.deviation = min(100.0, body.deviation + data["deviation_added"])
    save_body(world, pid, body)


# --- rest ---------------------------------------------------------------------------

def rest_events(world, pid: int, place: int, days: int = REST_DAYS) -> list[Event]:
    body = load_body(world, pid)
    now, end = world.time, world.time + days * WATCHES_PER_DAY
    step = days * WATCHES_PER_DAY  # resting heals twice as fast: each rested day counts as two
    healed = [i.location for i in unhealed(body, now) if not i.permanent and i.heals_at - step <= end]
    return [Event("rested", (pid,), place, {"days": days, "healed": healed})]


@effect("rested")
def _rested(world, event: Event) -> None:
    pid, days, now = event.actors[0], event.data["days"], world.time
    body = load_body(world, pid)
    step = days * WATCHES_PER_DAY  # the rested days count twice
    for injury in body.injuries:
        if not injury.permanent and injury.heals_at is not None:
            injury.heals_at = max(now, injury.heals_at - step)
    for meridian in body.meridians.values():
        if meridian.state == "damaged" and meridian.heals_at is not None:
            meridian.heals_at = max(now, meridian.heals_at - step)
    body.deviation = max(0.0, body.deviation - 0.5 * days)  # on top of the usual fading
    save_body(world, pid, body)
    advance(world, days * WATCHES_PER_DAY)


# --- breakthrough -----------------------------------------------------------------

def breakthrough_events(world, pid: int, place: int) -> list[Event]:
    body = load_body(world, pid)
    if not body.bottleneck or body.realm >= realms.MAX_REALM:
        return []
    met, requirement = realms.requirement(body, known_arts(world, pid))
    rng = _rng(world, pid, "breakthrough")
    chance = realms.breakthrough_chance(body, met)
    chance = min(max(chance, 0.95), chance * W.factor(world, place, "breakthrough"))  # a qi tide (phase 4d)
    success = rng.random() < chance
    damaged = []
    if not success:
        heart = heart_method(world, pid)
        route = heart.technique.data["route"] if heart else list(REGULAR)
        candidates = [m for m in route if body.meridians[m].state == "open"]
        damaged = rng.sample(candidates, min(len(candidates), rng.randint(1, 2)))
    target = realms.REALMS[body.realm + 1].name
    data = {
        "success": success, "realm_before": body.realm, "realm_after": body.realm + (1 if success else 0),
        "target": target, "requirement": requirement, "met": met, "chance": chance,
        "damaged": damaged, "discovered": _discovers(body, "breakthrough"),
    }
    events = [Event("breakthrough", (pid,), place, data)]
    if not success:
        end = _at_end(body, world.time, BREAKTHROUGH_DAYS)
        for name in damaged:
            if end.meridians[name].state == "open":
                end.meridians[name].state = "damaged"
        end.energy_years *= 0.95
        _floor_energy(end)
        end.constitution_known = end.constitution_known or bool(data["discovered"])
        events += _deviation_event(world, pid, place, end, 30.0, damaged or list(REGULAR), "a failed breakthrough")
    return events


@effect("breakthrough")
def _breakthrough(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    advance(world, BREAKTHROUGH_DAYS * WATCHES_PER_DAY)
    body = load_body(world, pid)
    if data["success"]:
        body.realm += 1
        body.purity = min(1.0, round(body.purity + 0.05, 3))
        realms.add_energy(body, 0.0)
        body.qi = max_qi(body)
    else:
        for name in data["damaged"]:
            add_injury(body, name, "meridian", 3, world.time, f"the failed breakthrough to {data['target']}")
        body.energy_years *= 0.95
        _floor_energy(body)
        body.deviation = min(100.0, body.deviation + 30)
    if data["discovered"]:
        body.constitution_known = True
    save_body(world, pid, body)


@effect("deviation")
def _deviation(world, event: Event) -> None:
    pid, data = event.actors[0], event.data
    body = load_body(world, pid)
    for name, _before, after in data["changes"]:
        if after == "damaged":
            add_injury(body, name, "meridian", 3, world.time, data["cause"])
        else:
            body.meridians[name].state, body.meridians[name].heals_at = "scarred", None
    body.energy_years = data["energy_after"]
    _floor_energy(body)
    body.deviation = float(DEVIATION_AFTER)
    if data.get("reveal"):
        set_known_completeness(world, pid, data["reveal"])
    if data["discovered"]:
        body.constitution_known = True
    save_body(world, pid, body)
