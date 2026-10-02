"""Claude's proposals checked against the rules and the world (phase 6 spec 7.4), turned into events.

`accept(scene, proposals, kinds)` takes the model's list and returns what may stand (events, at most one engine
action) and what may not (each with its reason, for the debug overlay; there is no retry, spec 14.5). It never
writes: the caller commits the events. The checks are the hard limits; the model is told the soft ones (its state
pack) and is expected to keep to them.
"""

from dataclasses import dataclass, field

import ai.deeds as D
from ai.guard import NAMED, allowed_people
from engine.actions import Action
from mcp_server.tools import belief_handle
from systems.purse import silver_of
from world.body import BODY_PARTS
from world.gen.materialize import people_at
from world.db import World
from world.gen.npc import OCCUPATIONS, TRAITS

FEELINGS = ("grateful", "amused", "respect", "annoyed", "contempt", "fear")
MAX_STRENGTH = 0.5
MAX_DEED = 120
HURTS = ("bruise", "cut", "burn", "fracture")
MAX_SEVERITY = 2
MAX_WATCHES = 8
REALMS = ("mortal", "third-rate")
PER_VISIT, PER_TOWN = 2, 6  # newcomers: a visit is a day in the town (plan ruling)
MAX_PROPOSALS = 4
KINDS = ("action", "pay", "give", "feeling", "deed", "tell", "minor_npc", "hurt", "time")
DIALOGUE_KINDS = tuple(k for k in KINDS if k not in ("action", "minor_npc"))  # talking, not acting (spec 14.4)

# One flat item schema for every kind (the CLI's structured output wants one shape); `accept` checks each kind's
# own fields.
PROPOSAL = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(KINDS)},
        "choice": {"type": "string", "maxLength": 120},
        "to": {"type": "string", "maxLength": 60}, "who": {"type": "string", "maxLength": 60},
        "amount": {"type": "integer"}, "item": {"type": "string", "maxLength": 80},
        "feeling": {"type": "string", "maxLength": 20}, "strength": {"type": "number"},
        "text": {"type": "string", "maxLength": 200}, "tone": {"type": "string", "maxLength": 10},
        "handle": {"type": "string", "maxLength": 20},
        "occupation": {"type": "string", "maxLength": 40},
        "traits": {"type": "array", "items": {"type": "string", "maxLength": 20}, "maxItems": 2},
        "realm": {"type": "string", "maxLength": 20},
        "location": {"type": "string", "maxLength": 20}, "injury": {"type": "string", "maxLength": 20},
        "severity": {"type": "integer"}, "watches": {"type": "integer"},
    },
    "required": ["kind"],
    "additionalProperties": False,
}
PROPOSALS = {"type": "array", "items": PROPOSAL, "maxItems": MAX_PROPOSALS}


@dataclass
class Scene:
    """What a turn's proposals are judged against."""
    world: World
    player: int
    place: int
    choices: list            # this turn's valid choices (shown and folded): `action` must name one
    salt: str                # seeds a minor NPC (the same turn, the same person)


@dataclass
class Accepted:
    events: list = field(default_factory=list)
    action: Action | None = None
    rejected: list = field(default_factory=list)   # (proposal, reason)


def _here(scene: Scene) -> dict[str, int]:
    found: dict[str, list[int]] = {}
    for person in people_at(scene.world, scene.place, exclude=scene.player):
        found.setdefault(person.name.lower(), []).append(person.id)
    return {name: ids[0] for name, ids in found.items() if len(ids) == 1}


def _someone(scene: Scene, name) -> int | None:
    return _here(scene).get(str(name or "").strip().lower())


def _item(scene: Scene, name) -> int | None:
    world, wanted = scene.world, str(name or "").strip().lower()
    held = set(world.targets(scene.player, "wields")) | set(world.targets(scene.player, "wears"))
    for item in world.targets(scene.player, "owns"):
        entity = world.entity(item)
        if entity is None or entity.name.lower() != wanted or entity.data.get("used"):
            continue
        if item in held or entity.data.get("armoury") is not None or entity.data.get("claimed_by") is not None:
            return None  # what is wielded, worn or a sect's is not yours to hand over
        return item
    return None


