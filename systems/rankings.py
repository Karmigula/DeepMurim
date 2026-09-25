"""The Heavenly Ranking Pavilion (phase 4d spec 6): who stands where under heaven, as far as the Pavilion has heard.

The Pavilion is an `institution` and a knower (3a). Its informants hear deeds from afar,
giving each fact two chances (plan ruling 3). Each spring it surveys the public figures of
the staffed factions (ruling 4), scores everyone it believes in, and publishes four lists as
one `published` fact (ruling 2). The lists are knowledge, not truth: the hidden stay hidden,
and the dead stay listed until the Pavilion hears of the death.
"""

import systems.world_clock as world_clock
import systems.world_events as W
from systems import factions as F
from systems.beliefs import believe
from systems.facts import make_variant, place_name, record_fact
from systems.lives import LIFESPAN
from systems.realms import realm_index
from world.events import Event, effect, listen
from world.gen.materialize import ensure_town
from world.gen.region import region_spec
from world.gen.town import town_spec
from world.seed import rng_for

LISTS = (("heaven", 10), ("earth", 20), ("human", 30))
YOUNG, YOUNG_AGE = 10, 30
TITLES = {"heaven": "of Heaven", "earth": "of Earth", "human": "of Men", "young": "among the Young Dragons"}
ORDINALS = ("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth",
            "Eleventh", "Twelfth", "Thirteenth", "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth",
            "Eighteenth", "Nineteenth", "Twentieth", "Twenty-first", "Twenty-second", "Twenty-third",
            "Twenty-fourth", "Twenty-fifth", "Twenty-sixth", "Twenty-seventh", "Twenty-eighth", "Twenty-ninth",
            "Thirtieth")
RANK_RENOWN = {"heaven": 12.0, "earth": 8.0, "human": 5.0, "young": 5.0}
TIER_FACTS = frozenset({"broke_through", "tribulation", "assessed", "enlightened", "treasure"})
HEARD = TIER_FACTS | {"defeated", "died", "killed", "bested", "won_tournament"}
CHAMPION_POINTS = {"grand_assembly": 60.0, "dragon_phoenix": 40.0}  # other tournaments: 10 (phase 4e)
DEEDS = frozenset({"defeated", "bested", "treasure", "enlightened", "won_tournament"})
FORGET_YEARS = 25  # a deed fades by 0.8 a year: after 25 it is worth under half a percent
INFORMANT_REACH, INFORMANT_FALL = 0.9, 0.85
WIN_POINTS, WIN_SHARE, TREASURE_POINTS, ENLIGHTENED_POINTS = 10.0, 0.6, 30.0, 20.0
DEED_FADE = 0.8
SILENCE_YEARS = 40  # a master unheard of for this long is presumed dead or gone (final review)
PUBLIC_ROLES = ("leader", "elder")
YEAR = 4 * W.SEASON


# --- the Pavilion ------------------------------------------------------------------------------

def capital(world) -> int:
    """The city nearest the heart of the world (region 0, 0), seeded; the Pavilion stands there."""
    found = world.get_meta("capital")
    if found is not None:
        return found
    town = None
    for radius in range(4):
        ring = [(x, y) for x in range(-radius, radius + 1) for y in range(-radius, radius + 1)
                if max(abs(x), abs(y)) == radius]
        for x, y in ring:
            for i in range(region_spec(world.world_seed, x, y).town_count):
                if town is None and town_spec(world.world_seed, x, y, i).kind == "city":
                    town = ensure_town(world, x, y, i)
        if town is not None:
            break
    town = town if town is not None else ensure_town(world, 0, 0, 0)
    world.set_meta("capital", town)
    return town


def pavilion(world) -> int | None:
    return world.get_meta("pavilion")


def ensure_pavilion(world) -> int:
    found = pavilion(world)
    if found is not None:
        return found
    town = capital(world)
    found = world.add_entity("institution", "the Heavenly Ranking Pavilion",
                             {"kind": "rankings", "town": town, "lists": None, "year": None, "scores": {},
                              "fact": None}, "institution:pavilion")
    world.set_meta("pavilion", found)
    return found


# --- what reaches the Pavilion ------------------------------------------------------------------

def _hears(world, fact, home, attempt: int) -> bool:
    origin = W.place_xy(world, fact.place) if fact.place is not None else None
    distance = 0 if origin is None or home is None else max(abs(origin[0] - home[0]), abs(origin[1] - home[1]))
    return rng_for(world.world_seed, f"pavilion:{fact.id}:{attempt}").random() < INFORMANT_REACH * INFORMANT_FALL ** distance


