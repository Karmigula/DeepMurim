"""What a town thinks of someone (phase 3a spec §9), read only from that town's gossip pool."""

from dataclasses import dataclass

from systems.attitude import is_bandit
from systems.beliefs import identities, true_identity
from world.seed import rng_for

EPITHET_RENOWN = 6.0
RENOWN_WORDS = ((2.0, "little known"), (6.0, "known"), (15.0, "renowned"))
PATH_VALUE = {"crippled": -0.7, "spared": 0.5, "defeated": 0.0, "fled_from": -0.2, "lied_about": -0.5,
              "paid_off": -0.1, "left_for_dead": -0.8, "owns_manual": 0.0, "seized": -0.8}
ADJECTIVES = {
    "righteous": ("Jade", "Azure", "White", "Upright"),
    "ruthless": ("Crimson", "Blood", "Black", "Iron"),
    "hard to read": ("Wandering", "Grey", "Silent"),
}
FORM_NOUNS = {"fist": "Fist", "palm": "Palm", "sword": "Sword", "saber": "Blade", "spear": "Spear", "staff": "Staff"}


@dataclass(frozen=True)
class Reputation:
    renown: float
    word: str
    path: str
    epithet: str | None


def renown_word(renown: float) -> str:
    if renown <= 0:
        return "unknown"
    for limit, word in RENOWN_WORDS:
        if renown < limit:
            return word
    return "famous"


def path_value(world, predicate: str, target_id) -> float:
    target = world.entity(target_id) if isinstance(target_id, int) else None
    if predicate == "killed":
        if target is not None and target.data.get("beast"):
            return 0.3
        return 1.0 if is_bandit(target) else -1.0
    if predicate == "robbed":
        return 0.2 if is_bandit(target) else -0.6
    return PATH_VALUE.get(predicate, 0.0)


def _own_reputation(world, town_id: int, subject_id: int) -> Reputation:
    true_id = true_identity(world, subject_id)
    seen = identities(world, town_id, true_id) if subject_id == true_id else {subject_id}
    best: dict = {}
    for belief, fact in world.known_facts(town_id):
        if belief.variant.get("actor") not in seen or fact.predicate == "is":
            continue
        if fact.id not in best or belief.confidence > best[fact.id][0].confidence:
            best[fact.id] = (belief, fact)
    renown = round(sum(f.weight * b.confidence for b, f in best.values()), 3)
    if renown <= 0:
        return Reputation(0.0, "unknown", "hard to read", None)
    lean = sum(path_value(world, f.predicate, b.variant.get("target")) * f.weight * b.confidence
               for b, f in best.values()) / renown
    path = "righteous" if lean >= 0.3 else "ruthless" if lean <= -0.3 else "hard to read"
    epithet = None
    if renown >= EPITHET_RENOWN:
        belief, _ = max(best.values(), key=lambda p: (p[1].weight * p[0].confidence, p[1].id))
        rng = rng_for(world.world_seed, f"epithet:{subject_id}:{town_id}")
        noun = FORM_NOUNS.get(belief.variant.get("form"), "Hand")
        place = belief.variant.get("place") or world.entity(town_id).name
        epithet = f"{rng.choice(ADJECTIVES[path])} {noun} of {place}"
    return Reputation(renown, renown_word(renown), path, epithet)


def _reputation(world, town_id: int, subject_id: int) -> Reputation:
    """What a town makes of someone, including half of the name they inherited (phase 4b spec 6)."""
    own = _own_reputation(world, town_id, subject_id)
    from systems.lineage import inherited
    extra, shadow = 0.0, None
    for ancestor, share in inherited(world, town_id, subject_id):
        old = reputation(world, town_id, ancestor)
        extra += share * old.renown
        name = world.entity(ancestor).name
        shadow = shadow or (f"heir of the {old.epithet}" if old.epithet else f"heir of {name}" if old.renown else None)
    if not extra:
        return own
    renown = round(own.renown + extra, 3)
    return Reputation(renown, renown_word(renown), own.path if own.renown else "hard to read", own.epithet or shadow)


def reputation(world, town_id: int, subject_id: int) -> Reputation:
    """What a town makes of someone: deeds, an inherited name, and a place on the Pavilion's lists (phase 4d)."""
    found = _reputation(world, town_id, subject_id)
    from systems.rankings import rank_known_in
    ranked = rank_known_in(world, town_id, subject_id)
    if ranked is None:
        return found
    title, bonus = ranked
    renown = round(found.renown + bonus, 3)
    return Reputation(renown, renown_word(renown), found.path, f"{title}, the {found.epithet}" if found.epithet else title)