def check(scene: Scene, p: dict, done: Accepted, felt: set) -> tuple[object, str | None]:
    """(an event or an Action, None) if it may stand; (None, the reason) if not."""
    world, me, here = scene.world, scene.player, scene.place
    kind = p.get("kind")
    if kind == "action":
        choice = next((c for c in scene.choices if c.label == p.get("choice")), None)
        if choice is None:
            return None, "no such choice now"
        if done.action is not None:
            return None, "only one action a turn"
        return choice.action, None
    if kind == "pay":
        npc, amount = _someone(scene, p.get("to")), p.get("amount")
        if npc is None:
            return None, "they are not here"
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            return None, "no such sum"
        spent = sum(e.data["amount"] for e in done.events if e.kind == "ai_paid")
        if amount + spent > silver_of(world, me):
            return None, "you have not that much silver"
        return D.paid(me, npc, here, amount, p), None
    if kind == "give":
        npc, item = _someone(scene, p.get("to")), _item(scene, p.get("item"))
        if npc is None:
            return None, "they are not here"
        if item is None or any(e.kind == "ai_gave" and e.data["item"] == item for e in done.events):
            return None, "you have no such thing to give"
        return D.gave(me, npc, here, item, p), None
    if kind == "feeling":
        npc, feeling, strength = _someone(scene, p.get("who")), p.get("feeling"), p.get("strength", 0.3)
        if npc is None:
            return None, "they are not here"
        if feeling not in FEELINGS:
            return None, "no such feeling"
        if not isinstance(strength, (int, float)) or not 0 < strength <= MAX_STRENGTH:
            return None, f"a feeling's strength is above 0 and at most {MAX_STRENGTH}"
        if npc in felt:
            return None, "one feeling a person a line"
        if world.entity(npc).data.get("ai_felt_day") == world.time // 4:
            return None, "they have felt enough today"  # or a feeling could be farmed line after line (6c review)
        felt.add(npc)
        return D.felt(me, npc, here, feeling, float(strength), p), None
    if kind == "deed":
        text, tone = str(p.get("text") or "").strip(), p.get("tone")
        if not text or len(text) > MAX_DEED:
            return None, f"a deed is told in at most {MAX_DEED} characters"
        if tone not in D.TONES:
            return None, "no such tone"
        known = allowed_people(world, me, here)
        for found in NAMED.findall(text):
            if not any(found in name or name in found for name in known):
                return None, f"it names {found}, whom you do not know"
        if any(e.kind == "ai_deed" for e in done.events):
            return None, "one deed a line"  # deeds weigh on karma: one a line, or merit could be farmed
        if world.entity(me).data.get("ai_deed_day") == world.time // 4:
            return None, "one deed a day"  # and one a day (6c review)
        people = tuple(sorted({pid for name, pid in _here(scene).items() if name in text.lower()}))
        return D.deed(me, people, here, text, tone, p), None
    if kind == "tell":
        npc, handle = _someone(scene, p.get("who")), p.get("handle")
        if npc is None:
            return None, "they are not here"
        fact = next((f.id for _, f in world.known_facts(npc) if belief_handle(world, npc, f.id) == handle), None)
        if fact is None:
            return None, "they hold no such belief"
        return D.told(npc, me, here, fact, p), None
    if kind == "minor_npc":
        occupation, traits, realm = p.get("occupation"), list(p.get("traits") or []), p.get("realm", "mortal")
        if occupation not in OCCUPATIONS:
            return None, "no such trade"
        if not traits or any(t not in TRAITS for t in traits):
            return None, "no such traits"
        if realm not in REALMS:
            return None, "a newcomer is a mortal or third-rate"
        new = sum(1 for e in done.events if e.kind == "ai_arrived")
        if new:
            return None, "one newcomer a line"
        if D.made_today(world, here) >= PER_VISIT or D.made_here(world, here) >= PER_TOWN:
            return None, "enough newcomers here for now"
        path = f"ai:{here}:{D.made_here(world, here)}:{scene.salt}:{new}"  # the same line twice: two people
        return D.arrived(me, here, path, occupation, traits, realm, p), None
    if kind == "hurt":
        location, injury, severity = p.get("location"), p.get("injury"), p.get("severity")
        if location not in BODY_PARTS or injury not in HURTS:
            return None, "no such hurt"
        if not isinstance(severity, int) or isinstance(severity, bool) or not 1 <= severity <= MAX_SEVERITY:
            return None, f"a hurt is of severity 1 to {MAX_SEVERITY}"
        return D.hurt(me, here, location, injury, severity, p), None
    if kind == "time":
        watches = p.get("watches")
        if not isinstance(watches, int) or isinstance(watches, bool) or not 1 <= watches <= MAX_WATCHES:
            return None, f"time passes in 1 to {MAX_WATCHES} watches"
        return D.waited(me, here, watches, p), None
    return None, "no such kind of proposal"


def accept(scene: Scene, proposals: list, kinds: tuple = KINDS) -> Accepted:
    done, felt, weighed = Accepted(), set(), 0
    for p in proposals if isinstance(proposals, list) else []:
        if not isinstance(p, dict):
            continue
        if weighed >= MAX_PROPOSALS:
            result, why = None, "too many changes"
        elif p.get("kind") in KINDS and p.get("kind") not in kinds:
            result, why = None, "not while talking"
        else:
            weighed += 1
            result, why = check(scene, p, done, felt)
        if why is not None:
            done.rejected.append((p, why))
        elif isinstance(result, Action):
            done.action = result
        else:
            done.events.append(result)
    return done
