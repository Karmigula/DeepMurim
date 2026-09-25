"""The tournament pages (phase 4e spec 6): F11's list, the bracket as you know it, and the sheet's lines.

Built from what the player has seen (the board at the venue, a bracket they are in) and what they
believe (the heralds' news of the great tournaments, results they have heard), never from the truth
of a tournament nobody told them of.
"""

import systems.tournaments as T
import systems.world_events as W
from narrate.base import Line
from narrate.outcomes import cap
from narrate.tournament_text import event_name

STAGE_WORDS = {"foretold": "foretold by the heralds", "announced": "registration open",
               "active": "the bouts are on", "aftermath": "over", "over": "over"}
HOW_WORDS = {"sim": "wins", "bout": "wins", "bye": "goes through", "walkover": "wins by walkover",
             "forfeit": "wins by forfeit", "disqualified": "wins by disqualification"}


def _where(world, player: int) -> int | None:
    here = world.targets(player, "located_in")
    return here[0] if here else None


def seen(world, player: int, occurrence) -> bool:
    """Whether the player can read this tournament's board: at the venue, or named in its bracket."""
    t = occurrence.data["data"]
    return occurrence.data["place"] == _where(world, player) or t.get("presiding") == player \
        or player in t.get("registered", []) or player in t.get("entrants", [])


def known(world, player: int) -> list[int]:
    """The tournaments the player knows of: those seen, and those whose news has reached them."""
    rows = {row[W.ID] for row in W.index(world) if row[W.TYPE] in T.KINDS}
    found = {oid for oid in rows if seen(world, player, world.entity(oid))}
    for _, fact in world.known_facts_about([player], predicate="phenomenon"):
        if fact.data.get("occurrence") in rows:
            found.add(fact.data["occurrence"])
    return sorted(found)


def status(world, player: int, occurrence) -> str:
    t = occurrence.data["data"]
    if t.get("presiding") == player:
        return "you preside"
    if t.get("champion") == player:
        return "you are the champion"
    if player in t.get("disqualified", []):
        return "you were disqualified"
    if player not in t.get("registered", []) and player not in t.get("entrants", []):
        return "not entered"
    for r, matches in enumerate(t.get("rounds", [])):
        for m in matches:
            if player in (m["a"], m["b"]):
                if m["how"] is None:
                    return f"in round {r + 1}"
                if m["winner"] != player:
                    return f"out in round {r + 1}"
    return "entered"


def tournament_line(world, player: int, occurrence_id: int) -> str:
    occurrence = world.entity(occurrence_id)
    t = occurrence.data["data"]
    stage = W.stage_at(occurrence.data, world.time)
    words = STAGE_WORDS.get(stage, stage)
    if seen(world, player, occurrence):
        if stage == "active":
            words = f"day {T.day(occurrence, world.time)} of the bouts"
        if t.get("finished") and t.get("champion") is not None:
            words = f"over; {'you' if t['champion'] == player else world.entity(t['champion']).name} won"
    host = world.entity(occurrence.data["place"]).name
    return f"  {cap(event_name(world, t))} in {host}: {words}. {T.RULES.get(t['kind'], '')} " \
           f"You: {status(world, player, occurrence)}."


def tournaments_lines(world, player: int) -> list[Line]:
    lines: list[Line] = [("Tournaments", "heading")]
    found = known(world, player)
    if not found:
        return lines + [("  You know of no tournament. Heralds cry the great ones through the cities.", "dim")]
    return lines + [(tournament_line(world, player, oid), "dim") for oid in found]


def _name(world, player: int, person, blank: str) -> str:
    return blank if person is None else "you" if person == player else world.entity(person).name


def _match_line(world, player: int, m: dict, r: int, today: int) -> str:
    blank = "a bye" if r == 0 else "?"
    a, b = _name(world, player, m["a"], blank), _name(world, player, m["b"], blank)
    if m["how"] is None:
        return f"  {a} v {b}" + (": today" if m["day"] == today and None not in (m["a"], m["b"]) else "")
    if m["winner"] is None:
        return f"  {a} v {b}: {'void' if m['how'] == 'void' else 'no one goes through'}"
    verb = HOW_WORDS[m["how"]]
    if m["winner"] == player:
        verb = verb.replace("wins", "win").replace("goes", "go")
    return f"  {a} v {b}: {_name(world, player, m['winner'], blank)} {verb}"


