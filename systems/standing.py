"""How a faction sees someone (phase 3b spec 3.4): from what its towns have heard, never from truth."""

from dataclasses import dataclass

from systems import factions as F
from systems.factions import current_memberships
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
    return world._cached(("faction_knowledge", faction_id), lambda: _knowledge(world, faction_id))


def _knowledge(world, faction_id: int) -> list:
    faction = world.entity(faction_id)
    towns = [t for t in [faction.data.get("seat"), *faction.data.get("branches", [])] if t]
    best: dict = {}
    for town in towns:
        for belief, fact in world.known_facts(town):
            if fact.id not in best or belief.confidence > best[fact.id][0].confidence:
                best[fact.id] = (belief, fact)
    return list(best.values())


def _towns(world, faction_id: int) -> list[int]:
    faction = world.entity(faction_id)
    return [t for t in [faction.data.get("seat"), *faction.data.get("branches", [])] if t]


def knowledge_about(world, faction_id: int, subject: int):
    """(beliefs about `subject` and their known masks, the ids taken to be them): only what concerns them."""
    return world._cached(("faction_knowledge_about", faction_id, subject),
                         lambda: [_about(world, faction_id, subject)])[0]


def _about(world, faction_id: int, subject: int):
    towns = _towns(world, faction_id)
    true_id = true_identity(world, subject)
    if subject == true_id:
        seen = {true_id} | {f.subject for _, f in world.known_facts_about(towns, predicate="is", obj=true_id)}
    else:
        seen = {subject}
    best: dict = {}
    for belief, fact in world.known_facts_about(towns, actors=seen):
        if fact.id not in best or belief.confidence > best[fact.id][0].confidence:
            best[fact.id] = (belief, fact)
    return list(best.values()), seen


def seen_ids(world, faction_id: int, subject: int, know=None) -> set[int]:
    """Who the faction takes `subject` to be: the player plus any persona it knows is them."""
    know = knowledge(world, faction_id) if know is None else know
    true_id = true_identity(world, subject)
    if subject != true_id:
        return {subject}
    return {true_id} | {f.subject for _, f in know if f.predicate == "is" and f.object == true_id}


def believed_factions(world, faction_id: int, subject: int, know=None) -> set[int]:
    if know is None:
        know, seen = knowledge_about(world, faction_id, subject)
    else:
        seen = seen_ids(world, faction_id, subject, know)
    return current_memberships(know, seen)



def _factions_of(world, person) -> list[int]:
    return [fid for fid, _, data in F.memberships(world, person) if data.get("status", "member") == "member"]


def standing(world, faction_id: int, subject: int) -> Standing:
    faction = world.entity(faction_id)
    path = faction.data["path"]
    know, seen = knowledge_about(world, faction_id, subject)
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
        if fact.predicate == "stole" and target == faction_id:
            value, reason = -1.0, "you stole from us"  # an armoury (5a), a garden or a pill hall (5c)
        if fact.predicate == "sold_secret" and target == faction_id:  # phase 5c: a secret recipe sold to a rival
            value, reason = -1.5, "you sold our secrets"
        if fact.predicate in ("returned_gear", "kept_gear") and target == faction_id:  # phase 5a: what was ours
            value, reason = (1.0, "you gave back what was ours") if fact.predicate == "returned_gear" \
                else (-1.0, "you keep what is ours")
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
    from systems.lineage import inherited  # a faction judges an heir, in part, by the one before (phase 4b)
    for ancestor, share in inherited(world, faction_id, subject):
        old = standing(world, faction_id, ancestor).score
        if old:
            terms.append((share * old, "the one who came before you"))
    score = round(sum(v for v, _ in terms), 3)
    reasons = tuple(r for _, r in sorted(terms, key=lambda t: -abs(t[0]))[:2])
    return Standing(score, word_for(score), reasons)
