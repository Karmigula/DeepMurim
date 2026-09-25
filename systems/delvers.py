"""Rival delvers in full detail (phase 4f spec 4.3): the sects' bands inside with the player.

When the player enters, the bands chosen at the gate are placed inside (the strong deeper). After
each thing the player does, every band takes one step: it loots, fights a guardian, tries the
inheritance, moves on, or heads for the gate in time. Two rival bands in one chamber clash. A band
in the player's chamber bars the way until it lets them pass or is beaten; a hostile one may strike first.
"""

import systems.delve as D
import systems.realm_gates as G
import systems.secret_realms as SR
from systems import factions as F
from systems.attitude import attitude
from systems.facts import make_variant, place_name, record_fact
from systems.tournaments import alive, realm_of
from world.events import Event, commit, effect, listen
from world.seed import rng_for

GUARDIAN_BASE, GUARDIAN_PER_REALM = 0.5, 0.15
INHERIT_CHANCE = 0.1  # a band's: the shade stands one realm above whoever comes (plan ruling 4)
CLASH_DEATH = 0.5
AMBUSH_CHANCE = 0.5
PASS_SCORE, WARM_SCORE = -0.3, 1.0
PROUD = frozenset({"proud", "hot-tempered"})


def _clamp(value: float, bounds) -> float:
    return min(bounds[1], max(bounds[0], value))


def _opening(world, player: int):
    pos = D.position(world, player)
    occurrence = SR.opening_of(world, pos["realm"]) if pos else None
    return world.entity(occurrence) if occurrence is not None else None


def members(world, team: dict, realm: int) -> list[int]:
    return [p for p in team["members"] if alive(world, p) and world.targets(p, "located_in") == [realm]]


def leader(world, team: dict) -> int:
    return max(team["members"], key=lambda p: (alive(world, p), realm_of(world, p), -p))


def rivals(world, team_a: dict, team_b: dict) -> bool:
    """Two bands fall on each other: sects at odds, or a proud member among them."""
    a, b = team_a["faction"], team_b["faction"]
    if a is not None and b is not None and a != b and F.stance(world, a, b) <= F.HOSTILE:
        return True
    return any(PROUD & set(world.entity(p).data.get("traits", ())) for p in team_a["members"] + team_b["members"])


# --- placing the bands ----------------------------------------------------------------------------------

def placement_events(world, occurrence) -> list[Event]:
    t = occurrence.data["data"]
    realm = world.entity(t["realm"])
    floors = realm.data["floors"]
    rng = rng_for(world.world_seed, f"realm:{occurrence.id}:placed")
    at = []
    for team in t["teams"]:
        floor = min(len(floors), max(1, max(realm_of(world, p) for p in team["members"])))
        chambers = floors[floor - 1]
        wanted = [c for c, room in enumerate(chambers) if room["kind"] == "rivals"] or list(range(len(chambers)))
        at.append([floor, rng.choice(wanted)])
    return [Event("delvers_placed", (), realm.id, {"occurrence": occurrence.id, "at": at})]


@effect("delvers_placed")
def _placed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    teams, inside = [], []
    for team, at in zip(t["teams"], event.data["at"]):
        for person in team["members"]:
            if alive(world, person):
                world.unrelate(person, "located_in")
                world.relate(person, event.place, "located_in")
                world.update_data(person, delve_at=at)
                inside.append(person)
        teams.append({**team, "at": at, "let_pass": [], "with": None, "with_floor": None, "left": False})
    world.update_data(occurrence.id, data={**t, "teams": teams, "placed": True, "entered": t["entered"] + inside})


@listen("realm_entered")
def _place_on_entry(world, event, event_id: int) -> None:
    occurrence = world.entity(event.data["occurrence"])
    if not occurrence.data["data"].get("placed") and occurrence.data["data"]["teams"]:
        commit(world, placement_events(world, occurrence))


# --- each step -----------------------------------------------------------------------------------------------

