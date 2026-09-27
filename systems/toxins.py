"""What poisons the body (phase 5b spec 4.2, 4.5): pill residue, and active poison.

Residue is a gauge a pill leaves behind; it dulls later pills and, high, risks deviation and meridian damage.
It fades as time passes (`world.body.settle`). An active poison spreads watch by watch while unsealed, doing
internal harm each day, until it is spent, sealed away, forced out, cured - or, for a strong one that lasts,
kills. Poisons run lazily with the body; the meta row `poisoned` lists the NPCs carrying one, so only they are
looked at for a poison's death.
"""

# The registry first: modules that fill it (pills, the poison path) may load while this one is still loading.
WOUND_HOOKS: list = []  # (world, hitter, target, form, hitter_body, target_body): a wound that poisons (5b)
ABSORB_HOOKS: list = []  # (world, person, body, grade, strength) -> (grade, strength): what a body lets in (5b)

import systems.lives as lives  # noqa: E402
import systems.world_clock as world_clock
from systems.bodies import load_body, save_body
from world.body import WATCHES_PER_DAY
from world.events import Event, effect
from world.seed import rng_for

DULL = 150.0            # a pill works at 1 - residue / 150
DEVIATION_AT, MERIDIAN_AT = 60.0, 90.0
DEVIATION_RISK, MERIDIAN_RISK = 15.0, 0.3
LETHAL_GRADE = 4        # a poison this strong kills if it outlasts realm + 2 days
SEAL_REALM, SEAL_WATCHES = 1, 4
FORCE_REALM, FORCE_QI = 3, 10.0


# --- residue -------------------------------------------------------------------------------------------

def dulling(body) -> float:
    return max(0.0, 1.0 - body.residue / DULL)


def leave_residue(body, grade: int, purity: float, rng) -> list[str]:
    """A pill's residue, and what a body already full of it risks (spec 4.5): the harms it did, in words."""
    before = body.residue
    body.residue = min(100.0, round(before + grade * (1 - purity) * 10, 3))
    harms = []
    if before > DEVIATION_AT and rng.random() < (before - DEVIATION_AT) / 40:
        body.deviation = min(100.0, body.deviation + DEVIATION_RISK)
        harms.append("deviation")
    if before > MERIDIAN_AT and rng.random() < MERIDIAN_RISK:
        open_ones = [m for m, v in body.meridians.items() if v.state == "open"]
        if open_ones:
            body.meridians[sorted(open_ones)[0]].state = "damaged"
            harms.append("meridian")
    return harms


# --- active poison ---------------------------------------------------------------------------------------

def poison(world, person: int, grade: int, strength: int, source: str) -> str:
    """Put a poison in someone's body; a resistance or immunity may let it pass. Returns what happened."""
    body = load_body(world, person)
    result = add_poison(world, person, body, grade, strength, source)
    save_body(world, person, body)
    return result


def add_poison(world, person: int, body, grade: int, strength: int, source: str) -> str:
    """The same, into a body already loaded (a duel's wound): the caller saves it."""
    if grade <= body.resist:
        return "resisted"
    for hook in ABSORB_HOOKS:  # the Myriad Poison Body's immunity, the poison path's conversion
        grade, strength = hook(world, person, body, grade, strength)
    if strength <= 0:
        return "absorbed"
    body.poisons = body.poisons + [{"grade": int(grade), "strength": int(strength), "days": 0.0,
                                    "at": world.time, "sealed_until": 0, "source": source}]
    if not world.entity(person).data.get("is_player"):
        listed = world.get_meta("poisoned") or []
        if person not in listed:
            world.set_meta("poisoned", listed + [person])
    return "poisoned"


def worst(body) -> dict | None:
    return max(body.poisons, key=lambda p: (p["grade"], p["strength"])) if body.poisons else None


def lethal(body) -> dict | None:
    """The poison that has outlasted this body: of grade 4 or more, past realm + 2 days (spec 4.2)."""
    return next((p for p in body.poisons if p["grade"] >= LETHAL_GRADE and p["days"] > body.realm + 2), None)


