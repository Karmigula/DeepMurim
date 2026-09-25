"""The realms page (F5, phase 4f spec 6): the secret realms you know of, as far as you know them.

Built from what the player has seen (gates, the realms they entered: `realms_seen`) and believes (the
heralds' news of an opening, the tales survivors carry out), never from a realm nobody told them of.
"""

import systems.delve as D
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.world_events as W
from narrate.base import Line
from systems.facts import place_name
from world.gen.materialize import region_of

RULE_WORDS = {"ceiling": "the seal admits no one above {value}", "token": "a jade token opens the gate",
              "open": "open to anyone at the gate", "quota": "the near sects hold its places"}
TALES = frozenset({"delved", "took", "inherited", "sealed"})


def _beliefs(world, player: int):
    """(heralded realms: {realm: (occurrence, stage)}, tales: {realm id: [(predicate, actor)]}) from beliefs."""
    heralded, tales = {}, {}
    for belief, fact in world.known_facts_about([player], predicate="phenomenon"):
        occurrence = world.entity(fact.data.get("occurrence")) if fact.data.get("occurrence") else None
        if occurrence is not None and occurrence.data.get("type") in SR.OPENINGS:
            heralded[occurrence.data["data"]["realm"]] = (occurrence.id, belief.variant.get("stage"))
    for predicate in sorted(TALES):
        for belief, fact in world.known_facts_about([player], predicate=predicate):
            realm = belief.variant.get("realm_id")
            if realm is not None:  # by id: newborn realms' names can repeat over the centuries
                tales.setdefault(realm, []).append((predicate, belief.variant.get("actor")))
    return heralded, tales


def known(world, player: int) -> list[int]:
    heralded, tales = _beliefs(world, player)
    seen = set(world.entity(player).data.get("realms_seen", []))
    return [r for r in SR.realms(world) if r in seen or r in heralded or r in tales]


def realm_line(world, player: int, realm: int, heralded=None, tales=None) -> str:
    if heralded is None:
        heralded, tales = _beliefs(world, player)
    entity = world.entity(realm)
    gate = entity.data["gate"]
    rule = entity.data["rule"]
    seen = realm in world.entity(player).data.get("realms_seen", [])
    words = RULE_WORDS[rule["kind"]].format(value=(rule["value"] or "").replace("-", " "))         if seen or realm in heralded else "its way in unknown to you"  # a tale tells of the inside, not the gate
    occurrence = D.gate_open(world, realm)
    if occurrence is not None and realm in world.entity(player).data.get("realms_seen", []):
        when = f"the gate stands open, closing in {D.days_left(world, occurrence)} days"
    elif realm in heralded:
        live = world.entity(heralded[realm][0])
        days = max(0, (live.data["active"][0] - world.time) // 4) if live is not None else 0
        when = f"heralded: its gate opens in about {days} days" if days else "heralded"
    else:
        when = "when it opens again, no one has told you"
    tokens = len(G.tokens_of(world, player, realm))
    told = tales.get(realm, [])
    heirs = [world.entity(actor).name for predicate, actor in told if predicate == "inherited" and actor is not None]
    inside = realm in world.entity(player).data.get("realms_seen", [])
    legacy = f"claimed by {heirs[0]}" if heirs else "unclaimed, as far as you know" if inside else "unknown"
    came_out = sum(1 for predicate, _ in told if predicate == "delved")
    return (f"  {entity.name[0].upper()}{entity.name[1:]}, its gate at {place_name(world, gate)} "
            f"({region_of(world, gate).name}): {words}; {when}. Inheritance: {legacy}."
            + (f" Your jade tokens: {tokens}." if tokens else "")
            + (f" You have heard of {came_out} who came out." if came_out else ""))


def realms_lines(world, player: int) -> list[Line]:
    lines: list[Line] = [("Secret realms", "heading")]
    heralded, tales = _beliefs(world, player)
    seen = set(world.entity(player).data.get("realms_seen", []))
    found = [r for r in SR.realms(world) if r in seen or r in heralded or r in tales]
    if not found:
        return lines + [("  You know of no secret realm. Heralds cry their openings; survivors tell of them.", "dim")]
    return lines + [(realm_line(world, player, r, heralded, tales), "dim") for r in found]


def sheet_realm_lines(world, player: int) -> list[Line]:
    """The character sheet's jade tokens and, if it has come to that, where the player is sealed."""
    lines: list[Line] = []
    tokens = [world.entity(i) for i in world.targets(player, "owns")]
    tokens = [t for t in tokens if t is not None and t.kind == "treasure" and t.data.get("kind") == "token"
              and not t.data.get("used")]
    if tokens:
        names = ", ".join(sorted({world.entity(t.data["realm"]).name for t in tokens}))
        lines += [("", "default"), (f"Jade tokens: {len(tokens)} ({names})", "default")]
    sealed = world.entity(player).data.get("sealed_in")
    if sealed:
        lines.append((f"Sealed in {world.entity(sealed['realm']).name}", "red"))
    return lines
