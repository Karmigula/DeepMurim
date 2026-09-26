"""Who may lead a sect in crisis (phase 4g spec 3.2, 4.1, 4.3): the chief disciple, claimants, voters and their leanings.

Leanings are computed, never stored (like 3a attitude): only the player's sways are kept, on the crisis.
"""

from systems import factions as F
from systems.attitude import attitude
from systems.facts import make_variant, place_name, record_fact
from systems.kin import kin_of
from systems.tournaments import alive, realm_of
from world.events import Event, effect, listen

AMBITIOUS = frozenset({"proud", "cunning", "greedy"})  # no new trait: world seeds stay as they are (plan ruling 3)
CLAN_TYPES = frozenset({"martial_clan", "local_clan"})
MAX_CLAIMANTS = 3
ADULT, BLOOD_AGE = 16, 14
NAMING_SEASON = 0  # the chief disciple is named in the first season of each year
PLAYER_FAVOUR = 0.5  # the leader's attitude that names a player member chief disciple
BACKING = 0.2  # a voter backs their best claimant only if they lean this far
REALM_LEAN = 0.2
PROOF_LEAN = {"chief": 0.2, "blood": 0.3, "will": 0.5, "transmission": 0.4, "token": 0.3,  # blood: in clans only
              "truth": 0.5}  # 4h: a returned heir whose frame was exposed
LOYAL_LEAN = 0.2


def ambitious(world, person: int) -> bool:
    return bool(AMBITIOUS & set(world.entity(person).data.get("traits", ())))


def role_in(world, person: int, faction: int) -> str | None:
    found = F.membership(world, person, faction)
    if not found or found[1].get("status", "member") != "member":
        return None
    return found[1].get("role")


def age_of(world, person: int) -> float:
    return float(world.entity(person).data.get("age", 30))


def staff(world, faction: int, roles) -> list[int]:
    """Living members in good standing of these roles, anywhere (one query)."""
    return [p for p, _, d in world.relations_to(faction, "member_of")
            if d.get("status", "member") == "member" and d.get("role") in roles and alive(world, p)]


def fit(world, person, faction: int) -> bool:
    """A named heir who can take the seat: alive, of the faction, not sealed away, grown."""
    return isinstance(person, int) and alive(world, person) and role_in(world, person, faction) is not None \
        and not world.entity(person).data.get("sealed_in") and age_of(world, person) >= ADULT


def _best(world, people: list[int]) -> int | None:
    return min(people, key=lambda p: (-realm_of(world, p), age_of(world, p), p)) if people else None


# --- the chief disciple (spec 3.2) ------------------------------------------------------------

def name_chief_events(world, faction: int, n: int) -> list[Event]:
    """Once a year the faction names its chief disciple, if the post is empty or its holder can no longer hold it."""
    data = world.entity(faction).data
    if n % 4 != NAMING_SEASON or data.get("type") not in F.STAFFED or data.get("dissolved"):
        return []
    held = data.get("heir")
    if held is not None and fit(world, held, faction) and role_in(world, held, faction) in ("keeper", "disciple"):
        return []
    leaders = staff(world, faction, ("leader", "regent"))
    player = world.get_meta("player_id")
    mine = F.membership(world, player, faction) if isinstance(player, int) else None
    chosen = None
    if mine and mine[1].get("status", "member") == "member" and mine[0] >= 2 and mine[1].get("role") != "leader" \
            and leaders and attitude(world, leaders[0], player).score >= PLAYER_FAVOUR:
        chosen = player
    if chosen is None:
        chosen = _best(world, [p for p in staff(world, faction, ("keeper", "disciple"))
                               if not world.entity(p).data.get("is_player")])
    if chosen is None or chosen == held:
        return []
    return [Event("named_chief", (chosen,), data.get("seat"), {"faction": faction, "season": n})]


@effect("named_chief")
def _named(world, event) -> None:
    world.update_data(event.data["faction"], heir=event.actors[0])


@listen("named_chief")
def _named_news(world, event, event_id: int) -> None:
    variant = make_variant("named_chief", event.actors[0], event.data["faction"], place=place_name(world, event.place))
    record_fact(world, event.actors[0], "named_chief", event.data["faction"], place=event.place,
                source_event=event_id, weight=1.5, variant=variant)


# --- claimants (spec 4.1) ---------------------------------------------------------------------

def declare(world, faction: int, leader: int | None) -> list[dict]:
    """Who claims the seat, in order, until there are three: chief disciple, blood heir, ambitious elders."""
    data = world.entity(faction).data
    out: list[dict] = []

    def add(person, kind):
        if person is not None and all(c["person"] != person for c in out) and len(out) < MAX_CLAIMANTS:
            out.append({"person": person, "kind": kind})
    heir = data.get("heir")
    if isinstance(heir, int) and alive(world, heir) and role_in(world, heir, faction) is not None \
            and not world.entity(heir).data.get("sealed_in"):
        add(heir, "chief")
    for kin, role in (kin_of(world, leader) if leader is not None else []):
        if role == "child" and alive(world, kin) and age_of(world, kin) >= BLOOD_AGE \
                and (data["type"] in CLAN_TYPES or role_in(world, kin, faction) is not None):
            add(kin, "blood")
    elders = sorted(staff(world, faction, ("elder",)), key=lambda p: (-realm_of(world, p), p))
    if out and all(age_of(world, c["person"]) < ADULT for c in out) and elders:
        add(elders[0], "regent")  # only children claim by right: the senior elder claims to rule for them (spec 4.1)
    for elder in elders:
        best = max((realm_of(world, c["person"]) for c in out), default=-1)
        if ambitious(world, elder) or realm_of(world, elder) >= best - 1:
            add(elder, "elder")
    return out


