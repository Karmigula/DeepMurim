"""The player as plotter (phase 4h spec 8): poison, a spy, a puppet, a frame, a forgery.

Each scheme makes a plot like any other: its clues are left, it can leak, and it can be exposed. When one of
the player's plots is exposed the deed is told (weight 3.0), the righteous judge it, the town sets a bounty,
and a sect the player belongs to casts them out.
"""

import systems.claimants as C
import systems.frames as R
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.succession_crisis as SC
from systems import factions as F
from systems.bodies import load_body
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.purse import silver_of
from systems.tournaments import alive
from world.events import Event, Witness, commit, effect, listen
from world.seed import rng_for

POISON_PRICE, SPY_PRICE, FRAME_PRICE, FORGE_PRICE = 50, 100, 100, 100
FUND_PER_POWER = 10
FRAME_BASE, FRAME_PER_WIT, FRAME_BOUNDS = 0.4, 0.1, (0.1, 0.8)
NPC_FIND = 0.15
SPY_SWAY = 0.15
DEEDS = {"murder": "poisoner", "spy": "spymaster", "frame": "framer", "forgery": "forger", "puppet": "puppet_master"}
OPEN = ("mourning", "canvass")


def _pay(world, player: int, amount: int) -> None:
    world.update_data(player, silver=silver_of(world, player) - amount)


def _wit(world, player: int) -> int:
    return load_body(world, player).physique["comprehension"]


# --- poison -------------------------------------------------------------------------------------------------

def poisons_of(world, player: int) -> list[int]:
    return [i for i in world.targets(player, "owns") if world.entity(i).kind == "treasure"
            and world.entity(i).data.get("kind") == "poison" and not world.entity(i).data.get("used")]


def buy_poison_block(world, player: int, npc: int) -> str | None:
    selling = [f for f, _, d in F.memberships(world, npc) if d.get("role") == "keeper"
               and d.get("status", "member") == "member" and world.entity(f).data.get("type") == "unorthodox_clan"
               and world.targets(npc, "located_in") == [world.entity(f).data.get("seat")]]
    if not selling:
        return "They sell no poisons."
    if silver_of(world, player) < POISON_PRICE:
        return f"A poison costs {POISON_PRICE} silver."
    return None


def buy_poison_events(world, player: int, npc: int, place: int) -> list[Event]:
    return [Event("poison_bought", (player, npc), place, {"silver": POISON_PRICE})]


@effect("poison_bought")
def _bought(world, event) -> None:
    player, seller = event.actors
    _pay(world, player, POISON_PRICE)
    world.update_data(seller, silver=silver_of(world, seller) + POISON_PRICE)
    item = world.add_entity("treasure", "a vial of black lotus", {"kind": "poison", "value": POISON_PRICE,
                                                                  "used": False})
    world.relate(player, item, "owns")


def poison_block(world, player: int, leader: int) -> str | None:
    if not poisons_of(world, player):
        return "You carry no poison."
    led = [f for f, _, d in F.memberships(world, leader) if d.get("role") == "leader"
           and d.get("status", "member") == "member" and world.entity(f).data.get("type") in F.STAFFED]
    if not led or world.entity(leader).data.get("is_player"):
        return "They are no sect's master."
    return None


def poison_events(world, player: int, leader: int, place: int) -> list[Event]:
    """Into their tea: they die in the night of an illness, and a murder plot bears the player's name."""
    faction = next(f for f, _, d in F.memberships(world, leader) if d.get("role") == "leader"
                   and d.get("status", "member") == "member")
    vial = poisons_of(world, player)[0]
    rng = rng_for(world.world_seed, f"scheme:poison:{player}:{leader}")
    return [Event("poison_slipped", (player, leader), place, {"faction": faction, "vial": vial}),
            Event("died", (leader, leader), place, {"cause": "illness", "world": True, "poisoned_by": player})] \
        + M.murder_events(world, faction, leader, player, None, place, rng)


@effect("poison_slipped")
def _slipped(world, event) -> None:
    vial = event.data["vial"]
    world.unrelate(event.actors[0], "owns", vial)
    world.update_data(vial, used=True)


# --- a spy of one's own ----------------------------------------------------------------------------------

def spy_block(world, player: int, follower: int, faction: int) -> str | None:
    if world.entity(follower).data.get("sworn_to") != player or not alive(world, follower):
        return "They are not sworn to you."
    if world.entity(faction).data.get("type") not in F.STAFFED or F.membership(world, follower, faction):
        return "They cannot join that sect in secret."
    if silver_of(world, player) < SPY_PRICE:
        return f"Setting them up costs {SPY_PRICE} silver."
    return None


