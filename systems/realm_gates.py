"""The gate of a secret realm (phase 4f spec 4): who may enter, the jade tokens, who the sects send,
and what becomes of them when the gate closes far from the player. The sealed walk out at the next opening.

Level of detail (spec §2.5): the delvers are chosen when the gate opens and nobody moves. If the
player never enters, one `realm_closed` event settles every fate when the gate closes; only the
sealed leave their towns. (When the player is inside, Task 6 closes the gate instead.)
"""

import systems.lives as lives
import systems.secret_realms as SR
import systems.world_events as W
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.founding import make_person
from systems.membership import set_membership
from systems.realms import REALMS, add_energy, realm_index
from systems.tournaments import alive, realm_of
from world.events import Event, effect, listen
from world.seed import rng_for

RANGE = 3
TOKENS = (3, 8)
PER_SECT, PER_SECT_TOKEN = 3, 2
MAX_DELVERS = 12  # spec §4.2: four to twelve go in
HEADS = frozenset({"leader", "elder"})  # a sect's heads stay home: the young generation goes in
WANDERER_CHANCE, MAX_WANDERERS = 0.3, 3
OUT_BASE, OUT_PER_FLOOR, DEAD_CHANCE = 0.6, 0.05, 0.25
LOOT_CHANCE = 0.5
INHERIT_CHANCE = 0.1  # an NPC's: the shade stands one realm above whoever comes (plan ruling 4)
SEALED_GROWTH = 3.0  # the dense qi of a realm: three times the cultivation
WEAPON_VALUE = 1500


# --- who may enter -----------------------------------------------------------------------------

def ceiling_of(world, realm: int) -> int | None:
    rule = world.entity(realm).data["rule"]
    return realm_index(rule["value"]) if rule["kind"] == "ceiling" else None


def tokens_of(world, person: int, realm: int) -> list[int]:
    found = []
    for item in world.targets(person, "owns"):
        entity = world.entity(item)
        if entity is not None and entity.kind == "treasure" and entity.data.get("kind") == "token" \
                and entity.data.get("realm") == realm and not entity.data.get("used"):
            found.append(item)
    return found


def near_sects(world, gate: int) -> list[int]:
    """Staffed factions with a home within RANGE regions of the gate, as 4d's races count them; nearest first."""
    xy = W.place_xy(world, gate)
    found = []
    for faction in world.entities("faction"):
        fd = faction.data
        if fd.get("type") not in F.STAFFED or fd.get("type") == "player_sect" or fd.get("dissolved") or "home" not in fd:
            continue
        if xy is not None and max(abs(fd["home"][0] - xy[0]), abs(fd["home"][1] - xy[1])) <= RANGE:
            found.append((max(abs(fd["home"][0] - xy[0]), abs(fd["home"][1] - xy[1])), faction.id))
    return [f for _, f in sorted(found)]


def _member_of_near(world, person: int, gate: int) -> bool:
    near = set(near_sects(world, gate))
    return any(f in near and d.get("status", "member") == "member" for f, _, d in F.memberships(world, person))


def admits(world, realm: int, person: int) -> str | None:
    """Why the gate refuses this person, or None. (A quota's sponsor and sneaking in are the engine's.)"""
    rule = world.entity(realm).data["rule"]
    cap = ceiling_of(world, realm)
    if cap is not None and realm_of(world, person) > cap:
        return f"The seal presses you back; it will not admit a {REALMS[realm_of(world, person)].name}."
    if rule["kind"] == "token" and not tokens_of(world, person, realm):
        return "The gate will not open without a jade token of this realm."
    if rule["kind"] == "quota" and not _member_of_near(world, person, world.entity(realm).data["gate"]):
        return "No sect near this gate has given you one of its places."
    return None


def _near_player(world, gate: int) -> bool:
    """Whether the player is in the gate's region: only there are wanderers made (level of detail, plan ruling 21)."""
    player = world.get_meta("player_id")
    here = world.targets(player, "located_in") if player is not None else []
    return bool(here) and W.place_xy(world, here[0]) == W.place_xy(world, gate)


def _strongest(world, faction: int, cap: int | None, count: int) -> list[int]:
    able = [p for p, _, d in world.relations_to(faction, "member_of")  # one query; below the sect's heads
            if d.get("status", "member") == "member" and d.get("role") not in HEADS and alive(world, p)
            and not world.entity(p).data.get("is_player") and not world.entity(p).data.get("sealed_in")]
    able = [p for p in able if cap is None or realm_of(world, p) <= cap]
    return sorted(able, key=lambda p: (-realm_of(world, p), p))[:count]