# --- voters and leanings (spec 4.3) -----------------------------------------------------------

def voters(world, faction: int) -> list[int]:
    """The elders and hall keepers, at the seat and the branches; the player if a member of rank 2 or more."""
    out = staff(world, faction, ("elder", "keeper"))
    player = world.get_meta("player_id")
    mine = F.membership(world, player, faction) if isinstance(player, int) else None
    if mine and mine[1].get("status", "member") == "member" and mine[0] >= 2 and player not in out:
        out.append(player)
    return sorted(out)


def proofs(world, crisis: dict, claimant: dict) -> list[str]:
    """What speaks for a claimant: the chief disciple's post, blood (in a clan), a read will naming them,
    the late master's transmission, the leader's token in their hands."""
    person, found = claimant["person"], []
    if claimant["kind"] == "chief":
        found.append("chief")
    if claimant["kind"] == "blood" and world.entity(crisis["faction"]).data["type"] in CLAN_TYPES:
        found.append("blood")
    will = crisis.get("will") or {}
    if will.get("state") == "read" and will.get("names") == person:
        found.append("will")
    if crisis.get("transmitted") == person:
        found.append("transmission")
    token = crisis.get("token")
    if token is not None and person in world.sources(token, "owns"):
        found.append("token")
    plot = world.entity(claimant["plot"]) if claimant.get("plot") is not None else None
    if claimant["kind"] == "returned" and plot is not None and plot.data.get("state") == "exposed":
        found.append("truth")
    return found


def proof_lean(world, crisis: dict, claimant: dict) -> float:
    return sum(PROOF_LEAN.get(p, 0.0) for p in proofs(world, crisis, claimant))


def lean(world, crisis: dict, voter: int, claimant: dict, full: bool = True) -> float:
    """How far `voter` leans to `claimant`: attitude (full detail only), realm, proofs, sways, loyalty."""
    person = claimant["person"]
    if voter == person:
        return 9.0  # claimants back themselves
    realms = [realm_of(world, c["person"]) for c in crisis["claimants"]]
    value = REALM_LEAN * (realm_of(world, person) - min(realms))
    value += proof_lean(world, crisis, claimant)
    value += crisis.get("sways", {}).get(str(voter), {}).get(str(person), 0.0)
    if full and not world.entity(voter).data.get("is_player"):
        value += attitude(world, voter, person).score
    if "loyal" in world.entity(voter).data.get("traits", ()) and person == named(world, crisis):
        value += LOYAL_LEAN
    return round(value, 3)


def named(world, crisis: dict) -> int | None:
    """Whom the late leader named: the will's name if it was read (Task 2), else the chief disciple."""
    will = crisis.get("will") or {}
    if will.get("state") == "read":
        return will.get("names")
    return next((c["person"] for c in crisis["claimants"] if c["kind"] == "chief"), None)


def camps(world, crisis: dict, full: bool = True) -> tuple[dict[int, list[int]], list[int]]:
    """({claimant: [backers]}, undecided): each voter backs their best claimant if they lean far enough."""
    backing: dict[int, list[int]] = {c["person"]: [c["person"]] for c in crisis["claimants"]}
    undecided = []
    declared = {int(k): v for k, v in crisis.get("declared", {}).items()}
    for voter in voters(world, crisis["faction"]):
        if voter in backing:
            continue
        if voter in declared and declared[voter] in backing:
            backing[declared[voter]].append(voter)
            continue
        if world.entity(voter).data.get("is_player"):
            undecided.append(voter)
            continue
        leans = [(lean(world, crisis, voter, c, full), c["person"]) for c in crisis["claimants"]]
        best, person = max(leans, key=lambda p: (p[0], -p[1])) if leans else (0.0, None)
        if person is not None and best >= BACKING:
            backing[person].append(voter)
        else:
            undecided.append(voter)
    return backing, undecided


def votes(world, crisis: dict, backing: dict[int, list[int]]) -> dict[int, int]:
    """Each backer counts one vote; the Grand Elder three, for whomever they back or for themself (spec 4.2)."""
    heavy = {crisis.get("grand_elder_backs"), crisis.get("grand_elder")} - {None}
    return {c: len(b) + (2 if c in heavy else 0) for c, b in backing.items()}


@listen("succeeded")
def _seat_filled(world, event, event_id: int) -> None:
    """A new leader: the fallen leader is mourned, and a chief disciple who rose leaves the post empty."""
    d = event.data
    if d["role"] != "leader":
        return
    data = world.entity(d["faction"]).data
    world.update_data(d["faction"], fallen=None, poisoned=None,
                      **({"heir": None} if data.get("heir") == event.actors[0] else {}))