def spy_events(world, player: int, follower: int, faction: int, place: int) -> list[Event]:
    key = f"spy:player:{follower}:{faction}"
    return [Event("spy_sent", (player, follower), place, {"faction": faction})] + \
        U.spy_events(world, faction, player, follower, key)


@effect("spy_sent")
def _sent(world, event) -> None:
    player, follower = event.actors
    faction = event.data["faction"]
    _pay(world, player, SPY_PRICE)
    world.relate(follower, faction, "member_of", 0, {"role": "disciple", "hall": 0, "merit": 0, "status": "member",
                                                    "secret": False})
    world.unrelate(follower, "located_in")
    world.relate(follower, world.entity(faction).data["seat"], "located_in")
    world.update_data(follower, sworn_to=None)


def _spy_reports(world, plot, n: int, rng) -> list[Event]:
    """The player's spy reports one hidden truth of their sect's plots each season (spec 8)."""
    patron = plot.data["patron"]
    if not (isinstance(patron, int) and world.entity(patron).data.get("is_player")):
        return []
    secrets = [p for p in P.plots_of(world, plot.data["faction"]) if p.id != plot.id and patron not in p.data["known_by"]]
    if not secrets:
        return []
    return [Event("spy_reported", (patron,), None, {"plot": rng.choice(sorted(secrets, key=lambda p: p.id)).id})]


@effect("spy_reported")
def _reported(world, event) -> None:
    P.learn(world, event.actors[0], world.entity(event.data["plot"]), 0.8, "told")


# --- backing a puppet -----------------------------------------------------------------------------------

def fund_price(world, faction: int) -> int:
    return FUND_PER_POWER * int(world.entity(faction).data.get("power", 50))