# --- the stages -------------------------------------------------------------------------------------

def token_events(world, occurrence) -> list[Event]:
    """At `announced`: 3-8 jade tokens, half to the near sects' strongest, the rest to wanderers at the gate."""
    t = occurrence.data["data"]
    realm = world.entity(t["realm"])
    if realm.data["rule"]["kind"] != "token" or t["tokens"]:
        return []
    gate = occurrence.data["place"]
    rng = rng_for(world.world_seed, f"realm:{occurrence.id}:tokens")
    count = rng.randint(*TOKENS)
    holders = []
    for faction in near_sects(world, gate):
        if len(holders) >= (count + 1) // 2:
            break
        holders += [p for p in _strongest(world, faction, None, 1) if p not in holders]
    i = 0
    while len(holders) < count and _near_player(world, gate):  # far away, only the sects hold tokens
        holders.append(make_person(world, f"realm:{occurrence.id}:holder:{i}", gate, occupation="wandering swordsman",
                                   age=rng.randint(18, 40), realm=rng.choice(("third-rate", "second-rate"))))
        i += 1
    return [Event("tokens_made", (), gate, {"occurrence": occurrence.id, "realm": realm.id, "holders": holders})]


@effect("tokens_made")
def _tokens_made(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    name = world.entity(d["realm"]).name
    tokens = []
    for holder in d["holders"]:
        token = world.add_entity("treasure", f"a jade token of {name}",
                                 {"kind": "token", "realm": d["realm"], "used": False, "value": 120})
        world.relate(holder, token, "owns")
        tokens.append(token)
    world.update_data(occurrence.id, data={**occurrence.data["data"], "tokens": tokens})


def delver_events(world, occurrence) -> list[Event]:
    """When the gate opens: the near sects send their strongest who pass the rule; wanderers may come too."""
    t = occurrence.data["data"]
    if t["delvers"]:
        return []
    realm, gate = t["realm"], occurrence.data["place"]
    rule = world.entity(realm).data["rule"]["kind"]
    cap = ceiling_of(world, realm)
    teams = []
    if rule == "token":
        holders = [p for token in t["tokens"] for p in world.sources(token, "owns")
                   if alive(world, p) and not world.entity(p).data.get("is_player")]
        by_sect: dict = {}
        for p in sorted(set(holders)):
            sect = next((f for f, _, d in F.memberships(world, p) if d.get("status", "member") == "member"
                         and world.entity(f).data.get("type") in F.STAFFED), None)
            by_sect.setdefault(sect, []).append(p)
        for sect, members in sorted(by_sect.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):
            teams += [{"faction": sect, "members": members[:PER_SECT_TOKEN]}] if sect is not None \
                else [{"faction": None, "members": [p]} for p in members]
    else:
        for faction in near_sects(world, gate):
            room = MAX_DELVERS - sum(len(team["members"]) for team in teams)
            members = _strongest(world, faction, cap, min(PER_SECT, room))
            if members:
                teams.append({"faction": faction, "members": members})
        rng = rng_for(world.world_seed, f"realm:{occurrence.id}:wanderers")
        realms = [r for r in ("third-rate", "second-rate", "first-rate") if cap is None or realm_index(r) <= cap]
        for i in range(MAX_WANDERERS if _near_player(world, gate) else 0):  # nobody made far from the player
            if rng.random() < WANDERER_CHANCE and sum(len(team["members"]) for team in teams) < MAX_DELVERS:
                wanderer = make_person(world, f"realm:{occurrence.id}:wanderer:{i}", gate,
                                       occupation="wandering swordsman", age=rng.randint(18, 45),
                                       realm=rng.choice(realms))
                teams.append({"faction": None, "members": [wanderer]})
    return [Event("delvers_chosen", (), gate, {"occurrence": occurrence.id, "teams": teams})]


@effect("delvers_chosen")
def _delvers_chosen(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    delvers = [p for team in d["teams"] for p in team["members"]]
    for person in delvers:  # a token passes one through the gate and is gone
        for token in tokens_of(world, person, t["realm"])[:1]:
            world.unrelate(person, "owns", token)
            world.update_data(token, used=True)
    world.update_data(occurrence.id, data={**t, "teams": d["teams"], "delvers": delvers})


def walk_out_events(world, occurrence) -> list[Event]:
    """When the gate opens again, those sealed at the last closing walk out (spec §4.4)."""
    realm = world.entity(occurrence.data["data"]["realm"])
    sealed = [p for p in realm.data["sealed"] if alive(world, p) and not world.entity(p).data.get("is_player")]
    if not sealed:
        return []
    return [Event("walked_out", tuple(sealed), occurrence.data["place"], {"realm": realm.id})]


@effect("walked_out")
def _walked_out(world, event) -> None:
    realm = world.entity(event.data["realm"])
    now = lives.current_season(world)
    for person in event.actors:
        entity = world.entity(person)
        seasons = max(0, now - entity.data["sealed_in"]["season"])
        body = load_body(world, person)  # the dense qi, and time at half pace (spec §4.4)
        add_energy(body, seasons / 4 * SEALED_GROWTH * 0.5)
        save_body(world, person, body)
        world.update_data(person, sealed_in=None, lived_to=now,
                          age=round(float(entity.data.get("age", 30)) + seasons / 8, 2))
        world.unrelate(person, "located_in")
        world.relate(person, event.place, "located_in")
        for faction, _, data in F.memberships(world, person):
            if data.get("status") == "missing":
                taken = data.get("role") == "leader" and any(  # the sect chose another while they were gone
                    d.get("role") == "leader" and d.get("status", "member") == "member" and alive(world, p)
                    for p, _, d in world.relations_to(faction, "member_of") if p != person)
                set_membership(world, person, faction, status="member", **({"role": "elder"} if taken else {}))
    world.update_data(realm.id, sealed=[p for p in realm.data["sealed"] if p not in event.actors])


# --- the gate closes far from the player ----------------------------------------------------------

def shade_realm(world, challenger: int) -> int:
    """The master's remnant always stands one realm above whoever challenges it (spec §3.2; plan ruling 4)."""
    return min(len(REALMS) - 1, realm_of(world, challenger) + 1)


def closing_events(world, occurrence, still_inside: bool = False) -> list[Event]:
    """The gate closes: each delver's fate rolled. `still_inside`: only those not already out are rolled for
    (the player went in, and left or fell before the end)."""
    t = occurrence.data["data"]
    if t["closed"]:
        return []
    realm = world.entity(t["realm"])
    floors = len(realm.data["floors"])
    rng = rng_for(world.world_seed, f"realm:{occurrence.id}:close")
    fates, loot = {}, {}
    for person in t["delvers"]:
        if not alive(world, person) or (still_inside and world.targets(person, "located_in") != [realm.id]):
            continue
        depth = min(floors, max(1, realm_of(world, person)))
        roll, out = rng.random(), OUT_BASE - OUT_PER_FLOOR * max(0, depth - 2)
        fate = "out" if roll < out else "dead" if roll < out + DEAD_CHANCE else "sealed"
        fates[str(person)] = fate
        if fate == "out" and rng.random() < LOOT_CHANCE:
            loot[str(person)] = SR.prize_at(rng, depth)
    inherited = None
    survivors = [int(p) for p, f in fates.items() if f == "out"]
    if realm.data["inheritance_claimed_by"] is None and survivors:
        best = max(survivors, key=lambda p: (realm_of(world, p), -p))
        if rng.random() < INHERIT_CHANCE:
            inherited = best
    gate = occurrence.data["place"]
    events = [Event("realm_closed", (), gate, {"occurrence": occurrence.id, "realm": realm.id, "fates": fates,
                                               "loot": loot, "inherited": inherited})]
    events += [Event("died", (int(p), int(p)), gate, {"cause": "realm", "world": True})
               for p, f in fates.items() if f == "dead"]
    return events


def seal(world, person: int, realm: int) -> None:
    """Shut in until the next opening: out of the world, their sect counting them missing (spec §4.4)."""
    world.update_data(person, sealed_in={"realm": realm, "season": lives.current_season(world)})
    world.unrelate(person, "located_in")
    world.relate(person, realm, "located_in")
    for faction, _, data in ([] if world.entity(person).data.get("is_player") else F.memberships(world, person)):
        if data.get("status", "member") == "member":  # the player keeps their posts: their sect waits (Task 6)
            set_membership(world, person, faction, status="missing")
    entity = world.entity(realm)
    if person not in entity.data["sealed"]:
        world.update_data(realm, sealed=entity.data["sealed"] + [person])


def inherit(world, person: int, realm: int) -> None:
    """The master's legacy: their art complete, their weapon, and the title of their last disciple."""
    from systems.techniques import teach
    entity = world.entity(realm)
    master = entity.data["master"]
    teach(world, person, master["art"], completeness=1.0, known_completeness=1.0, source="inheritance")
    weapon = world.add_entity("treasure", master["weapon"], {"kind": "weapon", "used": False, "value": WEAPON_VALUE})
    world.relate(person, weapon, "owns")
    titles = list(world.entity(person).data.get("titles", []))
    world.update_data(person, titles=titles + [f"Last Disciple of {master['name']}"])
    world.update_data(realm, inheritance_claimed_by=person, claims=entity.data.get("claims", 0) + 1)


@effect("realm_closed")
def _closed(world, event) -> None:
    from systems.races import make_prize
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "closed": True})
    for person, prize in d["loot"].items():
        make_prize(world, int(person), prize, f"{occurrence.id}:{person}")
    for person, fate in d["fates"].items():
        if fate == "sealed":
            seal(world, int(person), d["realm"])
        elif fate == "out" and world.targets(int(person), "located_in") == [d["realm"]]:
            world.update_data(int(person), delve_at=None)  # a band still inside walks out at the gate
            world.unrelate(int(person), "located_in")
            world.relate(int(person), occurrence.data["place"], "located_in")
    if d["inherited"] is not None:
        inherit(world, d["inherited"], d["realm"])
    realm = world.entity(d["realm"])
    fates = list(d["fates"].values())
    line = {"season": lives.current_season(world), "entered": len(t["delvers"]), "died": fates.count("dead"),
            "sealed": fates.count("sealed"), "took": len(d["loot"]), "inherited": d["inherited"]}
    world.update_data(realm.id, history=realm.data["history"] + [line])


