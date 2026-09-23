"""Rules that must hold after every turn. A broken rule is a bug caught early.

Checked live by the app (violations show in the log and F12 overlay) and by the
fuzz tests, so new systems are policed from the moment they exist.
"""

import re
from collections.abc import Sequence

from narrate.brief import MAX_FACTS, MAX_PROMPT
from systems.beliefs import known_people
from world.gen.materialize import people_at
from systems.realms import MAX_REALM, REALMS, next_threshold
from world.body import INJURY_KINDS, LOCATIONS, MERIDIANS, STATES, from_dict, max_qi, settle

LEFTOVER = re.compile(r"\{\w+\}|#\w+#")
FALLBACK = re.compile(r"^\[\w+\]$")
LOWER_START = re.compile(r"(^|[.?!]\s+)[\"']?[a-z]")
NARRATIVE = {"npc", "default", "gold"}  # prose colours; dim/system lines may repeat legitimately
MAX_CHOICES = 9
EPS = 1e-6


def check_world(world) -> list[str]:
    problems = []
    player_id = world.get_meta("player_id")
    if player_id is not None and world.entity(player_id) is None:
        problems.append(f"player_id #{player_id} points at nothing")
    for person in world.entities("person"):
        places = world.targets(person.id, "located_in")
        if person.data.get("dead"):
            if places or len(world.targets(person.id, "buried_at")) != 1:
                problems.append(f"{person.name} (#{person.id}) is dead but not properly buried")
        elif len(places) != 1:
            problems.append(f"{person.name} (#{person.id}) has {len(places)} locations")
        for place in places:
            if world.entity(place) is None:
                problems.append(f"{person.name} (#{person.id}) is located in missing entity #{place}")
        problems += check_fragments(person)
        if person.data.get("silver", 0) < 0:
            problems.append(f"{person.name} (#{person.id}) has negative silver")
        if "body" in person.data:
            problems += check_body(person, settle(from_dict(person.data["body"]), world.time))
            problems += check_arts(world, person)
    problems += check_items(world)
    problems += check_knowledge(world)
    problems += check_factions(world)
    times = world.recent_chronicle_times()
    for before, after in zip(times, times[1:]):
        if after < before:
            problems.append(f"chronicle time went backwards ({before} -> {after})")
    return problems


def check_body(person, body) -> list[str]:
    who = f"{person.name} (#{person.id})"
    out = []
    if not -EPS <= body.qi <= max_qi(body) + EPS:
        out.append(f"{who} qi {body.qi:.2f} outside 0..{max_qi(body):.2f}")
    if body.energy_years < 0:
        out.append(f"{who} has negative energy")
    if not 0 <= body.deviation <= 100:
        out.append(f"{who} deviation {body.deviation:.1f} outside 0..100")
    if not 0 <= body.realm <= MAX_REALM:
        return out + [f"{who} realm {body.realm} out of range"]
    low, high = REALMS[body.realm].threshold, next_threshold(body.realm)
    if body.energy_years < low - EPS or (high is not None and body.energy_years > high + EPS):
        out.append(f"{who} energy {body.energy_years:.3f} outside {REALMS[body.realm].name} bounds")
    elif high is not None and body.energy_years >= high - EPS and not body.bottleneck:
        out.append(f"{who} energy at {high} without a bottleneck")
    if person.data.get("realm") != REALMS[body.realm].label:
        out.append(f"{who} realm label {person.data.get('realm')!r} does not match body realm {REALMS[body.realm].label!r}")
    if set(body.meridians) != set(MERIDIANS):
        out.append(f"{who} is missing meridians")
    for name, meridian in body.meridians.items():
        if meridian.state not in STATES or not 0 <= meridian.flow <= 1:
            out.append(f"{who} {name} meridian state {meridian.state!r} flow {meridian.flow}")
    for injury in body.injuries:
        if (injury.location not in LOCATIONS or injury.kind not in INJURY_KINDS
                or not 1 <= injury.severity <= 5 or (injury.permanent and injury.heals_at is not None)):
            out.append(f"{who} has an invalid injury: {injury.location} {injury.kind} severity {injury.severity}")
    return out


def check_arts(world, person) -> list[str]:
    out = []
    for technique_id, mastery, data in world.relations_from(person.id, "knows"):
        technique = world.entity(technique_id)
        if technique is None or technique.kind != "technique":
            out.append(f"{person.name} knows #{technique_id}, which is not a technique")
        if data.get("known_completeness", 1.0) < data.get("completeness", 1.0) - EPS:
            out.append(f"{person.name} believes an art is less complete than it is")
        if mastery > data.get("completeness", 1.0) + EPS:
            out.append(f"{person.name} mastery {mastery:.2f} above completeness {data.get('completeness')}")
    return out