def seal_block(body, now: int) -> str | None:
    if not body.poisons:
        return "There is no poison in you."
    if body.realm < SEAL_REALM:
        return "You have not the qi to seal your own acupoints."
    if any((p.get("sealed_until") or 0) > now for p in body.poisons):
        return "Your acupoints are sealed already."
    return None


def seal_events(world, person: int, place) -> list[Event]:
    return [Event("acupoints_sealed", (person,), place, {"until": world.time + SEAL_WATCHES})]


@effect("acupoints_sealed")
def _sealed(world, event) -> None:
    body = load_body(world, event.actors[0])
    body.poisons = [{**p, "sealed_until": event.data["until"]} for p in body.poisons]
    save_body(world, event.actors[0], body)


def force_block(body) -> str | None:
    if not body.poisons:
        return "There is no poison in you."
    if body.realm < FORCE_REALM:
        return "Only a first-rate master can force a poison out."
    if body.qi < FORCE_QI:
        return "Your qi is too low to drive it out."
    return None


def force_events(world, person: int, place) -> list[Event]:
    body = load_body(world, person)
    target = worst(body)
    cleared = target["grade"] <= body.realm - 1
    return [Event("poison_forced", (person,), place, {"grade": target["grade"], "cleared": cleared})]


@effect("poison_forced")
def _forced(world, event) -> None:
    person, d = event.actors[0], event.data
    body = load_body(world, person)
    target = worst(body)
    if target is not None:
        rest = [p for p in body.poisons if p is not target]
        body.poisons = rest if d["cleared"] else rest + [{**target, "strength": max(1, target["strength"] // 2)}]
    body.qi = max(0.0, body.qi - FORCE_QI)
    save_body(world, person, body)
    _forget_if_clean(world, person, body)


def cure(world, person: int, grade: int) -> int:
    """An antidote of this grade: every poison of its grade or less is gone. Returns how many."""
    body = load_body(world, person)
    gone = [p for p in body.poisons if p["grade"] <= grade]
    body.poisons = [p for p in body.poisons if p["grade"] > grade]
    save_body(world, person, body)
    _forget_if_clean(world, person, body)
    return len(gone)


def _forget_if_clean(world, person: int, body) -> None:
    if not body.poisons:
        listed = world.get_meta("poisoned") or []
        if person in listed:
            world.set_meta("poisoned", [p for p in listed if p != person])


def death_events(world, person: int) -> list[Event]:
    """If a poison has outlasted this body: the death it brings (spec 4.2); else nothing."""
    body = load_body(world, person)
    if lethal(body) is None or world.entity(person).data.get("dead"):
        return []
    from systems.mortality import death_events as dying
    if world.entity(person).data.get("is_player"):
        return dying(world, person, "poisoned", None)
    return [Event("died", (person, person), lives.home(world, person), {"cause": "poisoned", "world": True})]


def season_hook(world, n: int) -> list[Event]:
    """The NPCs who carry a poison: those it has outlasted die; the clean leave the index."""
    events = []
    for person in list(world.get_meta("poisoned") or []):
        entity = world.entity(person)
        if entity is None or entity.data.get("dead"):
            world.set_meta("poisoned", [p for p in world.get_meta("poisoned") or [] if p != person])
            continue
        body = load_body(world, person)
        events += death_events(world, person)
        _forget_if_clean(world, person, body)
    return events


world_clock.SEASON_HOOKS.append(season_hook)


def days_to_death(body, poison_: dict) -> float | None:
    """How long the body has before this poison kills, if it can: for the sheet."""
    if poison_["grade"] < LETHAL_GRADE:
        return None
    left = body.realm + 2 - poison_["days"]
    return max(0.0, left) if poison_["strength"] / WATCHES_PER_DAY > left else None


def residue_rng(world, person: int, salt):
    return rng_for(world.world_seed, f"residue:{person}:{salt}")