def _next_bout(world, player: int, t: dict) -> str | None:
    for r, matches in enumerate(t["rounds"]):
        for m in matches:
            if m["how"] is None and player in (m["a"], m["b"]):
                other = m["b"] if m["a"] == player else m["a"]
                label = "the final" if r == len(t["rounds"]) - 1 else f"round {r + 1}"
                against = world.entity(other).name if other is not None else "whoever comes through"
                return f"Your next bout: {label} on day {m['day']}, against {against}."
    return None


def bracket_lines(world, player: int, occurrence_id: int) -> list[Line]:
    occurrence = world.entity(occurrence_id)
    t = occurrence.data["data"]
    host = world.entity(occurrence.data["place"]).name
    lines: list[Line] = [(f"{cap(event_name(world, t))} in {host}", "heading")]
    if not seen(world, player, occurrence):  # far from the board: only the results you have heard
        heard = [b.variant for b, f in world.known_facts_about([player], predicate="bested")
                 if b.variant.get("kind") == t["kind"] and b.variant.get("place") == host
                 and f.time >= occurrence.data["active"][0]]
        lines.append(("  You are not there to read the board.", "dim"))
        lines += [(f"  Heard: {_name(world, player, v.get('actor'), 'someone')} bested "
                   f"{_name(world, player, v.get('target'), 'someone')}.", "dim") for v in heard]
        return lines
    if t.get("compacted"):  # long over: only the podium is kept (plan ruling 5)
        podium = t["compacted"]
        lines.append((f"  Champion: {_name(world, player, t.get('champion'), 'no one')}.", "dim"))
        if podium["runner_up"] is not None:
            lines.append((f"  Runner-up: {_name(world, player, podium['runner_up'], 'no one')}.", "dim"))
        if podium["semis"]:
            lines.append((f"  The last four: {', '.join(_name(world, player, p, '?') for p in podium['semis'])}.", "dim"))
        return lines + [(f"  {podium['entrants']} fought.", "dim")]
    if not t["rounds"]:
        return lines + [("  The draw is made on the first day of the bouts.", "dim")]
    today = T.day(occurrence, world.time)
    for r, matches in enumerate(t["rounds"]):
        label = "The final" if r == len(t["rounds"]) - 1 else f"Round {r + 1}"
        lines.append((f"{label}, day {matches[0]['day']}:", "heading"))
        lines += [(_match_line(world, player, m, r, today), "dim") for m in matches]
    nxt = _next_bout(world, player, t)
    if nxt:
        lines.append((nxt, "default"))
    return lines


def posted_names(world, player: int) -> set[int]:
    """Everyone a board the player can read names: the brackets of tournaments they can see, the lei tai
    here, a raid's cultist. A posted bracket is public at the venue (the knowledge rule, check_people)."""
    found, here = set(), _where(world, player)
    for row in W.index(world):
        if row[W.TYPE] not in T.KINDS + ("lei_tai",):
            continue
        occurrence = world.entity(row[W.ID])
        t = occurrence.data["data"]
        if row[W.TYPE] == "lei_tai":
            if occurrence.data["place"] == here:
                found |= {p for p in [t.get("holder"), *t.get("challengers", [])] if p is not None}
        elif seen(world, player, occurrence):
            podium = t.get("compacted") or {}
            found |= set(t.get("entrants", [])) | set(t.get("registered", []))
            found |= {p for p in [t.get("champion"), (t.get("intrigue") or {}).get("cultist"),
                                  podium.get("runner_up"), *podium.get("semis", [])] if p is not None}
    return found


def open_bets(world, player: int) -> list[tuple[int, dict]]:
    found = []
    for row in W.index(world):
        if row[W.TYPE] in T.KINDS:
            found += [(row[W.ID], bet) for bet in world.entity(row[W.ID]).data["data"].get("bets", [])
                      if bet["player"] == player and not bet["settled"]]
    return found


def sheet_tournament_lines(world, player: int) -> list[Line]:
    """The character sheet's titles and open bets."""
    lines: list[Line] = [("", "default"), ("Titles:", "heading")]
    lines += [(f"  {title}", "default") for title in world.entity(player).data.get("titles", [])] or [("  none", "dim")]
    lines.append(("Open bets:", "heading"))
    lines += [(f"  {bet['stake']} silver on {world.entity(bet['on']).name} at {bet['odds']:.2f} to 1, round "
               f"{bet['round'] + 1} of {event_name(world, world.entity(oid).data['data'])}", "default")
              for oid, bet in open_bets(world, player)] or [("  none", "dim")]
    return lines