def check_items(world) -> list[str]:
    out = []
    for manual in world.entities("manual"):
        owners = world.sources(manual.id, "owns")
        if len(owners) != 1:
            out.append(f"manual #{manual.id} has {len(owners)} owners")
        technique = world.entity(manual.data.get("technique"))
        if technique is None or technique.kind != "technique":
            out.append(f"manual #{manual.id} holds no real technique")
        if manual.data.get("claimed_completeness", 1.0) < manual.data.get("true_completeness", 1.0) - EPS:
            out.append(f"manual #{manual.id} claims less than it holds")
    return out


FRAGMENT_KEYS = {"technique", "form", "element", "segment"}


def check_fragments(person) -> list[str]:
    fragments = person.data.get("fragments", [])
    if len(fragments) > 12:
        return [f"{person.name} holds {len(fragments)} fragments (max 12)"]
    if any(set(f) != FRAGMENT_KEYS for f in fragments):
        return [f"{person.name} holds malformed fragments"]
    return []


def check_combat(game) -> list[str]:
    out = []
    d = getattr(game, "combat", None)
    if d is not None:
        for side in (d.player, d.opponent):
            if game.world.entity(side) is None:
                out.append(f"duel participant #{side} does not exist")
        for side, value in d.harm.items():
            if not 0 <= value <= 100:
                out.append(f"duel harm for {side} is {value}")
        if d.stage not in ("fighting", "verdict"):
            out.append(f"duel stage {d.stage!r} is not a stage")
    encounter = getattr(game, "encounter", None)
    if encounter is not None and game.world.entity(encounter["person"]) is None:
        out.append("an encounter with no one")
    return out


def check_knowledge(world) -> list[str]:
    """Beliefs point at facts, lies name their liar, grief passes only from the dead, masks hide faces."""
    out = []
    player = world.get_meta("player_id")
    facts: dict = {}
    # Each turn checks only what was added since the last check, so long lives stay quick.
    mark = getattr(world, "_knowledge_mark", {"beliefs": 0, "facts": 0})
    for belief in world.all_beliefs(after=mark["beliefs"]):
        if belief.fact_id not in facts:
            facts[belief.fact_id] = world.fact(belief.fact_id)
        fact = facts[belief.fact_id]
        if fact is None:
            out.append(f"#{belief.knower} believes missing fact #{belief.fact_id}")
            continue
        if not 0 <= belief.confidence <= 1 or belief.hops < 0:
            out.append(f"#{belief.knower} holds fact #{fact.id} at confidence {belief.confidence}, hops {belief.hops}")
        if belief.channel == "witness" and belief.hops != 0:
            out.append(f"#{belief.knower} witnessed fact #{fact.id} at {belief.hops} retellings")
        actor = belief.variant.get("actor")
        if actor is not None and actor != fact.subject:
            out.append(f"a retelling of fact #{fact.id} credited #{actor} instead of #{fact.subject}")
    for lie in world.facts(is_true=False):
        if lie.id <= mark["facts"]:
            continue
        if "liar" not in lie.data or lie.source_event is None:
            out.append(f"lie #{lie.id} has no liar or no telling behind it")
    for memory in world.memories_inherited():
        source = world.entity(memory.inherited_from)
        if source is None or not source.data.get("dead"):
            out.append(f"#{memory.owner} inherited a memory from #{memory.inherited_from}, who is not dead")
    for persona in world.entities("persona"):
        if persona.data.get("of") != player:
            out.append(f"{persona.name} (#{persona.id}) is nobody's mask")
    world._knowledge_mark = {"beliefs": world.last_rowid("beliefs"), "facts": world.last_rowid("facts")}
    return out


def check_factions(world) -> list[str]:
    """Memberships, ranks, merit, duties and stances stay consistent (phase 3b spec 10)."""
    from systems import factions as F  # factions import the knowledge layer, which imports this module's peers
    out = []
    player = world.get_meta("player_id")
    for faction in world.entities("faction"):
        for other, value, _ in world.relations_from(faction.id, "stance"):
            if not -1 <= value <= 1 or abs(F.stance(world, other, faction.id) - value) > 1e-9:
                out.append(f"stance between #{faction.id} and #{other} is lopsided or out of range")
    for person_id in [player] if player is not None else []:
        rows = F.memberships(world, person_id)
        open_martial = [fid for fid, _, d in rows if d.get("status", "member") == "member" and not d.get("secret")
                        and world.entity(fid).data["type"] in F.MARTIAL]
        if len(open_martial) > 1:
            out.append(f"the player openly belongs to {len(open_martial)} martial factions")
        for fid, rank, data in rows:
            if world.entity(fid) is None or world.entity(fid).kind != "faction":
                out.append(f"membership points at #{fid}, which is no faction")
            founder = world.entity(fid).data.get("type") == "player_sect" and data.get("role") == "leader"
            if not 0 <= rank <= (4 if founder else 3):
                out.append(f"the player holds rank {rank} in #{fid}")
            if data.get("merit", 0) < 0:
                out.append(f"negative merit in #{fid}")
    for duty in world.entities("duty"):
        if duty.data.get("status") != "open":
            continue
        holder = world.entity(duty.data["holder"])
        if holder is None or holder.data.get("dead") or holder.data.get("duty") != duty.id:
            out.append(f"open duty #{duty.id} has no living holder")
        elif (F.membership(world, holder.id, duty.data["faction"]) or (0, {}))[1].get("status", "member") != "member":
            out.append(f"open duty #{duty.id} is held by someone no longer of the faction")
        target = duty.data.get("target")
        if target is not None and world.entity(target) is None:
            out.append(f"open duty #{duty.id} points at missing #{target}")
    return out