def fund_block(world, player: int, occurrence, claimant: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "Their camps are made; silver comes too late."
    if F.membership(world, player, crisis["faction"]):
        return "You cannot buy your own sect's seat from outside it."
    if SC.claimant(crisis, claimant) is None or claimant == player:
        return "They do not claim the seat."
    if any(p.data["type"] == "puppet" and p.data.get("occurrence") == occurrence.id
           for p in P.plots_of(world, crisis["faction"], ("puppet",))):
        return "Someone's silver is already behind a claimant here."
    if silver_of(world, player) < fund_price(world, crisis["faction"]):
        return f"Backing a claim here costs {fund_price(world, crisis['faction'])} silver."
    return None


def fund_events(world, player: int, occurrence, claimant: int) -> list[Event]:
    from systems.founding import my_sect
    patron = my_sect(world, player) or player
    price = fund_price(world, SC.crisis_of(occurrence)["faction"])
    return [Event("claim_funded", (player, claimant), occurrence.data["place"], {"silver": price})] + \
        U.puppet_events(world, occurrence, patron, claimant, f"puppet:player:{occurrence.id}", plotter=player)


@effect("claim_funded")
def _funded(world, event) -> None:
    _pay(world, event.actors[0], event.data["silver"])


@listen("crisis_settled")
def _grateful(world, event, event_id: int) -> None:
    """A puppet the player bought who wins remembers who paid (spec 8)."""
    for plot in P.plots_of(world, event.data["faction"], ("puppet",)):
        plotter = plot.data["plotter"]
        if plot.data["serves"] == event.data["winner"] and world.entity(plotter).data.get("is_player"):
            commit(world, [Event("puppet_thanks", (plotter, event.data["winner"]), event.place, {},
                                 witnesses=(Witness(event.data["winner"], "grateful", 0.8),))])


# --- a frame, and a forgery -----------------------------------------------------------------------------

def frame_chance(world, player: int) -> float:
    low, high = FRAME_BOUNDS
    return max(low, min(high, FRAME_BASE + FRAME_PER_WIT * (_wit(world, player) - 5)))


def frame_block(world, player: int, occurrence, rival: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "It is too late to plant anything now."
    if SC.claimant(crisis, rival) is None or rival == player:
        return "They do not claim the seat."
    if silver_of(world, player) < FRAME_PRICE:
        return f"False evidence costs {FRAME_PRICE} silver."
    return None


def frame_events(world, player: int, occurrence, rival: int) -> list[Event]:
    """100 silver of false evidence: it takes, and the rival is cast out; or it fails, and points at the player."""
    rng = rng_for(world.world_seed, f"scheme:frame:{occurrence.id}:{rival}")
    key = f"frame:player:{occurrence.id}:{rival}"
    events = [Event("frame_paid", (player, rival), occurrence.data["place"], {"silver": FRAME_PRICE})]
    if rng.random() < frame_chance(world, player):
        return events + R.frame_events(world, occurrence, player, rival, key, rng)
    crisis = SC.crisis_of(occurrence)
    return events + P.made_events(world, "frame", key, player, crisis["faction"], occurrence.data["place"],
                                  target=rival, clues=[P.clue("planted", player, at="quarters_of", owner=rival)],
                                  extra={"occurrence": occurrence.id, "crime": "stole_art", "failed": True})


@effect("frame_paid")
def _frame_paid(world, event) -> None:
    _pay(world, event.actors[0], event.data["silver"])


def forge_block(world, player: int, occurrence) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] not in OPEN:
        return "The camps are made; a will now would fool no one."
    if (crisis.get("will") or {}).get("state") == "read":
        return "A will has been read; a second one would be laughed out of the hall."
    if silver_of(world, player) < FORGE_PRICE:
        return f"A scribe who will forge a master's hand costs {FORGE_PRICE} silver."
    return None


def forge_events(world, player: int, occurrence, names: int) -> list[Event]:
    return [Event("forgery_paid", (player,), occurrence.data["place"], {"silver": FORGE_PRICE})] + \
        R.forgery_events(world, occurrence, player, names, f"forgery:player:{occurrence.id}")


@effect("forgery_paid")
def _forgery_paid(world, event) -> None:
    _pay(world, event.actors[0], event.data["silver"])


# --- the spy's sway, and the NPCs who look into the player's plots -----------------------------------------

@listen("crisis_phase")
def _spies_and_suspicion(world, event, event_id: int) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    player = world.get_meta("player_id")
    rng = rng_for(world.world_seed, f"scheme:{occurrence.id}:{event.data['phase']}")
    camp = crisis.get("declared", {}).get(str(player))
    for spy in P.plots_of(world, crisis["faction"], ("spy",)):
        if spy.data["patron"] == player and camp is not None and event.data["phase"] in ("canvass",):
            voters = [v for v in C.voters(world, crisis["faction"]) if v != camp and not world.entity(v).data.get("is_player")]
            if voters:
                voter = rng.choice(voters)
                sways = {k: dict(v) for k, v in crisis.get("sways", {}).items()}
                sways.setdefault(str(voter), {})[str(camp)] = round(sways.get(str(voter), {}).get(str(camp), 0.0)
                                                                     + SPY_SWAY, 3)
                crisis = {**crisis, "sways": sways}
                world.update_data(occurrence.id, data=crisis)
    for plot in P.plots_of(world, crisis["faction"]):
        if plot.data["plotter"] != player or not [c for c in plot.data["clues"] if not c.get("lost")]:
            continue
        for c in SC.standing_claimants(world, SC.crisis_of(world.entity(occurrence.id))):
            if not world.entity(c["person"]).data.get("is_player") and rng.random() < NPC_FIND:
                commit(world, P.exposed_events(world, plot, c["person"], occurrence.data["place"]))
                break


# --- the player's plot exposed ----------------------------------------------------------------------------

@listen("plot_exposed")
def _player_exposed(world, event, event_id: int) -> None:
    plot = world.entity(event.data["plot"])
    plotter = plot.data["plotter"]
    if not world.entity(plotter).data.get("is_player") or plot.data.get("failed"):
        return
    commit(world, [Event("scheme_exposed", (plotter,), event.place, {"plot": plot.id, "deed": DEEDS[plot.data["type"]],
                                                                   "faction": plot.data["faction"]})])


@effect("scheme_exposed")
def _scheme_exposed(world, event) -> None:
    player, faction = event.actors[0], event.data["faction"]
    found = F.membership(world, player, faction)
    if found and found[1].get("status", "member") == "member":
        set_membership(world, player, faction, status="expelled")


@listen("scheme_exposed")
def _deed_told(world, event, event_id: int) -> None:
    player = event.actors[0]
    variant = make_variant(event.data["deed"], player, event.data["faction"], place=place_name(world, event.place))
    record_fact(world, player, event.data["deed"], event.data["faction"], place=event.place, source_event=event_id,
                weight=3.0, variant=variant)


_spy_year = P.SEASON_HOOKS["spy"]  # puppets' (imported above): a spy's year, and now the player's spy's report
P.SEASON_HOOKS["spy"] = lambda world, plot, n, rng: _spy_year(world, plot, n, rng) + _spy_reports(world, plot, n, rng)
