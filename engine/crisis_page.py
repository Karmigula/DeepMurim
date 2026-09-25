"""The Succession block (standing page, phase 4g spec 7), the sky page's crises, and the sheet's posts.

Built from what the player knows (spec 5): a camp's backers the player has met or heard of, undecided
voters only if the player has worked on them this crisis, the will and the token as far as they are shown.
"""

import systems.claimants as C
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_events as W
from narrate.base import Line
from narrate.crisis_text import claim_words
from narrate.gossip_text import rumour_text
from systems import factions as F
from systems.beliefs import known_people
from world.gen.materialize import people_at

WATCHES_PER_DAY = 4
PHASE_WORDS = {"mourning": "the mourning: claims are made", "canvass": "the canvass: the camps are made",
               "contest": "the contest", "strife": "force of arms", "settled": "settled"}


def _days(world, occurrence) -> int:
    ends = occurrence.data["ends"]
    stage = W.stage_at(occurrence.data, world.time)
    end = ends.get(stage, occurrence.data["over_at"])
    return max(0, (end - world.time + WATCHES_PER_DAY - 1) // WATCHES_PER_DAY)


def _will_words(world, crisis: dict, player: int) -> str:
    will = crisis.get("will") or {}
    state = will.get("state")
    if state == "read":
        return f"the will names {world.entity(will['names']).name}"
    if state == "held" and will.get("holder") == player:
        return "you hold the late master's will"
    if state == "burned":
        return "the will is ash"
    return "no will has been read"


def _named(world, person: int, player: int, known: set, fallback: str) -> str:
    """A name the player has heard of or sees; otherwise words that name no one (spec 5, 4g final review)."""
    if person == player:
        return "you"
    return world.entity(person).name if person in known else fallback


def _token_words(world, crisis: dict, player: int, known: set = frozenset()) -> str:
    token = crisis.get("token")
    holder = T.holder(world, token) if token is not None else None
    if holder == player:
        return "you hold the leader's token"
    if holder is not None and SC.claimant(crisis, holder) is not None:
        return f"{_named(world, holder, player, known, 'a claimant you have not met')} holds the leader's token"
    return "where the leader's token lies, you do not know"


def succession_lines(world, player: int) -> list[Line]:
    """For each faction of the player's in crisis: its stage, claimants, the camps as known, the will and the token."""
    lines: list[Line] = []
    heard = None
    for fid, _, data in F.memberships(world, player):
        occurrence = SC.live(world, fid) if data.get("status", "member") == "member" else None
        if occurrence is None:
            continue
        if heard is None:
            here = world.targets(player, "located_in")
            heard = set(known_people(world, player)) | {p.id for p in (people_at(world, here[0]) if here else [])}
        crisis = SC.crisis_of(occurrence)
        lines += [("", "default"), (f"Succession: the {world.entity(fid).name}", "heading"),
                  (f"  {PHASE_WORDS.get(crisis['phase'], crisis['phase'])}, {_days(world, occurrence)} days left",
                   "dim")]
        backing, undecided = C.camps(world, crisis)
        mine = crisis.get("declared", {}).get(str(player))
        for c in SC.standing_claimants(world, crisis):
            person = c["person"]
            proofs = [p for p in C.proofs(world, crisis, c)
                      if p != "token" or "holds" in _token_words(world, crisis, player, heard)]
            known = [world.entity(b).name for b in backing.get(person, []) if b != person and (b in heard or b == player)]
            name = _named(world, person, player, heard, "a claimant you have not met")
            tag = " (your camp)" if mine == person and person != player else ""
            lines.append((f"  {name}, {claim_words(c['kind'])}{tag}"
                          + (f"; proofs: {', '.join(proofs)}" if proofs else "")
                          + (f"; backed by {', '.join(known)}" if known else ""), "dim"))
        worked = {int(v) for v in crisis.get("swayed", {})}
        wavering = [world.entity(v).name for v in undecided if v in worked]
        if wavering:
            lines.append((f"  Undecided: {', '.join(wavering)}", "dim"))
        spent = sum(1 for stage in crisis.get("swayed", {}).values() if stage == crisis["phase"])
        lines.append((f"  You have worked on {spent} this stage. {_will_words(world, crisis, player).capitalize()}; "
                      f"{_token_words(world, crisis, player, heard)}.", "dim"))
        trial = crisis.get("trial") or {}
        if trial.get("pending"):
            a, b = trial["champions"][str(trial["a"])], trial["champions"][str(trial["b"])]
            lines.append((f"  A trial of arms waits: {_named(world, a, player, heard, 'an unknown champion')} against "
                          f"{_named(world, b, player, heard, 'an unknown champion')}.", "red"))
    return lines


def sky_crisis_lines(world, player: int) -> list[Line]:
    """The sky page's crises heard of, while they last: the heralds' cry, as the player heard it."""
    newest: dict = {}
    for belief, fact in world.known_facts(player):
        occurrence = fact.data.get("occurrence")
        if fact.predicate == "crisis" and occurrence is not None and world.entity(occurrence) is not None \
                and SC.crisis_of(world.entity(occurrence))["phase"] != "settled" \
                and (occurrence not in newest or fact.time >= newest[occurrence][1].time):
            newest[occurrence] = (belief, fact)
    if not newest:
        return []
    return [("Succession crises heard of:", "heading")] + [
        (f"  {rumour_text(world, belief.variant, player)}", "dim") for belief, fact in newest.values()]


def sheet_crisis_lines(world, player: int) -> list[Line]:
    """The sheet's posts a crisis made: chief disciple, leader of a seat won, retired master."""
    lines = []
    for fid, rank, data in F.memberships(world, player):
        if data.get("status", "member") != "member":
            continue
        faction = world.entity(fid)
        if faction.data.get("heir") == player:
            lines.append(f"Chief disciple of the {faction.name}")
        if data.get("role") == "leader" and faction.data.get("type") != "player_sect":
            lines.append(f"Leader of the {faction.name}")
        if data.get("role") == "retired":
            lines.append(f"Retired master of the {faction.name}")
    return [(text, "default") for text in lines]
