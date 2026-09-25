"""Murim tournaments (phase 4e spec 3-4): brackets seeded by belief, rounds by day, and what the winner takes.

A tournament is a 4d world-event occurrence. Its kind's module (systems/events/<kind>.py) sets the
size, the round days, who may enter and whom to invite; this module does the rest. The bracket
lives in the occurrence's `data["data"]`:

    {"kind", "size", "round_days", "registered", "entrants", "rounds", "champion", "finished",
     "prize", "title", "edition", "arts", ...}

A match is {"a", "b", "winner", "day", "how", "on"}. `how` is "sim" (NPCs fought), "bout" (the
player fought), "bye", "walkover" (a fighter was gone), "forfeit" (the player's day passed) or
"disqualified". Matches play out during their day and resolve once it has passed, or when the
player fights them (spec §4.3).
"""

import systems.world_events as W
from systems import factions as F
from systems.bodies import load_body
from systems.combat_core import INTENTS
from systems.duel import best_art, ensure_npc_arts, fighter_for
from systems.duel_sim import simulate
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from systems.realms import REALMS, realm_index
from world.events import Event, commit, effect, listen
from world.seed import rng_for

KINDS = ("grand_assembly", "dragon_phoenix", "sect_contest")
KIND_WEIGHT = {"grand_assembly": 3.0, "dragon_phoenix": 2.0, "sect_contest": 1.0}
NEWSWORTHY = frozenset({"grand_assembly", "dragon_phoenix"})  # their every bout is talked of
LIST_WEIGHT = {"heaven": 3000, "earth": 2000, "human": 1000, "young": 500}
ORDINALS = ("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth")


# --- setting up ---------------------------------------------------------------------------------

def start_data(kind: str, size: int, round_days, prize: int, title: str, edition: int, **extra) -> dict:
    return {"kind": kind, "size": size, "round_days": list(round_days), "registered": [], "entrants": [],
            "rounds": [], "champion": None, "finished": False, "prize": prize, "title": title,
            "edition": edition, **extra}


def edition(world, kind: str) -> int:
    """How many of this kind have been held, counting the one about to start."""
    row = world._conn.execute("select count(*) from entities where kind = 'world_event' "
                              "and json_extract(data, '$.type') = ?", (kind,)).fetchone()
    return row[0] + 1


def ordinal(n: int) -> str:
    return ORDINALS[n - 1] if n <= len(ORDINALS) else f"{n}th"


def host_city(world, rng) -> int:
    """A materialized city, seeded per edition; the Pavilion's capital if none is known (plan ruling 6)."""
    cities = sorted(t.id for t in world.entities("town") if t.data.get("kind") == "city")
    if cities:
        return rng.choice(cities)
    from systems.rankings import capital
    return capital(world)


# --- people ----------------------------------------------------------------------------------------

def realm_of(world, person: int) -> int:
    entity = world.entity(person)
    if entity.data.get("is_player"):
        return load_body(world, person).realm
    return realm_index(entity.data.get("realm", "mortal"))


def alive(world, person) -> bool:
    entity = world.entity(person) if isinstance(person, int) else None
    return entity is not None and entity.kind == "person" and not entity.data.get("dead") \
        and not entity.data.get("vanished")


def strengths(world, town: int, people) -> dict[int, float]:
    """How strong the host town believes each of these people is: their place on the lists it has heard,
    then the weight of what it says of them. One indexed query for the whole field (plan ruling 8)."""
    from systems.rankings import latest, rank_of
    known = latest(world, town)
    wanted = set(people)
    renown = {**dict.fromkeys(wanted, 0.0), **(world.renown_among(town, sorted(wanted)) if wanted else {})}
    out = {}
    for person in wanted:
        found = rank_of(known["lists"], person) if known else None
        out[person] = (LIST_WEIGHT[found[0]] - found[1] if found else 0) + renown[person]
    return out


def belief_strength(world, town: int, person: int) -> float:
    return strengths(world, town, [person])[person]


