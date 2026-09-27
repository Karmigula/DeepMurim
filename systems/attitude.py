"""How someone feels about someone else (phase 3a spec §3.2): computed when asked, never stored.

Four things add up: what they remember (fading), what they have heard (judged
by their nature), the grief and grudges their family passed on (as memories),
and their temperament. The strongest term gives the reason, so a narrator can
say *why*.
"""

from dataclasses import dataclass

from systems.beliefs import appears_as, identities, knowledge_of, true_identity
from systems.factions import HOSTILE, current_memberships, memberships, stance
from systems.memory import effective_intensity
from systems.realms import realm_index

FEELING_VALUE = {
    "grateful": 1.0, "saved": 1.0, "respect": 0.6, "amused": 0.3,
    "sparred": 0.1, "conversed": 0.1, "met": 0.1, "curious": 0.1, "familiar": 0.1,
    "annoyed": -0.4, "contempt": -0.3, "humiliated": -0.8, "hatred": -1.5, "grief": -1.5, "wronged": -1.2,
}
JUDGEMENT = {
    "killed": -1.0, "crippled": -0.7, "robbed": -0.5, "defeated": 0.0, "spared": 0.4, "fled_from": -0.2,
    "lied_about": -0.6, "owns_manual": 0.0, "paid_off": -0.1, "left_for_dead": -0.8, "is": 0.0,
    "poisoner": -1.0, "murdered": -1.0, "framer": -0.8, "forger": -0.6, "spymaster": -0.6, "puppet_master": -0.5,
    "false_accusation": -0.3, "spy_exposed": -0.8,
    "poison_body": -0.4,  # phase 5b: folk keep away from a body that is poison
    "healed": 0.3,  # phase 5c: a healer is thought well of
    "poisoned_for_hire": -1.0,
}
HARSH = frozenset({"killed", "crippled", "robbed"})
HARM = frozenset({"killed", "crippled"})
REASONS = {
    "grateful": "you showed them mercy", "saved": "you saved them", "respect": "they respect your skill",
    "amused": "you amused them", "annoyed": "you annoyed them", "contempt": "they look down on you",
    "humiliated": "you humiliated them", "hatred": "you wronged them", "wronged": "you spread lies about them",
}
VERBS = {
    "killed": "killed", "crippled": "crippled", "robbed": "robbed", "spared": "spared", "defeated": "beat",
    "fled_from": "fled from", "lied_about": "spread lies about", "left_for_dead": "left", "paid_off": "paid off",
}


@dataclass(frozen=True)
class Attitude:
    score: float
    word: str
    reason: str | None


def word_for(score: float) -> str:
    if score >= 1.0:
        return "warm"
    if score >= 0.3:
        return "friendly"
    if score > -0.3:
        return "neutral"
    if score > -1.0:
        return "wary"
    if score > -2.0:
        return "hostile"
    return "hateful"


def is_bandit(entity) -> bool:
    return entity is not None and (entity.data.get("occupation") == "bandit" or entity.data.get("roamer_kind") == "bandit")


def judgement(world, predicate: str, target_id, traits: set, weight: float) -> float:
    """How bad (or good) a deed seems to someone of these traits."""
    value = JUDGEMENT.get(predicate, 0.0)
    target = world.entity(target_id) if isinstance(target_id, int) else None
    if predicate == "killed" and target is not None:
        if target.data.get("beast"):
            value = 0.2
        elif is_bandit(target):
            value = -0.5
    if predicate == "robbed" and is_bandit(target):
        value = -0.3
    if predicate in HARSH and value < 0:
        if traits & {"kind", "honest"}:
            value *= 2
        elif traits & {"greedy", "cunning"}:
            value *= 0.5
    if predicate == "defeated" and "proud" in traits and weight > 0.5:
        value += 0.2  # the proud respect whoever beats a stronger fighter
    return value


def _role(world, owner: int, other) -> str | None:
    for kin, _, data in world.relations_from(owner, "kin_of"):
        if kin == other:
            return data.get("role")
    return None


def _memory_reason(world, owner: int, memory) -> str | None:
    event = memory.event
    if memory.feeling == "grief":
        role = _role(world, owner, event.actors[1] if len(event.actors) > 1 else None)
        return f"you killed their {role}" if role else "you killed someone dear to them"
    if memory.inherited_from is not None:
        return "their family has not forgotten what you did"
    if event.kind == "duel_ended" and event.data.get("verdict") == "cripple" and owner in event.actors[1:]:
        return "you crippled them"
    return REASONS.get(memory.feeling)


