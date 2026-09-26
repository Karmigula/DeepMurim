"""Rules that must hold after every turn. A broken rule is a bug caught early.

Checked live by the app (violations show in the log and F12 overlay) and by the
fuzz tests, so new systems are policed from the moment they exist.
"""

import json
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


_BODIES_CHECKED: dict = {}  # (save path, person) -> the stored body text that last checked clean


def check_world(world) -> list[str]:
    problems = []
    stored = dict(world._conn.execute(
        "select id, json_extract(data, '$.body') from entities where kind = 'person'").fetchall())
    player_id = world.get_meta("player_id")
    if player_id is not None and world.entity(player_id) is None:
        problems.append(f"player_id #{player_id} points at nothing")
    where: dict = {}
    for a, b, kind in world._conn.execute(
            "select a, b, kind from relations where kind in ('located_in', 'buried_at') order by since, b"):
        where.setdefault((a, kind), []).append(b)
    existing = {row[0] for row in world._conn.execute("select id from entities")}
    people = world.entities("person")
    for person in people:
        places = where.get((person.id, "located_in"), [])
        if person.data.get("dead"):
            if places or len(where.get((person.id, "buried_at"), [])) != 1:
                problems.append(f"{person.name} (#{person.id}) is dead but not properly buried")
        elif len(places) != (0 if person.data.get("vanished") else 1):  # the vanished are nowhere (4e)
            problems.append(f"{person.name} (#{person.id}) has {len(places)} locations")
        for place in places:
            if place not in existing:
                problems.append(f"{person.name} (#{person.id}) is located in missing entity #{place}")
        problems += check_fragments(person)
        if person.data.get("silver", 0) < 0:
            problems.append(f"{person.name} (#{person.id}) has negative silver")
        if "body" in person.data:
            key, text = (str(world.path), person.id), stored.get(person.id)
            if _BODIES_CHECKED.get(key) != text:  # an unchanged body that checked clean need not be rebuilt
                found = check_body(person, settle(from_dict(person.data["body"]), world.time))
                problems += found
                if found:
                    _BODIES_CHECKED.pop(key, None)
                else:
                    _BODIES_CHECKED[key] = text
            problems += check_arts(world, person)
    problems += check_items(world)
    problems += check_gear(world)
    problems += check_knowledge(world)
    problems += check_factions(world)
    problems += check_sect(world)
    problems += check_life(world, people)
    problems += check_lineage(world)
    problems += check_trade(world)
    problems += check_sky(world)
    problems += check_races(world)
    problems += check_rankings(world)
    problems += check_tournaments(world)
    problems += check_realms(world)
    problems += check_crises(world)
    problems += check_plots(world)
    times = world.recent_chronicle_times()
    for before, after in zip(times, times[1:]):
        if after < before:
            problems.append(f"chronicle time went backwards ({before} -> {after})")
    problems += world.cache_drift()  # an entity's .data edited in place and never saved (the entity cache)
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


def check_gear(world) -> list[str]:
    """Weapons and armour (phase 5a spec 7): one owner, what is wielded is owned, deeds are real."""
    from systems.gear import SLOTS
    out = []
    for item in world.entities("gear"):
        owners = world.sources(item.id, "owns")
        if len(owners) > 1:
            out.append(f"{item.name} (#{item.id}) has {len(owners)} owners")
        history = item.data.get("owners") or []
        if owners and (not history or history[-1]["person"] != owners[0]):
            out.append(f"{item.name} (#{item.id}) is owned by #{owners[0]}, whom its history does not end with")
        for deed in item.data.get("deeds", []):
            if world.chronicle_entry(deed["event"]) is None:
                out.append(f"{item.name} (#{item.id}) remembers a deed that never happened (#{deed['event']})")
        if len(item.data.get("deeds", [])) > 12:
            out.append(f"{item.name} (#{item.id}) remembers more than twelve deeds")
        for slot, rel in SLOTS.items():
            for holder in world.sources(item.id, rel):
                if holder not in owners:
                    out.append(f"#{holder} {rel} {item.name} (#{item.id}) without owning it")
                if item.data["slot"] != slot:
                    out.append(f"#{holder} {rel} {item.name} (#{item.id}), which is no {slot}")
    for rel in SLOTS.values():
        for holder, count in world._conn.execute(
                "select a, count(*) from relations where kind = ? group by a having count(*) > 1", (rel,)):
            out.append(f"#{holder} {rel} {count} things at once")
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
        wearer = world.entity(persona.data["of"]) if isinstance(persona.data.get("of"), int) else None
        if persona.data.get("of") != player and (wearer is None or not wearer.data.get("dead")):  # a dead player's masks stay theirs
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
            founder = data.get("role") == "leader"  # a sect founded (3c), or a seat won in a crisis (4g)
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