def watched(world, occurrence) -> bool:
    """Whether the player is at the host town: only there are bouts simulated blow by blow (level of detail)."""
    player = world.get_meta("player_id")
    return player is not None and occurrence.data["place"] in world.targets(player, "located_in")


def positions(size: int) -> list[int]:
    """Seed numbers in bracket order, so the strongest meet last (1 v 32, 16 v 17, ...)."""
    order = [1]
    while len(order) < size:
        top = len(order) * 2 + 1
        order = [seed for s in order for seed in (s, top - s)]
    return order


def pool(world, occurrence, ok, size: int, wanderer) -> list[int]:
    """Whom the organisers invite: each staffed sect's best who qualifies, the ranked names the host town
    knows of, then wanderers to fill the bracket (spec §4.1)."""
    from systems.rankings import latest
    d = occurrence.data
    town = d["place"]
    registered = [p for p in d["data"]["registered"] if alive(world, p) and ok(p)]  # only those who qualify count
    found: list[int] = []
    for faction in world.entities("faction"):
        fd = faction.data
        if fd.get("type") not in F.STAFFED or fd.get("type") == "player_sect" or fd.get("dissolved"):
            continue
        able = [p for p, _, d in world.relations_to(faction.id, "member_of")  # one query; staff only (the strong)
                if d.get("status", "member") == "member" and d.get("role") not in (None, "member") and alive(world, p)
                and not world.entity(p).data.get("is_player") and ok(p)]
        if able:
            found.append(max(able, key=lambda p: (realm_of(world, p), -p)))
    known = latest(world, town)
    for names in (known["lists"].values() if known else []):
        found += [p for p in names if p not in found and alive(world, p)
                  and not world.entity(p).data.get("is_player") and ok(p)]
    found = [p for p in found if p not in registered]
    rng = rng_for(world.world_seed, f"tournament:{occurrence.id}:wanderers")
    i = 0
    while wanderer is not None and len(found) + len(registered) < size:  # a sect contest takes no outsiders
        found.append(wanderer(world, occurrence, i, rng))
        i += 1
    return found


# --- the bracket -----------------------------------------------------------------------------------

def qualifies(world, occurrence, person: int, slack: int = 0) -> bool:
    """Whether this person meets the rules of this tournament (its kind's module decides)."""
    from systems.sky import module
    check = getattr(module(occurrence.data["type"]), "qualifies", None)
    return check is None or check(world, occurrence, person, slack)


def day(occurrence, now: int) -> int:
    """The day of the active stage it is: 1 on the first day, 0 before it begins."""
    start = occurrence.data["active"][0]
    return 0 if now < start else (now - start) // 4 + 1


def day_start(occurrence, k: int) -> int:
    return occurrence.data["active"][0] + (k - 1) * 4


def ends(occurrence) -> int:
    """When the last bout must be fought: the active stage's end, unless a raid pushed the final past it."""
    return occurrence.data["data"].get("until", occurrence.data["active"][1])