def step_events(world, player: int) -> list[Event]:
    occurrence = _opening(world, player)
    if occurrence is None or not occurrence.data["data"].get("placed"):
        return []
    t = occurrence.data["data"]
    realm = world.entity(t["realm"])
    floors = realm.data["floors"]
    pos = D.position(world, player)
    days = D.days_left(world, occurrence.id)
    rng = rng_for(world.world_seed, f"step:{occurrence.id}:{world.time}")
    moves, extra = [], []
    for i, team in enumerate(t["teams"]):
        alive_in = members(world, team, realm.id)
        if team.get("left") or not team.get("at") or not alive_in:
            continue
        f, c = team["at"]
        room = floors[f - 1][c]
        best = max(alive_in, key=lambda p: (realm_of(world, p), -p))
        step = {"team": i, "at": [f, c], "took": None, "slew": False, "left": False}
        if team.get("with") == player:
            step["at"] = [pos["floor"], pos["chamber"]]  # travelling together
        elif days <= f:  # time to make for the gate: a day a floor
            if f == 1 and c == 0:
                step["left"] = True
            else:
                step["at"] = [f, c - 1] if c > 0 else [f - 1, len(floors[f - 2]) - 1]
        elif room["kind"] == "treasure" and room["state"] == "untouched":
            step["took"] = room["contents"]["prize"]
        elif room["kind"] == "guardian" and room["state"] == "untouched":
            gap = realm_of(world, best) - room["contents"]["realm"]
            if rng.random() < _clamp(GUARDIAN_BASE + GUARDIAN_PER_REALM * gap, (0.05, 0.95)):
                step["slew"] = True
            else:
                weakest = min(alive_in, key=lambda p: (realm_of(world, p), p))
                extra.append(Event("died", (weakest, weakest), realm.id, {"cause": "realm", "world": True}))
        elif room["kind"] == "inheritance" and realm.data["inheritance_claimed_by"] is None \
                and [f, c] != [pos["floor"], pos["chamber"]]:
            if rng.random() < INHERIT_CHANCE:
                extra.append(Event("inheritance_won", (best,), realm.id, {"realm": realm.id}))
        elif c < len(floors[f - 1]) - 1:
            step["at"] = [f, c + 1]
        elif room["kind"] == "stair" and f < len(floors):
            step["at"] = [f + 1, 0]
        moves.append(step)
    clashes = _clashes(world, t["teams"], moves, realm.id, rng)
    events = [Event("delvers_stepped", (), realm.id, {"occurrence": occurrence.id, "moves": moves, "clashes": clashes})]
    for clash in clashes:
        killer = leader(world, t["teams"][clash["winner"]])
        events += [Event("died", (killer, p), realm.id, {"cause": "realm", "world": True}) for p in clash["dead"]]
    return events + extra


def _clashes(world, teams: list, moves: list, realm: int, rng) -> list[dict]:
    """Two bands that end in one chamber and are at odds fight: by the realm gap, the losers die or flee."""
    where: dict = {}
    for step in moves:
        if not step["left"]:
            where.setdefault(tuple(step["at"]), []).append(step["team"])
    clashes = []
    for at, found in sorted(where.items()):
        if len(found) < 2:
            continue
        a, b = found[0], found[1]
        if not rivals(world, teams[a], teams[b]):
            continue
        ra, rb = (max(realm_of(world, p) for p in members(world, teams[i], realm)) for i in (a, b))
        winner = a if rng.random() < _clamp(0.5 + 0.15 * (ra - rb), (0.1, 0.9)) else b
        loser = b if winner == a else a
        dead = [p for p in members(world, teams[loser], realm) if rng.random() < CLASH_DEATH]
        clashes.append({"winner": winner, "loser": loser, "dead": dead, "at": list(at)})
    return clashes


@effect("delvers_stepped")
def _stepped(world, event) -> None:
    from systems.races import make_prize
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    teams = [dict(team) for team in t["teams"]]
    realm = t["realm"]
    gate = world.entity(realm).data["gate"]
    for step in d["moves"]:
        team = teams[step["team"]]
        f, c = team["at"]
        if step["took"] is not None:
            make_prize(world, leader(world, team), step["took"], f"realm:{realm}:{f}:{c}:{world.time}")
            D.set_chamber(world, realm, f, c, state="looted")
        if step["slew"]:
            D.set_chamber(world, realm, f, c, state="slain")
        team["at"] = step["at"]
        if team.get("with") is not None and team.get("with_floor") != step["at"][0]:
            team["with"], team["with_floor"] = None, None  # a floor together, and they go their own way
        if step["left"]:
            team["left"] = True
            for person in members(world, team, realm):
                world.unrelate(person, "located_in")
                world.relate(person, gate, "located_in")
                world.update_data(person, delve_at=None)
        else:
            for person in members(world, team, realm):
                world.update_data(person, delve_at=step["at"])
    for clash in d["clashes"]:
        loser = teams[clash["loser"]]
        f, c = loser["at"]
        loser["at"] = [f, c - 1] if c > 0 else ([f - 1, 0] if f > 1 else [f, c])  # the survivors flee back
        for person in members(world, loser, realm):
            if person not in clash["dead"]:
                world.update_data(person, delve_at=loser["at"])
    world.update_data(occurrence.id, data={**t, "teams": teams})