def check_life(world, people=None) -> list[str]:
    """The living world (phase 4a spec 8): clocks never ahead, families and factions consistent."""
    out = []
    now = world.time // 360
    tick = world.get_meta("world_tick")
    if tick is not None and tick > now:
        out.append(f"the world clock is at season {tick}, ahead of season {now}")
    leaders: dict = {}
    people = world.entities("person") if people is None else people
    dead = {p.id for p in people if p.data.get("dead")}
    member_rows: dict = {}
    kin_rows: dict = {}
    for a, b, kind, raw in world._conn.execute(
            "select a, b, kind, data from relations where kind in ('member_of', 'kin_of') order by since, b"):
        (member_rows if kind == "member_of" else kin_rows).setdefault(a, []).append((b, json.loads(raw)))
    for person in people:
        d = person.data
        who = f"{person.name} (#{person.id})"
        if d.get("lived_to") is not None and d["lived_to"] > now:
            out.append(f"{who} has lived ahead to season {d['lived_to']}")
        active = [(f, data) for f, data in member_rows.get(person.id, []) if data.get("status", "member") == "member"]
        if d.get("dead"):
            if active:
                out.append(f"{who} is dead but still a member of #{active[0][0]}")
            continue
        for f, data in active:
            if data.get("role") == "leader":
                leaders.setdefault(f, []).append(person.id)
        spouses = []
        for other, data in kin_rows.get(person.id, []):
            if data.get("role") != "spouse" or other in dead:
                continue
            spouses.append(other)
            back = [r for b, r in kin_rows.get(other, []) if b == person.id]
            if not back or back[0].get("role") != "spouse":
                out.append(f"{who} calls #{other} a spouse, but not the other way round")
        if len(spouses) > 1:
            out.append(f"{who} has {len(spouses)} living spouses")
        if float(d.get("age", 30)) < 12:
            if any(data.get("role") not in (None, "member") for _, data in active) or d.get("sworn_to"):
                out.append(f"{who} is a child but serves a faction or a master")
            if any(r.get("role") == "disciple" for _, r in kin_rows.get(person.id, [])):
                out.append(f"{who} is a child with a disciple")
    for faction, people in leaders.items():
        entity = world.entity(faction)
        if len(people) > 1 and not entity.data.get("dissolved") and entity.data.get("type") != "player_sect":
            out.append(f"{entity.name} has {len(people)} living leaders")
    for fact in world.facts(predicate="born"):
        town = world.entity(fact.place) if fact.place else None
        cap = 1.5 * town.data.get("npc_count", 10) if town is not None else 0
        if fact.data.get("population", 0) >= cap:
            out.append(f"a child was born in a full town ({fact.data.get('population')} >= {cap})")
    return out


def mentions(name: str, text: str) -> bool:
    """Whether `name` appears in `text` as whole words ("wang clan" is not in "hwang clan")."""
    return name in text and re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text) is not None