def draw_events(world, occurrence, invited: list[int]) -> list[Event]:
    """The draw on the first day: registrants keep their places, invitations fill the rest, seeded by belief."""
    d = occurrence.data
    t, town = d["data"], d["place"]
    registered = [p for p in t["registered"] if alive(world, p) and qualifies(world, occurrence, p)]
    field = registered + [p for p in invited if p not in registered and alive(world, p)]
    field = field[: t["size"]]
    if watched(world, occurrence):
        strength = strengths(world, town, field)
    else:  # nobody sees this draw: seed by realm, without asking the town what it believes (plan ruling 7)
        strength = {p: realm_of(world, p) for p in field}
    ordered = sorted(field, key=lambda p: (-strength[p], p))
    arts = {}
    for person in ordered if watched(world, occurrence) else ():  # fighters prepare where the player can see
        if not world.entity(person).data.get("is_player"):
            ensure_npc_arts(world, person)
            art = best_art(world, person)
            arts[str(person)] = art.technique.id if art else None
    slots = [ordered[s - 1] if s <= len(ordered) else None for s in positions(t["size"])]
    days = t["round_days"]
    rounds = [[{"a": slots[i], "b": slots[i + 1], "winner": None, "day": days[0], "how": None, "on": None}
               for i in range(0, len(slots), 2)]]
    for r in range(1, len(days)):
        rounds.append([{"a": None, "b": None, "winner": None, "day": days[r], "how": None, "on": None}
                       for _ in range(len(rounds[-1]) // 2)])
    from systems.intrigue import plot  # at most one dark intervention, seeded at the draw (spec §5.4)
    return [Event("bracket_drawn", (), town, {"occurrence": occurrence.id, "entrants": ordered, "rounds": rounds,
                                              "arts": arts, "intrigue": plot(world, occurrence, rounds, ordered)})]


@effect("bracket_drawn")
def _drawn(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "entrants": event.data["entrants"],
                                           "rounds": event.data["rounds"], "arts": event.data["arts"],
                                           "intrigue": event.data.get("intrigue")})


def _fighter(world, occurrence, person: int):
    arts = occurrence.data["data"].get("arts") or {}
    if str(person) in arts:  # chosen at the draw: one body load per fighter, not two
        return fighter_for(world, person, arts[str(person)])
    art = best_art(world, person)
    return fighter_for(world, person, art.technique.id if art else None)


def _sim_winner(world, occurrence, a: int, b: int, r: int, i: int) -> int:
    from systems.intrigue import FIX_FACTOR, weaken, weakened
    rng = rng_for(world.world_seed, f"tournament:{occurrence.id}:{r}:{i}")
    weak = weakened(occurrence, r, i)  # a fixed bout: one fighter at 0.6 of their strength (spec §5.4)
    if not watched(world, occurrence):  # far from the player: decided by realm, with upsets (plan ruling 7)
        chance = max(0.1, min(0.9, 0.5 + 0.15 * (realm_of(world, a) - realm_of(world, b))))
        if weak == a:
            chance *= FIX_FACTOR
        elif weak == b:
            chance = 1 - (1 - chance) * FIX_FACTOR
        return a if rng.random() < chance else b
    for person in (a, b):
        ensure_npc_arts(world, person)
    fa, fb = _fighter(world, occurrence, a), _fighter(world, occurrence, b)
    fa, fb = (weaken(fa) if weak == a else fa), (weaken(fb) if weak == b else fb)
    result, _ = simulate(fa, fb, lambda r_, history: r_.choice(INTENTS), rng)
    if result == "draw":
        return a if rng.random() < 0.5 else b
    return a if result == "player" else b


def match_event(occurrence, r: int, i: int, winner, loser, how: str, now_day: int, world=None) -> Event:
    actors = tuple(p for p in (winner, loser) if p is not None)
    witnesses = ()
    if world is not None and how in ("sim", "bout"):  # the beaten remember who beat them (spec §5.3)
        from systems.arena import loser_witnesses
        witnesses = loser_witnesses(world, occurrence, winner, loser, f"{r}:{i}")
    return Event("match_resolved", actors, occurrence.data["place"],
                 {"occurrence": occurrence.id, "round": r, "match": i, "winner": winner, "loser": loser,
                  "how": how, "on": now_day}, witnesses=witnesses)


def _settle(world, occurrence, r: int, i: int, m: dict, now_day: int) -> Event:
    a, b = m["a"], m["b"]
    player = world.get_meta("player_id")
    here_a, here_b = alive(world, a), alive(world, b)
    if not here_a or not here_b:
        winner = a if here_a else b if here_b else None
        how = "bye" if None in (a, b) else "walkover"
    elif player in (a, b):
        winner, how = (b if a == player else a), "forfeit"  # the player's day passed without their bout
    else:
        winner, how = _sim_winner(world, occurrence, a, b, r, i), "sim"
    loser = (b if winner == a else a) if winner is not None else None
    return match_event(occurrence, r, i, winner, loser, how, now_day, world)


def _next_events(world, occurrence_id: int) -> list[Event]:
    occurrence = world.entity(occurrence_id)
    d = occurrence.data
    t = d["data"]
    if not t["rounds"] or t["finished"]:
        return []
    over = world.time >= ends(occurrence)
    now_day = day(occurrence, world.time)
    from systems.intrigue import due_events
    dark = due_events(world, occurrence, now_day, over)
    if dark:
        return dark
    player = world.get_meta("player_id")
    for r, matches in enumerate(t["rounds"]):
        due, waiting = [], False
        for i, m in enumerate(matches):
            if m["how"] is not None:
                continue
            if _due(t, r, m, now_day, over, player):
                due.append(_settle(world, occurrence, r, i, m, max(now_day, m["day"])))  # a round's matches are apart
            else:
                waiting = True
        if due:
            return due
        if waiting:
            return []  # this round is still being fought; the next cannot start
    return champion_events(occurrence, t["rounds"][-1][0]["winner"])


def _due(t: dict, r: int, m: dict, now_day: int, over: bool, player) -> bool:
    """A match resolves once its day has passed; NPCs settle at once when the next round is the same day."""
    if over or m["day"] < now_day or m["a"] is None or m["b"] is None:
        return True  # a bye needs no fighting (a round is only reached once the one before it is settled)
    same_day = r + 1 < len(t["rounds"]) and t["rounds"][r + 1][0]["day"] == m["day"]
    return same_day and m["day"] == now_day and player not in (m["a"], m["b"])


def resolve(world, occurrence_id: int) -> None:
    """Settle every match whose day has passed, round by round, and crown the champion after the final."""
    for _ in range(64):
        events = _next_events(world, occurrence_id)
        if not events:
            return
        commit(world, events)


@effect("match_resolved")
def _resolved(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    rounds = [list(r) for r in t["rounds"]]
    rounds[d["round"]][d["match"]] = dict(rounds[d["round"]][d["match"]], winner=d["winner"], how=d["how"], on=d["on"])
    if d["round"] + 1 < len(rounds):
        side = "a" if d["match"] % 2 == 0 else "b"
        nxt = d["match"] // 2
        rounds[d["round"] + 1][nxt] = dict(rounds[d["round"] + 1][nxt], **{side: d["winner"]})
    world.update_data(occurrence.id, data={**t, "rounds": rounds})


@listen("match_resolved")
def _noticed(world, event, event_id: int) -> None:
    d = event.data
    if d["how"] in ("sim", "bout") and d["winner"] is not None:
        from systems.arena import notice_events
        occurrence = world.entity(d["occurrence"])
        if watched(world, occurrence):  # elders in the crowd notice where the player is (level of detail)
            events = notice_events(world, occurrence, d["round"], d["winner"])
            if events:
                commit(world, events)


@listen("match_resolved")
def _bested(world, event, event_id: int) -> None:
    d = event.data
    if d["how"] not in ("sim", "bout") or d["winner"] is None or d["loser"] is None:
        return
    occurrence = world.entity(d["occurrence"])
    kind = occurrence.data["data"]["kind"]
    if kind not in NEWSWORTHY and not watched(world, occurrence):
        return  # a sect's own bouts far away are not news
    loser = world.entity(d["loser"])
    variant = make_variant("bested", d["winner"], d["loser"], place=place_name(world, event.place),
                           realm=REALMS[realm_of(world, loser.id)].label)
    variant["kind"] = kind
    record_fact(world, d["winner"], "bested", d["loser"], place=event.place, source_event=event_id,
                weight=0.5 + 0.25 * d["round"], variant=variant)


def champion_events(occurrence, champion) -> list[Event]:
    t = occurrence.data["data"]
    return [Event("tournament_won", (champion,) if champion is not None else (), occurrence.data["place"],
                  {"occurrence": occurrence.id, "champion": champion, "prize": t["prize"], "title": t["title"],
                   "kind": t["kind"]})]


@effect("tournament_won")
def _won(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "champion": d["champion"], "finished": True})
    if d["champion"] is not None:
        champion = world.entity(d["champion"])
        world.update_data(champion.id, silver=silver_of(world, champion.id) + d["prize"],
                          titles=list(champion.data.get("titles", [])) + [d["title"]])


@listen("tournament_won")
def _won_news(world, event, event_id: int) -> None:
    d = event.data
    t = world.entity(d["occurrence"]).data["data"]
    where = place_name(world, event.place)
    if d["champion"] is not None:
        variant = make_variant("won_tournament", d["champion"], None, place=where)
        variant.update(kind=d["kind"], title=d["title"])
        record_fact(world, d["champion"], "won_tournament", None, place=event.place, source_event=event_id,
                    weight=KIND_WEIGHT.get(d["kind"], 1.0), variant=variant)
    final = t["rounds"][-1][0] if t["rounds"] else {"a": None, "b": None, "winner": None}  # a summary has no bracket
    podium = [(final.get("b") if final["winner"] == final.get("a") else final.get("a"), 2)] \
        if t["rounds"] and final["winner"] is not None else []  # a void final has no runner-up
    if len(t["rounds"]) > 1:
        for m in t["rounds"][-2]:
            podium.append((m["b"] if m["winner"] == m["a"] else m["a"], 3))
    for person, place in podium:
        if person is not None and alive(world, person):
            variant = make_variant("placed", person, None, place=where)
            variant.update(kind=d["kind"], place=place)
            record_fact(world, person, "placed", None, place=event.place, weight=1.0 if place == 2 else 0.75,
                        variant=variant)
    from systems.sky import module
    rewards = getattr(module(d["kind"]), "rewards", None)
    if rewards is not None:
        events = rewards(world, world.entity(d["occurrence"]), d["champion"])
        if events:
            commit(world, events)


# --- the kinds' shared hooks ------------------------------------------------------------------------

SUMMARIZED = frozenset({"sect_contest"})  # far from the player, only its champion is decided (plan ruling 9)


def summary_events(world, occurrence, invite) -> list[Event]:
    """A contest nobody watched: the champion is drawn by lot, weighted by realm, from those who would enter."""
    field = [p for p in invite(world, occurrence) if alive(world, p)][: occurrence.data["data"]["size"]]
    if not field:
        return champion_events(occurrence, None)
    rng = rng_for(world.world_seed, f"tournament:{occurrence.id}:summary")
    weights = [1 + realm_of(world, p) for p in field]
    return champion_events(occurrence, rng.choices(field, weights=weights)[0])


def on_stage(world, occurrence, stage: str, invite) -> list[Event]:
    summarized = occurrence.data["data"]["kind"] in SUMMARIZED and not watched(world, occurrence)
    if stage == "active" and not summarized:
        return draw_events(world, occurrence, invite(world, occurrence))
    if stage == "over":
        if not occurrence.data["data"]["rounds"] and not occurrence.data["data"]["finished"]:
            return summary_events(world, occurrence, invite)
        resolve(world, occurrence.id)
        return compact_events(world.entity(occurrence.id))
    return []


KEPT = ("kind", "size", "round_days", "champion", "finished", "prize", "title", "edition", "faction", "presiding",
        "disqualified", "intrigue")


def compact_events(occurrence) -> list[Event]:
    """A finished bracket shrinks to its podium when the aftermath ends (plan ruling 5)."""
    t = occurrence.data["data"]
    if not t["rounds"] or t.get("compacted") or not t["finished"]:
        return []
    final = t["rounds"][-1][0]
    runner_up = (final["b"] if final["winner"] == final["a"] else final["a"]) if final["winner"] is not None else None
    semis = [m["b"] if m["winner"] == m["a"] else m["a"] for m in t["rounds"][-2]] if len(t["rounds"]) > 1 else []
    return [Event("bracket_compacted", (), occurrence.data["place"],
                  {"occurrence": occurrence.id, "runner_up": runner_up, "semis": [p for p in semis if p is not None],
                   "entrants": len(t["entrants"])})]


@effect("bracket_compacted")
def _compacted(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    t = occurrence.data["data"]
    kept = {k: t[k] for k in KEPT if k in t}
    world.update_data(occurrence.id, data={**kept, "registered": [], "entrants": [], "rounds": [], "bets": [],
                                           "compacted": {"runner_up": d["runner_up"], "semis": d["semis"],
                                                         "entrants": d["entrants"]}})


def on_observe(world, occurrence) -> list[Event]:
    resolve(world, occurrence.id)
    return []


# --- the player in a tournament (phase 4e spec 3, 4.3-4.4) -------------------------------------

BONDS = {"grand_assembly": 100, "dragon_phoenix": 30}
RULES = {"grand_assembly": "Only fighters of Second-rate and above may enter the Assembly.",
         "dragon_phoenix": "The Meet is for those of thirty or under.",
         "sect_contest": "Only the sect's own may enter its contest."}


def stage(world, occurrence_id: int) -> str:
    return W.stage_at(world.entity(occurrence_id).data, world.time)


def here(world, town: int, kinds, stages) -> int | None:
    """A tournament of one of these kinds in this town, at one of these stages."""
    for row in W.index(world):
        if row[W.TYPE] in kinds and row[W.PLACE] == town and not row[W.DONE] and stage(world, row[W.ID]) in stages:
            return row[W.ID]
    return None


def sponsor_of(world, player: int) -> int | None:
    """A faction that vouches for the player: one they belong to, or one that welcomes them (3b standing)."""
    from systems.standing import standing
    mine = sorted(f for f, _, d in F.memberships(world, player) if d.get("status", "member") == "member"
                  and world.entity(f).data.get("type") in F.STAFFED | {"player_sect"})
    if mine:
        return mine[0]
    for faction in world.entities("faction"):
        if faction.data.get("type") in F.STAFFED and not faction.data.get("dissolved") \
                and standing(world, faction.id, player).score >= 1:
            return faction.id
    return None


def _ranked(world, player: int) -> bool:
    from systems.rankings import latest, rank_of_you
    known = latest(world, player)
    return bool(known and rank_of_you(world, known["lists"], player))


def can_preside(world, occurrence_id: int, player: int) -> bool:
    t = world.entity(occurrence_id).data["data"]
    return t["kind"] == "sect_contest" and world.entity(t["faction"]).data.get("founder") == player


def register_block(world, occurrence_id: int, player: int) -> str | None:
    occurrence = world.entity(occurrence_id)
    t = occurrence.data["data"]
    if stage(world, occurrence_id) != "announced":
        return "Registration is not open."
    if player in t["registered"] or t.get("presiding") == player:
        return "You are already entered."
    if not qualifies(world, occurrence, player):
        return RULES.get(t["kind"], "You may not enter.")
    bond = BONDS.get(t["kind"], 0)
    if bond and sponsor_of(world, player) is None and not _ranked(world, player) \
            and world.entity(player).data.get("silver", 0) < bond:
        return f"You need a sponsor, a place on the Pavilion's lists, or a bond of {bond} silver."
    return None


def register_events(world, occurrence_id: int, player: int, preside: bool = False) -> list[Event]:
    t = world.entity(occurrence_id).data["data"]
    bond = 0 if preside or sponsor_of(world, player) is not None or _ranked(world, player) else BONDS.get(t["kind"], 0)
    return [Event("registered", (player,), world.entity(occurrence_id).data["place"],
                  {"occurrence": occurrence_id, "bond": bond, "preside": preside})]


@effect("registered")
def _registered(world, event) -> None:
    player, d = event.actors[0], event.data
    occurrence = world.entity(d["occurrence"])
    t = dict(occurrence.data["data"])
    if d["preside"]:
        t["presiding"] = player
    else:
        t["registered"] = t["registered"] + [player]
    if d["bond"]:
        t["bonds"] = {**t.get("bonds", {}), str(player): d["bond"]}
        world.update_data(player, silver=silver_of(world, player) - d["bond"])
    world.update_data(occurrence.id, data=t)


@listen("match_resolved")
def _bond_back(world, event, event_id: int) -> None:
    d = event.data
    t = world.entity(d["occurrence"]).data["data"]
    bond = t.get("bonds", {}).get(str(d["winner"]))
    if d["round"] == 0 and bond:
        commit(world, [Event("bond_refunded", (d["winner"],), event.place, {"occurrence": d["occurrence"], "silver": bond})])


@effect("bond_refunded")
def _refunded(world, event) -> None:
    person, d = event.actors[0], event.data
    occurrence = world.entity(d["occurrence"])
    bonds = {k: v for k, v in occurrence.data["data"].get("bonds", {}).items() if k != str(person)}
    world.update_data(occurrence.id, data={**occurrence.data["data"], "bonds": bonds})
    world.update_data(person, silver=silver_of(world, person) + d["silver"])


def player_call(world, player: int, town: int) -> tuple[int, int, int, int] | None:
    """(tournament, round, match, opponent) if the herald calls the player here today."""
    for row in W.index(world):
        if row[W.TYPE] not in KINDS or row[W.PLACE] != town or row[W.DONE]:
            continue
        occurrence = world.entity(row[W.ID])
        t = occurrence.data["data"]
        if not t["rounds"] or t["finished"] or world.time >= ends(occurrence):
            continue
        today = day(occurrence, world.time)
        for r, matches in enumerate(t["rounds"]):
            for i, m in enumerate(matches):
                if m["how"] is None and m["day"] == today and player in (m["a"], m["b"]):
                    other = m["b"] if m["a"] == player else m["a"]
                    if other is not None and alive(world, other):
                        return row[W.ID], r, i, other
    return None


def bout_result_events(world, occurrence_id: int, r: int, i: int, player: int, opponent: int, data: dict) -> list[Event]:
    occurrence = world.entity(occurrence_id)
    m = occurrence.data["data"]["rounds"][r][i]
    if m["how"] is not None:
        return []
    today = day(occurrence, world.time)
    if data.get("result") == "won" and data.get("verdict") == "kill":
        return [Event("disqualified", (player,), occurrence.data["place"], {"occurrence": occurrence_id, "victim": opponent}),
                match_event(occurrence, r, i, None, player, "disqualified", max(today, m["day"]))]
    if data.get("result") == "won":
        winner = player
    elif data.get("result") == "drawn":  # the judges favour the fighter the crowd believed stronger
        town = occurrence.data["place"]
        winner = max((player, opponent), key=lambda p: (belief_strength(world, town, p), -p))
    else:
        winner = opponent
    loser = opponent if winner == player else player
    return [match_event(occurrence, r, i, winner, loser, "bout", max(today, m["day"]), world)]


def forfeit_events(world, occurrence_id: int, player: int) -> list[Event]:
    call = player_call(world, player, world.entity(occurrence_id).data["place"])
    if call is None or call[0] != occurrence_id:
        return []
    occurrence = world.entity(occurrence_id)
    _, r, i, other = call
    return [match_event(occurrence, r, i, other, player, "forfeit", day(occurrence, world.time))]


@effect("disqualified")
def _disqualified(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "disqualified": t.get("disqualified", []) + [event.actors[0]]})


@listen("disqualified")
def _disgraced(world, event, event_id: int) -> None:
    killer, victim = event.actors[0], event.data["victim"]
    variant = make_variant("disgraced", killer, victim, place=place_name(world, event.place))
    record_fact(world, killer, "disgraced", victim, place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


def lei_tai_open(world, occurrence_id: int, player: int) -> bool:
    t = world.entity(occurrence_id).data["data"]
    return stage(world, occurrence_id) == "active" and t["holder"] not in (None, player) \
        and alive(world, t["holder"]) and player not in t.get("challenged", [])


def lei_tai_result_events(world, occurrence_id: int, player: int, holder: int, won: bool) -> list[Event]:
    return [Event("lei_tai_challenged", (player, holder), world.entity(occurrence_id).data["place"],
                  {"occurrence": occurrence_id, "won": won})]


@effect("lei_tai_challenged")
def _challenged(world, event) -> None:
    player, holder = event.actors
    occurrence = world.entity(event.data["occurrence"])
    t = occurrence.data["data"]
    world.update_data(occurrence.id, data={**t, "holder": player if event.data["won"] else holder,
                                           "challenged": t.get("challenged", []) + [player]})
