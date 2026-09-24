"""Half-strength inheritance (phase 4b spec 6): an heir is judged, in part, by the one they succeeded.

Only among those who believe the heir is the heir: the knower, their home town,
or (for a faction) one of its towns must hold the `heir_of` fact. Only the
direct predecessor is consulted; earlier ancestors reach the heir through them,
halving again each generation.
"""

from world.seed import rng_for

FACTOR = 0.5         # how much of the predecessor's name, feelings, standing and debts pass on
GRUDGE_SHARE = 0.5   # the share of the predecessor's avengers who carry the grudge to the heir


def predecessor(world, heir) -> int | None:
    entity = world.entity(heir) if isinstance(heir, int) else None
    ancestors = entity.data.get("ancestors") if entity is not None and entity.kind == "person" else None
    return ancestors[-1] if ancestors else None


def _heir_fact(world, heir: int, ancestor: int) -> int | None:
    """The `heir_of` fact's id (world._cached keeps lists, so the one value travels in a list)."""
    return world._cached(("heir_fact", heir, ancestor), lambda: [next(
        (f.id for f in world.facts(predicate="heir_of", subject=heir) if f.object == ancestor), None)])[0]


def _knowers(world, fact_id: int) -> set:
    return set(world._cached(("heir_knowers", fact_id), lambda: [b.knower for b in world.believers(fact_id)]))


def believes(world, knower, heir: int, ancestor: int) -> bool:
    fact = _heir_fact(world, heir, ancestor)
    if fact is None or not isinstance(knower, int):
        return False
    knowers = _knowers(world, fact)
    if knower in knowers:
        return True
    entity = world.entity(knower)
    if entity is None:
        return False
    if entity.kind == "person":
        from systems.beliefs import home_of
        return home_of(world, knower) in knowers
    if entity.kind == "faction":
        from systems.standing import _towns
        return bool(knowers & set(_towns(world, knower)))
    return False


def inherited(world, knower, heir) -> list[tuple[int, float]]:
    """[(predecessor, share)] when this knower takes the heir for the predecessor's heir; else []."""
    old = predecessor(world, heir)
    if old is None:
        return []
    return [(old, FACTOR)] if believes(world, knower, heir, old) else []


def inherited_avengers(world, heir: int) -> list[int]:
    old = predecessor(world, heir)
    if old is None:
        return []
    from systems.kin import avengers_for
    out = []
    for avenger in avengers_for(world, old):
        if avenger == heir or not believes(world, avenger, heir, old):
            continue
        if rng_for(world.world_seed, f"heir-grudge:{avenger}:{heir}").random() < GRUDGE_SHARE:
            out.append(avenger)
    return out