def check_rankings(world) -> list[str]:
    """Phase 4d spec 8, rule 4: the lists name only people the Pavilion believes in, in order, once each."""
    import systems.rankings as R
    pav = R.pavilion(world)
    d = world.entity(pav).data if pav is not None else {}
    if not d.get("lists"):
        return []
    key = (str(world.path), d["year"], len(d["lists"].get("heaven", [])), sum(map(len, d["lists"].values())))
    if getattr(world, "_rankings_checked", None) == key:
        return []
    out, seen = [], set()
    believed = {b.variant.get("actor") for b, f in world.known_facts(pav)}
    for name, size in R.LISTS:
        names = d["lists"].get(name, [])
        values = [d["scores"].get(str(p), 0.0) for p in names]
        if len(names) > size or len(set(names)) != len(names) or values != sorted(values, reverse=True):
            out.append(f"the {name} list is out of order, too long or repeats someone")
        if seen & set(names):
            out.append(f"the {name} list shares a name with a higher list")
        seen |= set(names)
    for person in seen | set(d["lists"].get("young", [])):
        if person not in believed:
            out.append(f"#{person} is ranked but the Pavilion holds no belief about them")
    published = world.chronicle_of_kind("rankings_published")  # judged as the Pavilion saw them then (4f ruling 24)
    ages = R.believed_ages(world, pav, published[-1].time if published else None)
    for person in d["lists"].get("young", []):
        if ages.get(person, R.YOUNG_AGE + 1) > R.YOUNG_AGE:
            out.append(f"#{person} is a Young Dragon but the Pavilion believes them older than {R.YOUNG_AGE}")
    if not out:
        world._rankings_checked = key
    return out