def informants(world, n: int) -> None:
    """Deeds at least a season old reach the Pavilion, less often from far away; each gets two chances."""
    pav = ensure_pavilion(world)
    home = W.place_xy(world, world.entity(pav).data["town"])
    mark = world.get_meta("pavilion_mark", 0)
    retry = world.get_meta("pavilion_retry", [])
    fresh = world.facts_after(mark, world.time - W.SEASON, HEARD)
    keep = [[f, due] for f, due in retry if due > world.time]
    for fact in fresh:
        if _hears(world, fact, home, 0):
            believe(world, pav, fact.id, fact.variant, None, 0.9, 1, "informant")
        else:
            keep.append([fact.id, world.time + YEAR])
    for fact_id, due in retry:
        fact = world.fact(fact_id) if due <= world.time else None
        if fact is not None and _hears(world, fact, home, 1):
            believe(world, pav, fact.id, fact.variant, None, 0.8, 2, "informant")
    world.set_meta("pavilion_mark", max([mark] + [f.id for f in fresh]))
    world.set_meta("pavilion_retry", keep)


def survey(world) -> None:
    """Each spring the Pavilion takes the measure of every sect's leaders and elders (plan ruling 4)."""
    pav = ensure_pavilion(world)
    known = {(b.variant.get("actor"), b.variant.get("realm")) for b, f in world.known_facts(pav) if f.predicate == "assessed"}
    for faction in world.entities("faction"):
        fd = faction.data
        if fd.get("type") not in F.STAFFED or fd.get("type") == "player_sect" or fd.get("dissolved"):
            continue
        for person in F.members_of(world, faction.id):
            found = F.membership(world, person, faction.id)
            entity = world.entity(person)
            realm = entity.data.get("realm", "mortal")
            if not found or found[1].get("role") not in PUBLIC_ROLES or (person, realm) in known \
                    or entity.data.get("is_player"):
                continue
            variant = make_variant("assessed", person, faction.id, place=place_name(world, fd.get("seat")), realm=realm)
            variant["age"] = int(entity.data.get("age", 30))
            fact = record_fact(world, person, "assessed", faction.id, place=fd.get("seat"), weight=1.0,
                               variant=variant, spread=False)
            believe(world, pav, fact, variant, None, 1.0, 0, "survey")


# --- scoring --------------------------------------------------------------------------------------

