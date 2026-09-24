"""What people believe (phase 3a spec §4.2): beliefs, knowledge, confidence, and seeing through masks.

Nothing shown to the player reads facts directly: everything goes through a
knower's beliefs. Ground truth (the chronicle, facts.is_true, a persona's `of`)
stays behind this layer; `of` is read only to ask "is the reader the wearer?".
"""

from dataclasses import replace

from world.db import Belief, Fact, World

CONF_DECAY = 0.85


def believe(world: World, knower: int, fact_id: int, variant: dict, source: int | None,
            confidence: float, hops: int, channel: str) -> bool:
    confidence = round(max(0.0, min(1.0, confidence)), 3)
    return world.upsert_belief(knower, fact_id, variant, source, confidence, max(0, hops), channel)


def confidence_for(hops: int, trust: float = 1.0) -> float:
    return 1.0 if hops == 0 else round(CONF_DECAY ** hops * trust, 3)


def confidence_phrase(hops: int, confidence: float) -> str:
    if hops == 0:
        return "you saw it yourself"
    if confidence >= 0.75:
        return "from a witness"
    if confidence >= 0.45:
        return "hearsay"
    return "doubtful"


def confidence_word(belief: Belief) -> str:
    return confidence_phrase(belief.hops, belief.confidence)


def home_of(world: World, person_id: int) -> int | None:
    """The town a person is in, or None (the dead, roamers of the wilds)."""
    for place_id in world.targets(person_id, "located_in"):
        place = world.entity(place_id)
        if place is not None and place.kind == "town":
            return place.id
    return None


def knowledge_of(world: World, knower_id: int) -> list[tuple[Belief, Fact]]:
    """A person's own beliefs plus their town's gossip, one retelling further. A town knows its pool."""
    own = world.known_facts(knower_id)
    entity = world.entity(knower_id)
    if entity is None or entity.kind != "person":
        return own
    town = home_of(world, knower_id)
    if town is None:
        return own
    held = {(b.fact_id, b.variant_key) for b, _ in own}
    pool = [
        (replace(b, knower=knower_id, source=town, hops=b.hops + 1,
                 confidence=round(b.confidence * CONF_DECAY, 3), channel="gossip"), f)
        for b, f in world.known_facts(town) if (b.fact_id, b.variant_key) not in held
    ]
    return own + pool


def knows_identity(world: World, knower_id: int, persona_id: int | None) -> bool:
    """Does this knower know who wears the mask? The wearer always does."""
    if persona_id is None:
        return False
    persona = world.entity(persona_id)
    if persona is None:
        return False
    if persona.data.get("of") == knower_id:
        return True
    return any(f.predicate == "is" and f.subject == persona_id for _, f in knowledge_of(world, knower_id))


def appears_as(world: World, observer: int, event, true_id: int) -> int:
    """Who `observer` takes `true_id` to be in this event: the persona while masked and unrecognised."""
    data = event.data if isinstance(event.data, dict) else {}
    persona = data.get("as")
    if persona and event.actors and true_id == event.actors[0] and observer != true_id \
            and not knows_identity(world, observer, persona):
        return persona
    return true_id


def seen_as(world: World, observer: int, event) -> int:
    return appears_as(world, observer, event, event.actors[0])


def apparent_to(world: World, observer: int, player_id: int) -> int:
    """Who the player seems to be to `observer` right now: their worn persona unless recognised."""
    persona = world.entity(player_id).data.get("masked")
    if persona and not knows_identity(world, observer, persona):
        return persona
    return player_id


def true_identity(world: World, subject_id: int) -> int:
    entity = world.entity(subject_id)
    if entity is not None and entity.kind == "persona":
        return entity.data.get("of", subject_id)
    return subject_id


def identities(world: World, knower_id: int, true_id: int) -> set[int]:
    """The ids this knower attributes to `true_id`: themselves plus any persona known to be them."""
    ids = {true_id}
    for persona in world.entities("persona"):
        if persona.data.get("of") == true_id and knows_identity(world, knower_id, persona.id):
            ids.add(persona.id)
    return ids


def known_people(world: World, player_id: int) -> list[int]:
    """Everyone the player has met or heard of (people and personas), most recent first."""
    seen: list[int] = world.acquaintances(player_id)  # all of history, not just recent pages
    for belief, _ in reversed(world.known_facts(player_id)):
        for someone in (belief.variant.get("actor"), belief.variant.get("target")):
            if someone is not None and someone != player_id and someone not in seen:
                seen.append(someone)
        for names in (belief.variant.get("lists") or {}).values():  # a list you have read names people (phase 4d)
            seen += [p for p in names if p != player_id and p not in seen]
    out = []
    for someone in seen:
        entity = world.entity(someone)
        if entity is not None and entity.kind in ("person", "persona"):
            out.append(someone)
    return out