@listen("delvers_stepped")
def _came_out(world, event, event_id: int) -> None:
    """A band that reaches the gate tells of it (spec §5)."""
    d = event.data
    t = world.entity(d["occurrence"]).data["data"]
    realm = world.entity(t["realm"])
    gate = realm.data["gate"]
    for step in d["moves"]:
        if step["left"]:
            for person in t["teams"][step["team"]]["members"]:
                if alive(world, person):
                    variant = make_variant("delved", person, None, place=place_name(world, gate))
                    variant.update(realm_name=realm.name, realm_id=realm.id)
                    record_fact(world, person, "delved", None, place=gate, weight=1.0, variant=variant)


@effect("inheritance_won")
def _won(world, event) -> None:
    realm = event.data["realm"]
    G.inherit(world, event.actors[0], realm)
    floors = world.entity(realm).data["floors"]
    D.set_chamber(world, realm, len(floors), len(floors[-1]) - 1, state="passed")


# --- the player and the bands -------------------------------------------------------------------------------

def here(world, player: int) -> list[int]:
    """The bands in the player's chamber (their indexes on the opening)."""
    occurrence = _opening(world, player)
    pos = D.position(world, player)
    if occurrence is None or not pos:
        return []
    t = occurrence.data["data"]
    return [i for i, team in enumerate(t["teams"]) if not team.get("left") and team.get("at") == [pos["floor"], pos["chamber"]]
            and members(world, team, t["realm"])]


def blocking(world, player: int) -> bool:
    occurrence = _opening(world, player)
    if occurrence is None:
        return False
    teams = occurrence.data["data"]["teams"]
    return any(player not in teams[i].get("let_pass", []) and teams[i].get("with") != player for i in here(world, player))


def _hostile_to(world, team: dict, player: int) -> bool:
    mine = [f for f, _, d in F.memberships(world, player) if d.get("status", "member") == "member"]
    return team["faction"] is not None and any(F.stance(world, team["faction"], f) <= F.HOSTILE for f in mine)


def pass_events(world, player: int, i: int) -> list[Event]:
    occurrence = _opening(world, player)
    team = occurrence.data["data"]["teams"][i]
    head = leader(world, team)
    granted = attitude(world, head, player).score > PASS_SCORE and not _hostile_to(world, team, player)
    return [Event("pass_asked", (player, head), D.position(world, player)["realm"],
                  {"occurrence": occurrence.id, "team": i, "granted": granted})]


@effect("pass_asked")
def _asked(world, event) -> None:
    d = event.data
    if d["granted"]:
        occurrence = world.entity(d["occurrence"])
        t = occurrence.data["data"]
        teams = [dict(team) for team in t["teams"]]
        teams[d["team"]]["let_pass"] = teams[d["team"]].get("let_pass", []) + [event.actors[0]]
        world.update_data(occurrence.id, data={**t, "teams": teams})


def rout_events(world, player: int, i: int) -> list[Event]:
    occurrence = _opening(world, player)
    head = leader(world, occurrence.data["data"]["teams"][i])
    return [Event("band_routed", (player, head), D.position(world, player)["realm"],
                  {"occurrence": occurrence.id, "team": i})]


@effect("band_routed")
def _routed(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    teams = [dict(team) for team in t["teams"]]
    teams[d["team"]]["let_pass"] = teams[d["team"]].get("let_pass", []) + [event.actors[0]]  # beaten, they give way
    world.update_data(occurrence.id, data={**t, "teams": teams})


def join_events(world, player: int, i: int) -> list[Event]:
    occurrence = _opening(world, player)
    team = occurrence.data["data"]["teams"][i]
    if attitude(world, leader(world, team), player).score < WARM_SCORE:
        return []
    return [Event("band_joined", (player, leader(world, team)), D.position(world, player)["realm"],
                  {"occurrence": occurrence.id, "team": i, "floor": D.position(world, player)["floor"]})]


@effect("band_joined")
def _joined(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    teams = [dict(team) for team in t["teams"]]
    teams[d["team"]].update({"with": event.actors[0], "with_floor": d["floor"]})
    world.update_data(occurrence.id, data={**t, "teams": teams})


def ambusher(world, player: int) -> int | None:
    """A band in your chamber that strikes first: hostile to you, or proud and stronger (chance 0.5)."""
    occurrence = _opening(world, player)
    if occurrence is None:
        return None
    teams = occurrence.data["data"]["teams"]
    for i in here(world, player):
        team = teams[i]
        if player in team.get("let_pass", []) or team.get("with") == player:
            continue
        head = leader(world, team)
        proud = PROUD & set(world.entity(head).data.get("traits", ())) and realm_of(world, head) > realm_of(world, player)
        if (attitude(world, head, player).score <= -1.0 or proud or _hostile_to(world, team, player)) \
                and rng_for(world.world_seed, f"ambush:{occurrence.id}:{i}:{world.time}").random() < AMBUSH_CHANCE:
            return head
    return None