def scores(world, pav: int) -> dict[int, float]:
    """Everyone the Pavilion believes in, scored: realm tier x 100, plus deeds that fade year by year."""
    last = world.entity(pav).data.get("scores") or {}
    tier, deeds, dead, heard = {}, {}, set(), {}
    known = world.known_facts(pav)
    won_duels = {f.source_event for _, f in known if f.predicate == "defeated" and f.source_event is not None}
    for belief, fact in known:
        v, predicate = belief.variant, fact.predicate
        if predicate == "died":
            dead.add(fact.subject)
            continue
        if predicate == "killed" and v.get("target") is not None:
            dead.add(v["target"])
            if fact.source_event in won_duels:
                continue  # the player's duel already counted as a win (plan ruling 5)
        who = v.get("actor")
        if who is None:
            continue
        heard[who] = max(heard.get(who, 0), fact.time)
        realm = realm_index(v["realm"]) if v.get("realm") else None
        if realm is not None and (predicate in TIER_FACTS or predicate in ("defeated", "killed", "bested")):
            tier[who] = max(tier.get(who, 0), realm)
        fade = DEED_FADE ** max(0, (world.time - fact.time) // YEAR)
        if predicate in ("defeated", "killed", "bested"):  # an NPC's killing records no `defeated`; a bout `bested`
            points = WIN_POINTS + WIN_SHARE * last.get(str(v.get("target")), 0.0)
        else:
            points = {"treasure": TREASURE_POINTS, "enlightened": ENLIGHTENED_POINTS}.get(predicate, 0.0)
            if predicate == "won_tournament":
                points = CHAMPION_POINTS.get(v.get("kind"), 10.0)
        if points:
            deeds[who] = deeds.get(who, 0.0) + points * fade
    ages = believed_ages(world, pav)
    out = {}
    for who in set(tier) | set(deeds):
        entity = world.entity(who)
        if who in dead or entity is None or entity.kind not in ("person", "persona"):
            continue
        if world.time - heard.get(who, 0) > SILENCE_YEARS * YEAR:
            continue  # silent for a lifetime of rumours: presumed dead or gone (final review)
        if ages.get(who, 0) > LIFESPAN[min(tier.get(who, 0), len(LIFESPAN) - 1)]:
            continue  # older than anyone of that realm lives
        out[who] = round(tier.get(who, 0) * 100 + deeds.get(who, 0.0), 2)
    return out


def believed_ages(world, pav: int) -> dict[int, int]:
    """How old the Pavilion thinks people are: the newest age it was told, plus the years since."""
    newest: dict = {}
    for belief, fact in world.known_facts(pav):
        who, age = belief.variant.get("actor"), belief.variant.get("age")
        if who is not None and age is not None and (who not in newest or fact.time > newest[who][1]):
            newest[who] = (age, fact.time)
    return {who: int(age + (world.time - t) // YEAR) for who, (age, t) in newest.items()}


# --- publishing ------------------------------------------------------------------------------------

def revision_events(world, n: int) -> list[Event]:
    pav = ensure_pavilion(world)
    table = scores(world, pav)
    order = sorted(table, key=lambda p: (-table[p], p))
    lists, start = {}, 0
    for name, size in LISTS:
        lists[name] = order[start:start + size]
        start += size
    ages = believed_ages(world, pav)
    lists["young"] = [p for p in order if ages.get(p, YOUNG_AGE + 1) <= YOUNG_AGE][:YOUNG]
    entrants = sorted({p for names in lists.values() for p in names})
    return [Event("rankings_published", (pav, *entrants), world.entity(pav).data["town"],
                  {"year": n // 4 + 1, "lists": lists, "scores": {str(p): table[p] for p in table}})]


@effect("rankings_published")
def _published(world, event) -> None:
    d = event.data
    world.update_data(event.actors[0], lists=d["lists"], year=d["year"], scores=d["scores"])


@listen("rankings_published")
def _published_news(world, event, event_id: int) -> None:
    pav, d = event.actors[0], event.data
    variant = make_variant("published", pav, None, place=place_name(world, event.place))
    variant.update(year=d["year"], first=(d["lists"]["heaven"] or [None])[0])
    fact = record_fact(world, pav, "published", None, place=event.place, weight=3.0,  # no witnesses: the named hear it by rumour
                       variant=variant, extra={"lists": d["lists"]})  # the lists once, not in every believer's copy
    world.update_data(pav, fact=fact)


def season_hook(world, n: int) -> list[Event]:
    """Every season the informants report; every spring the lists are revised."""
    ensure_pavilion(world)
    informants(world, n)
    if n % 4:
        return []
    world.forget(pavilion(world), DEEDS, world.time - FORGET_YEARS * YEAR)  # faded deeds (4e ruling 11)
    survey(world)
    return revision_events(world, n)


world_clock.SEASON_HOOKS.append(season_hook)


# --- reading the lists ----------------------------------------------------------------------------

def latest(world, knower: int) -> dict | None:
    """The newest lists this knower has heard of: {"year", "lists", "time"}."""
    found = world.newest_known(knower, "published", "year")  # one row, however many lists an old town heard (4e)
    if found is None:
        return None
    belief, fact = found
    return {"year": belief.variant.get("year", 0), "lists": fact.data.get("lists", {}), "time": fact.time}


def rank_of(lists: dict, person: int) -> tuple[str, int] | None:
    for name in ("heaven", "earth", "human", "young"):
        names = lists.get(name, [])
        if person in names:
            return name, names.index(person) + 1
    return None


def rank_of_you(world, lists: dict, player: int) -> tuple[str, int] | None:
    """The player's best place on these lists, as themselves or behind one of their masks."""
    order = ("heaven", "earth", "human", "young")
    selves = [player] + [p.id for p in world.entities("persona") if p.data.get("of") == player]
    found = [f for f in (rank_of(lists, s) for s in selves) if f]
    return min(found, key=lambda f: (order.index(f[0]), f[1])) if found else None


def title(name: str, place: int) -> str:
    return f"{ORDINALS[place - 1]} {TITLES[name]}"


def rank_known_in(world, town: int, person: int) -> tuple[str, float] | None:
    """(title, renown) if this town has heard lists that name this person."""
    known = latest(world, town)
    found = rank_of(known["lists"], person) if known else None
    return (title(*found), RANK_RENOWN[found[0]]) if found else None


def post_in_city(world, player: int, town: int) -> bool:
    """Cities post the Pavilion's newest lists; arriving in one teaches them (spec §6.5)."""
    pav = pavilion(world)
    fact_id = world.entity(pav).data.get("fact") if pav is not None else None
    if fact_id is None or world.entity(town).data.get("kind") != "city":
        return False
    fact = world.fact(fact_id)
    believe(world, town, fact.id, fact.variant, None, 1.0, 1, "posted")
    return believe(world, player, fact.id, fact.variant, town, 1.0, 1, "posted")


def best_rank(world, person: int) -> str | None:
    """The highest place this person ever held on the Pavilion's lists, as a title (the lineage page's pride)."""
    order = ("heaven", "earth", "human", "young")
    best = None
    for entry in world.chronicle_of_kind("rankings_published"):
        found = rank_of(entry.data["lists"], person)
        if found and (best is None or (order.index(found[0]), found[1]) < (order.index(best[0]), best[1])):
            best = found
    return title(*best) if best else None