def check_tournaments(world) -> list[str]:
    """Phase 4e spec 7, rules 1-2: a sound bracket, each winner advancing once, one champion at most."""
    import systems.tournaments as T
    import systems.world_events as W
    out = []
    for row in W.index(world):
        if row[W.TYPE] not in T.KINDS:
            continue
        t = world.entity(row[W.ID]).data["data"]
        rounds = t.get("rounds") or []
        if not rounds:
            continue
        who = f"tournament #{row[W.ID]}"
        if len(rounds[0]) * 2 != t["size"] or t["size"] & (t["size"] - 1):
            out.append(f"{who} has a bracket of {len(rounds[0]) * 2} for a size of {t['size']}")
        for r, matches in enumerate(rounds):
            if r and len(matches) * 2 != len(rounds[r - 1]):
                out.append(f"{who} round {r + 1} has {len(matches)} matches")
            for i, m in enumerate(matches):
                if m["winner"] is not None and m["winner"] not in (m["a"], m["b"]):
                    out.append(f"{who} round {r + 1} match {i + 1} has a winner who did not fight in it")
                if m["how"] is not None and m["on"] is not None and m["on"] < m["day"]:
                    out.append(f"{who} round {r + 1} match {i + 1} was settled before its day")
                loser = m["b"] if m["winner"] == m["a"] else m["a"]
                if m["how"] == "bout" and loser is not None and m["winner"] is not None \
                        and (world.entity(loser).data.get("death") or {}).get("killer") == m["winner"]:
                    out.append(f"{who}: #{m['winner']} killed #{loser} in a bout and was not disqualified")
                if m["how"] is not None and r + 1 < len(rounds):
                    up = rounds[r + 1][i // 2]["a" if i % 2 == 0 else "b"]
                    if up != m["winner"]:
                        out.append(f"{who} round {r + 1} match {i + 1}'s winner did not advance")
        for n, bet in enumerate(t.get("bets", [])):
            if bet["stake"] > bet["silver"] * 0.1 + 1e-9:
                out.append(f"{who} bet {n + 1} staked more than a tenth of the bettor's silver")
            if t.get("finished") and not bet["settled"]:
                out.append(f"{who} has an open bet ({n + 1}) after it ended")
        if t.get("finished") and t.get("champion") != rounds[-1][0]["winner"]:
            out.append(f"{who} crowned someone other than the final's winner")
        if not t.get("finished"):
            occurrence = world.entity(row[W.ID])
            for person in t.get("entrants", []):
                if T.alive(world, person) and not T.qualifies(world, occurrence, person, slack=1):
                    out.append(f"{who}: #{person} does not qualify for it")
    return out


def check_races(world) -> list[str]:
    """Phase 4d spec 8, rule 5: a prize is claimed at most once, and every treasure has one owner (or was used)."""
    import systems.races as races
    import systems.world_events as W
    out = []
    live = {row[W.ID] for row in W.index(world)}
    mark = getattr(world, "_races_checked", 0)
    rows = world._conn.execute("select id, data from entities where kind = 'world_event' and id > ? order by id", (mark,))
    settled = True  # the mark moves only past a run of settled occurrences, so none is skipped while open
    for occurrence, text in rows.fetchall():
        d = json.loads(text)
        race = d["data"] if d["type"] in races.RACE_KINDS else {}
        if race.get("claimed") is not None and world.entity(race.get("item") or -1) is None:
            out.append(f"race #{occurrence} was claimed but its prize is missing")
            settled = False
        settled = settled and (occurrence not in live or race.get("claimed") is not None)
        if settled:
            world._races_checked = occurrence
    for item in world.entities("treasure"):
        if item.data.get("kind") == "sect_token":
            continue  # owned or lying where its leader fell: one place, as check_crises holds (4g)
        owners = world.sources(item.id, "owns")
        if len(owners) != (0 if item.data.get("used") else 1):
            out.append(f"treasure #{item.id} has {len(owners)} owners")
    return out


def check_sky(world) -> list[str]:
    """Phase 4d spec 8, rules 1-3: occurrences keep their calendar, one per type and place, modifiers in bounds."""
    import systems.world_events as W
    out, live = [], {}
    rows = W.index(world)
    for row in rows:
        occurrence = world.entity(row[W.ID])
        if occurrence is None or occurrence.kind != "world_event":
            out.append(f"the sky index names missing occurrence #{row[W.ID]}")
            continue
        d = occurrence.data
        if d["type"] not in W.TYPES:
            out.append(f"occurrence #{occurrence.id} has unknown type {d['type']!r}")
            continue
        ends = [d["ends"][s] for s in W.STAGES if s in d["ends"]]
        if ends != sorted(ends) or not ends or ends[0] <= d["starts"]:
            out.append(f"occurrence #{occurrence.id} has its stages out of order")
        if d["seen"] != W.stages_of(d)[:len(d["seen"])]:
            out.append(f"occurrence #{occurrence.id} saw its stages out of order: {d['seen']}")
        if d.get("over") and world.time < d["over_at"]:
            out.append(f"occurrence #{occurrence.id} is over before its time")
        if not row[W.DONE]:
            live.setdefault((row[W.TYPE], row[W.PLACE]), []).append(row)
        for key in W.TYPES[d["type"]]["modifiers"]:
            value = W.factor(world, None if row[W.SCOPE] == "world" else row[W.PLACE], key)
            if not W.FACTOR_MIN - 1e-9 <= value <= W.FACTOR_MAX + 1e-9:
                out.append(f"the {key} modifier over #{row[W.PLACE]} is {value}")
    for (kind, place), found in live.items():
        found.sort(key=lambda r: r[W.STARTS])
        for a, b in zip(found, found[1:]):
            if a[W.OVER_AT] > b[W.STARTS]:
                out.append(f"two {kind} occurrences overlap over #{place}")
    return out


def check_trade(world) -> list[str]:
    """Phase 4c spec 9: sane packs, markets, price events and price books."""
    from systems.goods import GOODS, capacity, pack_weight
    out = []
    player = world.get_meta("player_id")
    for person in world.entities("person"):
        goods = person.data.get("goods") or {}
        if any(g not in GOODS or not isinstance(n, int) or n < 0 for g, n in goods.items()):
            out.append(f"{person.name} (#{person.id}) carries impossible goods {goods}")
        elif person.id == player and not person.data.get("dead") and pack_weight(goods) > capacity(world, person.id):
            out.append(f"the player's pack weighs {pack_weight(goods)}, over its {capacity(world, person.id)}")
        book = person.data.get("price_book") or {}
        if any(entry.get("time", 0) > world.time for entry in book.values()):
            out.append(f"{person.name} (#{person.id}) has a price book entry from the future")
    for town in world.entities("town"):
        for good, (value, _) in (town.data.get("market") or {}).items():
            if not 0.1 - 1e-9 <= value <= 3.0 + 1e-9:
                out.append(f"{town.name} market stock of {good} is {value}")
    for event in world.entities_after("price_event", "until", world.time):
        if any(not 0.3 <= m <= 4.0 for m in event.data["multipliers"].values()):
            out.append(f"price event #{event.id} has a multiplier outside 0.3-4.0")
    return out


def check_lineage(world) -> list[str]:
    """Phase 4b spec 8: exactly one living player, or a dead one choosing a successor."""
    out = []
    player_id = world.get_meta("player_id")
    player = world.entity(player_id) if player_id is not None else None
    if player is None:
        return out
    flagged = [p.id for p in world.entities("person") if p.data.get("is_player") and not p.data.get("dead")]
    if player.data.get("dead"):
        if not player.data.get("dying"):
            out.append("the player is dead but no successor is being chosen")
        if flagged:
            out.append(f"living people marked as the player while the player is dead: {flagged}")
    elif flagged != [player_id]:
        out.append(f"is_player marks {flagged}, but the player is #{player_id}")
    for ancestor in player.data.get("ancestors", []):
        entity = world.entity(ancestor)
        if entity is None or not entity.data.get("dead") or len(world.targets(ancestor, "buried_at")) != 1:
            out.append(f"ancestor #{ancestor} is not dead and buried")
        elif entity.data.get("silver", 0) or world.targets(ancestor, "owns") or world.targets(ancestor, "owns_land") \
                or entity.data.get("goods") or entity.data.get("mule"):
            out.append(f"ancestor #{ancestor} still holds silver, items, land, goods or a mule")
    named = player.data.get("named_heir")
    if named is not None and not player.data.get("dying") and (world.entity(named) is None or world.entity(named).data.get("dead")):
        out.append(f"the named heir #{named} is dead")
    return out


def check_sect(world) -> list[str]:
    """The player's sect: one leader, an owned seat, a sane roster and clock (phase 3c spec 9)."""
    from systems import factions as F
    from world.gen.materialize import region_of
    out = []
    for town in world.entities("town"):
        if len(world.sources(town.id, "owns_land")) > 1:
            out.append(f"{town.name} has {len(world.sources(town.id, 'owns_land'))} owners")
    for sect in world.entities("faction"):
        if sect.data.get("type") != "player_sect":
            continue
        living = [p for p in world.sources(sect.id, "member_of")
                  if (F.membership(world, p, sect.id) or (0, {}))[1].get("status", "member") == "member"]
        if sect.data.get("dissolved"):
            if living:
                out.append(f"dissolved {sect.name} still has {len(living)} members")
            continue
        founder = sect.data["founder"]
        if world.entity(founder).data.get("dead"):
            continue  # its founder has died and a successor is being chosen (phase 4b)
        leaders = [p for p in living if F.membership(world, p, sect.id)[1].get("role") == "leader"]
        if leaders != [founder]:
            out.append(f"{sect.name} has leaders {leaders}, not its founder")
        seat = sect.data["seat"]
        if seat not in world.targets(founder, "owns_land"):
            out.append(f"{sect.name}'s seat is not the founder's land")
        roles = [F.membership(world, p, sect.id)[1].get("role") for p in living]
        if roles.count("disciple") > 12 or roles.count("elder") > 3:
            out.append(f"{sect.name} has too many members")
        region = region_of(world, seat).id
        for person in living:
            entity = world.entity(person)
            if entity.data.get("dead"):
                out.append(f"{entity.name} of {sect.name} is dead but still a member")
            if person == founder or entity.data.get("dead"):
                continue
            where = world.targets(person, "located_in")
            expected = region if entity.data.get("on_duty") else seat
            if where != [expected]:
                out.append(f"{entity.name} of {sect.name} is not at the seat or on duty")
        if sect.data["last_tick"] > world.time:
            out.append(f"{sect.name}'s seasons are ahead of the clock")
        if sect.data["treasury"] < 0:
            out.append(f"{sect.name} has a negative treasury")
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
    raw = "\n".join([t for t, _ in turn.lines] + [c.label for c in turn.all_choices])
    text = raw.lower()
    known = {player.name.lower()}
    known |= {world.entity(p).name.lower() for p in known_people(world, player_id)}
    here = world.targets(player_id, "located_in")
    if here:
        known |= {p.name.lower() for p in people_at(world, here[0])}
    known |= {p.name.lower() for p in world.entities("persona") if p.data.get("of") == player_id}
    from engine.tournament_page import posted_names  # a bracket posted where you can read it (phase 4e)
    known |= {world.entity(p).name.lower() for p in posted_names(world, player_id)}
    known |= {world.entity(k).name.lower() for k, _, _ in world.relations_from(player_id, "kin_of")}  # your family
    for ancestor in player.data.get("ancestors", []):  # and your forebears, and who killed them (phase 4b)
        forebear = world.entity(ancestor)
        known.add(forebear.name.lower())
        killer = (forebear.data.get("death") or {}).get("killer")
        if killer is not None:
            known.add(world.entity(killer).name.lower())
    for kind in ("person", "persona"):
        for entity in world.entities(kind):
            name = entity.name.lower()
            if name in known or len(name) < 4 or name not in text:  # cheap substring test before the regex
                continue
            if re.search(rf"(?<![\w-]){re.escape(entity.name)}(?![\w-])", raw):  # a proper noun: "again" is not Again
                out.append(f"{entity.name} (#{entity.id}) is named on screen but the player never heard of them")
    from engine.standing_page import known_factions  # the page decides which factions the player knows
    town = here[0] if here else None
    heard = set(known_factions(world, player_id, town)) if town is not None else set()
    heard_names = {world.entity(f).name.lower() for f in heard}  # minor factions far apart can share a name
    for faction in world.entities("faction"):
        if faction.name.lower() not in heard_names and mentions(faction.name.lower(), text):
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


def check_realms(world) -> list[str]:
    """Phase 4f spec 7, rules 1, 2 and 4: one inheritance, no one inside who should not be, the ceiling holds."""
    import systems.realm_gates as G
    import systems.secret_realms as SR
    import systems.tournaments as T
    import systems.world_events as W
    out = []
    realms = world.get_meta("secret_realms") or []
    live = {}  # realm -> its live opening, from one pass over the sky index
    for row in W.index(world):
        if row[W.TYPE] in SR.OPENINGS and not row[W.DONE]:
            occurrence = world.entity(row[W.ID])
            live[occurrence.data["data"]["realm"]] = occurrence
    for realm in realms:
        entity = world.entity(realm)
        claims = entity.data.get("claims", 0)
        if claims > 1 or (claims == 1) != (entity.data["inheritance_claimed_by"] is not None):
            out.append(f"{entity.name}'s inheritance was claimed {claims} times")
        inside = world.sources(realm, "located_in")
        if not inside:
            continue
        occurrence = live.get(realm)
        t = occurrence.data["data"] if occurrence is not None else {}
        open_ = occurrence is not None and W.stage_at(occurrence.data, world.time) == "active"
        cap = G.ceiling_of(world, realm)
        for person in inside:
            p = world.entity(person)
            if p is None or p.kind != "person" or p.data.get("realm_spirit"):
                continue
            sealed = person in entity.data["sealed"]
            if not sealed and person not in t.get("entered", []):  # entered this opening: sealed when it closes
                out.append(f"{p.name} (#{person}) is inside {entity.name} but neither entered it nor is sealed there")
            if not sealed and open_ and cap is not None and T.realm_of(world, person) > cap:
                out.append(f"{p.name} (#{person}) is inside {entity.name} above its ceiling")
    player = world.get_meta("player_id")
    if player is not None and world.entity(player) is not None:
        pos = world.entity(player).data.get("delve")
        inside = [r for r in world.targets(player, "located_in") if r in realms]
        if pos is None and inside and player not in world.entity(inside[0]).data["sealed"]:
            out.append("the player is inside a realm with no delve position")
        if pos is not None:
            floors = world.entity(pos["realm"]).data["floors"] if pos["realm"] in realms else []
            if inside != [pos["realm"]] or not 1 <= pos["floor"] <= len(floors) \
                    or not 0 <= pos["chamber"] < len(floors[pos["floor"] - 1]):
                out.append(f"the player's delve position {pos} does not fit the realm they are in")
    return out


def check_crises(world) -> list[str]:
    """Succession crises (phase 4g spec 8): one live crisis a faction, pointed at, with the seat empty."""
    import systems.claimants as C
    import systems.succession_crisis as SC
    import systems.world_events as W
    out, live = [], {}
    for row in W.index(world):
        if row[W.TYPE] != SC.KIND:
            continue
        occurrence = world.entity(row[W.ID])
        crisis = occurrence.data["data"]
        if crisis["phase"] == "settled":
            continue
        faction = crisis["faction"]
        if faction in live:
            out.append(f"the {world.entity(faction).name} has two live crises")
        live[faction] = occurrence.id
        if world.entity(faction).data.get("crisis") != occurrence.id:
            out.append(f"the {world.entity(faction).name} does not point at its crisis #{occurrence.id}")
        claimants = {c["person"] for c in crisis["claimants"]}
        if any(p not in claimants for p in C.staff(world, faction, ("leader",))):
            out.append(f"the {world.entity(faction).name} has a leader during its crisis")  # a holder must be a claimant
    for faction in world.entities("faction"):
        pointed = faction.data.get("crisis")
        if pointed is not None and SC.live(world, faction.id) is not None and live.get(faction.id) != pointed:
            out.append(f"the {faction.name} points at #{pointed}, which is no live crisis of theirs")
    parents: dict = {}
    for faction in world.entities("faction"):
        if faction.data.get("parent") is not None:
            parents[faction.data["parent"]] = parents.get(faction.data["parent"], 0) + 1
    for parent, count in parents.items():
        if count > 2:
            out.append(f"the {world.entity(parent).name} has {count} breakaways")
    for token in world.entities("treasure"):
        if token.data.get("kind") == "sect_token":
            places = len(world.sources(token.id, "owns")) + len(world.targets(token.id, "located_in"))
            if places != 1:
                out.append(f"{token.name} is in {places} places")
    return out


def check_plots(world) -> list[str]:
    """Plots (phase 4h spec 12): the index holds exactly the open ones; their people exist; clues point true."""
    import systems.plots as P
    import systems.succession_crisis as SC
    out = []
    listed = set(P.open_plots(world))
    for plot in world.entities("plot"):
        d = plot.data
        if (d["state"] == "open") != (plot.id in listed):
            out.append(f"{plot.name} (#{plot.id}) is {d['state']} but {'in' if plot.id in listed else 'not in'} the open index")
        for key in ("plotter", "target", "faction"):
            if isinstance(d.get(key), int) and world.entity(d[key]) is None:
                out.append(f"{plot.name} points at missing #{d[key]} ({key})")
        for c in d["clues"]:
            if c["points_to"] != d["plotter"] and not c.get("false"):
                out.append(f"{plot.name}'s {c['kind']} clue points at #{c['points_to']}, not its plotter")
        if d["state"] == "exposed":
            occurrence = SC.live(world, d["faction"])
            if occurrence is not None and SC.claimant(SC.crisis_of(occurrence), d["plotter"]) is not None:
                out.append(f"{plot.name}'s exposed plotter still claims the seat")
        if d["type"] == "spy" and d["state"] == "open" and world.entity(d["plotter"]) is not None \
                and not world.entity(d["plotter"]).data.get("dead"):
            found = world.relations_from(d["plotter"], "member_of")
            if not any(f == d["faction"] and data.get("status", "member") == "member" for f, _, data in found):
                out.append(f"{plot.name}: the spy is no longer of the sect they spy on")
    import systems.frames as R
    for person in R.exiles(world):
        if not (world.entity(person).data.get("framed") or {}).get("returns_at"):
            out.append(f"{world.entity(person).name} waits in exile with no return")
    for pid in listed:
        if world.entity(pid) is None or world.entity(pid).kind != "plot":
            out.append(f"the open index lists #{pid}, which is no plot")
    return out