@listen("realm_closed")
def _closed_news(world, event, event_id: int) -> None:
    """Only those who came out can tell it (spec §5)."""
    d = event.data
    realm = world.entity(d["realm"])
    where = place_name(world, event.place)
    for person, fate in d["fates"].items():
        p = int(person)
        if fate == "out":
            variant = make_variant("delved", p, None, place=where)
            variant.update(realm_name=realm.name, realm_id=realm.id)
            record_fact(world, p, "delved", None, place=event.place, source_event=event_id, weight=1.0,
                        variant=variant)
        elif fate == "sealed":
            variant = make_variant("sealed", p, None, place=where)
            variant.update(realm_name=realm.name, realm_id=realm.id)
            record_fact(world, p, "sealed", None, place=event.place, source_event=event_id, weight=1.5,
                        variant=variant)
    for person, prize in d["loot"].items():
        variant = make_variant("took", int(person), None, place=where)
        variant.update(realm_name=realm.name, realm_id=realm.id, prize=prize["kind"])
        record_fact(world, int(person), "took", None, place=event.place, source_event=event_id, weight=1.0,
                    variant=variant)
    if d["inherited"] is not None:
        variant = make_variant("inherited", d["inherited"], None, place=where)
        variant.update(realm_name=realm.name, realm_id=realm.id, master=realm.data["master"]["name"])
        record_fact(world, d["inherited"], "inherited", None, place=event.place, source_event=event_id, weight=3.0,
                    variant=variant)


def stage_events(world, occurrence, stage: str) -> list[Event]:
    if stage == "announced":
        return token_events(world, occurrence)
    if stage == "active":
        from systems.chambers import renew_events  # each opening, the chambers renew (Task 4)
        from systems.sealed import unseal_events
        return (renew_events(world, occurrence) + walk_out_events(world, occurrence) + unseal_events(world, occurrence)
                + delver_events(world, occurrence))
    if stage == "aftermath":
        player = world.get_meta("player_id")
        if player not in occurrence.data["data"]["entered"]:
            return closing_events(world, occurrence)
        realm = occurrence.data["data"]["realm"]
        if not alive(world, player) or world.targets(player, "located_in") != [realm]:
            return closing_events(world, occurrence, still_inside=True)  # left or fell early: no one saw the rest
        from systems.sealed import inside_closing_events  # the player was inside: what happened, happened (Task 6)
        return inside_closing_events(world, occurrence)
    return []