def check_people(game, turn) -> list[str]:
    """No one the player never met or heard of is named on screen; the dead never talk or fight."""
    world = game.world
    player_id = world.get_meta("player_id")
    player = world.entity(player_id) if player_id is not None else None
    if player is None:
        return []
    out = []
    for who, role in ((getattr(game, "focus", None), "conversation partner"),
                      (getattr(game, "challenger", None), "challenger")):
        if who is not None and world.entity(who).data.get("dead"):
            out.append(f"the dead #{who} is a {role}")
    encounter = getattr(game, "encounter", None)
    if encounter is not None and world.entity(encounter["person"]).data.get("dead"):
        out.append("a road encounter with the dead")
    text = "\n".join([t for t, _ in turn.lines] + [c.label for c in turn.all_choices]).lower()
    known = {player.name.lower()}
    known |= {world.entity(p).name.lower() for p in known_people(world, player_id)}
    here = world.targets(player_id, "located_in")
    if here:
        known |= {p.name.lower() for p in people_at(world, here[0])}
    known |= {p.name.lower() for p in world.entities("persona") if p.data.get("of") == player_id}
    for kind in ("person", "persona"):
        for entity in world.entities(kind):
            name = entity.name.lower()
            if name in known or len(name) < 4 or name not in text:  # cheap substring test before the regex
                continue
            if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text):
                out.append(f"{entity.name} (#{entity.id}) is named on screen but the player never heard of them")
    from engine.standing_page import known_factions  # the page decides which factions the player knows
    town = here[0] if here else None
    heard = set(known_factions(world, player_id, town)) if town is not None else set()
    heard_names = {world.entity(f).name.lower() for f in heard}  # minor factions far apart can share a name
    for faction in world.entities("faction"):
        if faction.name.lower() not in heard_names and faction.name.lower() in text:
            out.append(f"the faction {faction.name} is named on screen but the player never heard of it")
    return out


def check_turn(game, turn, recent_narration: Sequence[str]) -> list[str]:
    problems = check_combat(game) + check_people(game, turn)
    for text, key in turn.lines:
        if LEFTOVER.search(text):
            problems.append(f"leftover template slot in: {text[:80]}")
        if FALLBACK.match(text):
            problems.append(f"narration fallback, no grammar for {text}")
        if key in NARRATIVE and LOWER_START.search(text):
            problems.append(f"lowercase sentence start in: {text[:80]}")
        if key in NARRATIVE and text and text in recent_narration:
            problems.append(f"repeat of a recent line: {text[:80]}")
    if len(turn.choices) > MAX_CHOICES:
        problems.append(f"{len(turn.choices)} choices shown; only {MAX_CHOICES} have number keys")
    for choice in turn.all_choices:
        if not hasattr(game, f"_do_{choice.action.verb}"):
            problems.append(f"choice {choice.label!r} has no handler for verb {choice.action.verb!r}")
    hidden = None
    player_id = game.world.get_meta("player_id")
    player = game.world.entity(player_id) if player_id is not None else None
    if player is not None and "body" in player.data:
        body = from_dict(player.data["body"])
        if body.constitution and not body.constitution_known:
            hidden = body.constitution
    for brief in getattr(game, "last_briefs", []):
        prompt = brief.to_prompt()
        if len(brief.facts) > MAX_FACTS:
            problems.append(f"brief for {brief.kind} has {len(brief.facts)} facts (max {MAX_FACTS})")
        if len(prompt) > MAX_PROMPT:
            problems.append(f"brief for {brief.kind} is {len(prompt)} chars (max {MAX_PROMPT})")
        if LEFTOVER.search(prompt):
            problems.append(f"leftover template slot in {brief.kind} brief")
        if hidden and hidden in prompt:
            problems.append(f"undiscovered constitution leaked into a {brief.kind} brief")
        if any("true" in key for key in brief.details):
            problems.append(f"a hidden truth leaked into a {brief.kind} brief")
        if any("completeness" in key for key in brief.details):
            problems.append(f"completeness leaked into a {brief.kind} brief")
    if player is not None:
        for entry in game.world.chronicle_about(player.id, limit=3):
            if entry.kind == "breakthrough" and entry.data.get("realm_after", 0) - entry.data.get("realm_before", 0) > 1:
                problems.append("a breakthrough skipped a realm")
    return problems