def _belief_reason(world, variant: dict) -> str | None:
    predicate = variant.get("predicate")
    verb = VERBS.get(predicate)
    if verb is None:
        return None
    if predicate == "killed" and variant.get("soft"):
        verb = "nearly killed"
    target = world.entity(variant["target"]) if isinstance(variant.get("target"), int) else None
    whom = target.name if target else "someone"
    tail = " for dead" if predicate == "left_for_dead" else ""
    where = f" in {variant['place']}" if variant.get("place") else ""
    return f"heard you {verb} {whom}{tail}{where}"


def _inherited_terms(world, npc_id: int, heir: int, weight: float, now: int, depth: int = 0) -> list:
    """Memories of an heir's forebears, halving with each generation back (phase 4b spec 6)."""
    from systems.lineage import inherited
    out = []
    for ancestor, share in inherited(world, npc_id, heir):
        carried = weight * share
        for memory in world.memories(npc_id, about=ancestor):
            value = FEELING_VALUE.get(memory.feeling, 0.0) * effective_intensity(memory, now) * carried
            if value:
                out.append((value, "they remember the one who came before you"))
        if depth < 8:
            out += _inherited_terms(world, npc_id, ancestor, carried, now, depth + 1)
    return out


def attitude(world, npc_id: int, subject_id: int) -> Attitude:
    npc = world.entity(npc_id)
    traits = set(npc.data.get("traits", ()))
    true_id = true_identity(world, subject_id)
    now = world.time
    terms: list[tuple[float, str | None]] = []
    for memory in world.memories(npc_id, about=true_id):
        if appears_as(world, npc_id, memory.event, true_id) != subject_id:
            continue
        value = FEELING_VALUE.get(memory.feeling, 0.0) * effective_intensity(memory, now)
        if value:
            terms.append((value, _memory_reason(world, npc_id, memory)))
    seen = identities(world, npc_id, true_id) if subject_id == true_id else {subject_id}
    best: dict[int, tuple[float, str | None]] = {}
    mine = [fid for fid, _, d in memberships(world, npc_id) if d.get("status", "member") == "member"]
    heard = knowledge_of(world, npc_id)
    still_of = current_memberships(heard, seen) if mine else set()
    for belief, fact in heard:
        if belief.variant.get("actor") not in seen or fact.object == npc_id:
            continue  # things done to them are already in their memories
        if fact.predicate == "guild_rank":  # phase 5c: an alchemist's rank, the highest one heard
            value = 0.05 * belief.variant.get("rank", 0) * belief.confidence
            if value > best.get(-1, (0.0, None))[0]:
                best[-1] = (value, "they respect a ranked alchemist")
            continue
        if fact.predicate == "member_of":  # enemies by association (phase 3b spec 3.4)
            if fact.object not in still_of:
                continue
            worst = min((stance(world, f, fact.object) for f in mine), default=0.0)
            if worst <= HOSTILE and fact.id not in best:
                best[fact.id] = (-abs(worst) * belief.confidence, f"you are of the {world.entity(fact.object).name}")
            continue
        value = judgement(world, fact.predicate, belief.variant.get("target"), traits, fact.weight) \
            * belief.confidence * fact.weight
        if value and (fact.id not in best or abs(value) > abs(best[fact.id][0])):
            best[fact.id] = (value, _belief_reason(world, belief.variant))
    terms += list(best.values())
    if subject_id == true_id:  # behind a mask, no one sees whose heir you are
        terms += _inherited_terms(world, npc_id, true_id, 1.0, now)
    if "kind" in traits:
        terms.append((0.2, None))
    if "hot-tempered" in traits:
        terms.append((-0.1, None))
    if subject_id != true_id:
        terms.append((-0.2, "you hide your face"))
    score = round(sum(value for value, _ in terms), 3)
    reasons = sorted(((abs(value), reason) for value, reason in terms if reason), key=lambda p: -p[0])
    return Attitude(score, word_for(score), reasons[0][1] if reasons else None)


def afraid(world, npc_id: int, subject_id: int) -> bool:
    """Weaker than the subject is believed to be, and has heard they kill or cripple."""
    npc = world.entity(npc_id)
    true_id = true_identity(world, subject_id)
    seen = identities(world, npc_id, true_id) if subject_id == true_id else {subject_id}
    harmful, believed = False, 0
    for belief, fact in knowledge_of(world, npc_id):
        if belief.variant.get("actor") not in seen:
            continue
        harmful = harmful or fact.predicate in HARM
        if fact.predicate in ("defeated", "killed", "crippled") and belief.variant.get("realm"):
            believed = max(believed, realm_index(belief.variant["realm"]))
    for memory in world.memories(npc_id, about=true_id):
        if memory.event.kind == "duel_ended" and appears_as(world, npc_id, memory.event, true_id) == subject_id:
            believed = max(believed, realm_index(world.entity(true_id).data.get("realm", "mortal")))
    return harmful and realm_index(npc.data.get("realm", "mortal")) < believed
