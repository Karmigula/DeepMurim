"""How a faction sees someone (phase 3b spec 3.4): from what its towns have heard, never from truth."""

from dataclasses import dataclass

from systems import factions as F
from systems.beliefs import true_identity
from systems.reputation import path_value

HARMFUL = frozenset({"killed", "crippled", "robbed", "left_for_dead", "defeated"})
GONE = frozenset({"expelled", "deserter", "spy"})


@dataclass(frozen=True)
class Standing:
    score: float
    word: str
    reasons: tuple[str, ...]


def word_for(score: float) -> str:
    if score >= 3:
        return "honoured"
    if score >= 1:
        return "welcome"
    if score > -1:
        return "neutral"
    if score > -3:
        return "distrusted"
    return "enemy"


def knowledge(world, faction_id: int) -> list:
    """What the faction's seat and branch towns believe: the surest version of each fact."""
    faction = world.entity(faction_id)
    towns = [t for t in [faction.data.get("seat"), *faction.data.get("branches", [])] if t]
    best: dict = {}
    for town in towns:
        for belief, fact in world.known_facts(town):
            if fact.id not in best or belief.confidence > best[fact.id][0].confidence:
                best[fact.id] = (belief, fact)
    return list(best.values())


def seen_ids(world, faction_id: int, subject: int, know=None) -> set[int]:
    """Who the faction takes `subject` to be: the player plus any persona it knows is them."""
    know = knowledge(world, faction_id) if know is None else know
    true_id = true_identity(world, subject)
    if subject != true_id:
        return {subject}
    return {true_id} | {f.subject for _, f in know if f.predicate == "is" and f.object == true_id}


def believed_factions(world, faction_id: int, subject: int, know=None) -> set[int]:
    know = knowledge(world, faction_id) if know is None else know
    seen = seen_ids(world, faction_id, subject, know)
    return {f.object for b, f in know if f.predicate == "member_of" and b.variant.get("actor") in seen}


def _factions_of(world, person) -> list[int]:
    return [fid for fid, _, data in F.memberships(world, person) if data.get("status", "member") == "member"]


def standing(world, faction_id: int, subject: int) -> Standing:
    faction = world.entity(faction_id)
    path = faction.data["path"]
    know = knowledge(world, faction_id)
    seen = seen_ids(world, faction_id, subject, know)
    terms: list[tuple[float, str]] = []
    for belief, fact in know:
        if belief.variant.get("actor") not in seen or fact.predicate in ("is", "member_of"):
            continue
        target = belief.variant.get("target")
        value, reason = 0.0, None
        if fact.predicate in HARMFUL and isinstance(target, int):
            theirs = _factions_of(world, target)
            if faction_id in theirs or any(F.stance(world, faction_id, g) >= 0.5 for g in theirs):
                value, reason = -1.0, "you harmed one of ours"
            elif any(F.stance(world, faction_id, g) <= F.HOSTILE for g in theirs):
                value, reason = 0.5, "you struck at our enemies"
        doctrine = path_value(world, fact.predicate, target)
        if path == "righteous" and doctrine:
            value += doctrine
            reason = reason or ("your righteous deeds" if doctrine > 0 else "your cruelty")
        elif path == "ruthless" and doctrine:
            value -= 0.5 * doctrine
            reason = reason or ("your ruthlessness" if doctrine < 0 else "your soft heart")
        value *= fact.weight * belief.confidence
        if value:
            terms.append((value, reason))
    for other in believed_factions(world, faction_id, subject, know):
        if other != faction_id and F.is_martial(world, other) and F.stance(world, faction_id, other) <= F.HOSTILE:
            terms.append((-2.0, f"you are of the {world.entity(other).name}"))
    true_id = true_identity(world, subject)
    mine = F.membership(world, true_id, faction_id) if subject == true_id else None
    if mine and mine[1].get("status", "member") == "member":
        terms.append((1.0, "you are one of us"))
    elif mine and mine[1].get("status") in GONE:
        terms.append((-3.0, "you betrayed them"))
    score = round(sum(v for v, _ in terms), 3)
    reasons = tuple(r for _, r in sorted(terms, key=lambda t: -abs(t[0]))[:2])
    return Standing(score, word_for(score), reasons)
