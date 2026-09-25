"""What the player is told about tournaments (phase 4e)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

KIND_NAMES = {"grand_assembly": "the Grand Martial Assembly", "dragon_phoenix": "the Dragon-Phoenix Meet",
              "sect_contest": "the sect contest", "lei_tai": "the lei tai"}
PLACES = {2: "second", 3: "among the last four"}


def event_name(world, t: dict) -> str:
    """What people call this tournament: a sect's contest carries the sect's name."""
    if t["kind"] == "sect_contest" and t.get("faction") is not None:
        return f"the {world.entity(t['faction']).name}'s contest"
    return KIND_NAMES[t["kind"]]


def stage_line(world, occurrence, stage: str) -> str:
    """What the streets say when a tournament here reaches a new stage (heralds, the opening day)."""
    t = occurrence.data["data"]
    if t["kind"] == "lei_tai":
        holder = t.get("holder")
        return "A lei tai platform goes up in the square" + (f"; {world.entity(holder).name} holds it." if holder else ".")
    if stage == "announced":
        return f"Heralds cry {event_name(world, t)} through the streets: registration is open."
    return f"{cap(event_name(world, t))} opens today; the draw is posted in the square."


def _today(world, occurrence) -> str:
    import systems.tournaments as T
    t = occurrence.data["data"]
    if t.get("finished"):
        champion = t.get("champion")
        return f"{world.entity(champion).name} is champion." if champion is not None else "it ended without a champion."
    today = T.day(occurrence, world.time)
    for r, matches in enumerate(t["rounds"]):
        waiting = [m for m in matches if m["how"] is None]
        if not waiting:
            continue
        label = "the final" if r == len(t["rounds"]) - 1 else f"round {r + 1}"
        when = "today" if waiting[0]["day"] == today else f"on day {waiting[0]['day']}"
        fighters = [p for m in waiting for p in (m["a"], m["b"]) if p is not None]
        if not fighters:
            return f"{label} {when}."
        strength = T.strengths(world, occurrence.data["place"], fighters)  # the bookmaker's view, the town's belief
        favourite = max(fighters, key=lambda p: (strength[p], -p))
        return f"{label} {when}; the odds favour {world.entity(favourite).name}."
    return "the last bout is being fought."


def tournament_facts(world, town: int, player: int) -> list[str]:
    """The scene's tournament: registration, today's round and the favourite; a lei tai's holder (spec §6)."""
    import systems.tournaments as T
    import systems.world_events as W
    facts = []
    oid = T.here(world, town, T.KINDS, ("announced", "active"))
    if oid is not None:
        occurrence = world.entity(oid)
        name = cap(event_name(world, occurrence.data["data"]))
        if W.stage_at(occurrence.data, world.time) == "announced":
            days = max(1, (occurrence.data["active"][0] - world.time + 3) // 4)
            facts.append(f"{name}: registration is open; the bouts begin in {days} days.")
        else:
            facts.append(f"{name}: {_today(world, occurrence)}")
    platform = T.here(world, town, ("lei_tai",), ("active",))
    holder = world.entity(platform).data["data"].get("holder") if platform is not None else None
    if holder is not None:
        facts.append(f"A lei tai stands in the square; {world.entity(holder).name} holds it.")
    return facts


def _bested_story(world, variant, viewer) -> str:
    winner, loser = who(world, variant.get("actor"), viewer), who(world, variant.get("target"), viewer)
    event = KIND_NAMES.get(variant.get("kind"), "a tournament")
    return cap(f"{winner} bested {loser} at {event} in {variant.get('place') or 'a crowded city'}.")


def _won_story(world, variant, viewer) -> str:
    winner = who(world, variant.get("actor"), viewer)
    event = KIND_NAMES.get(variant.get("kind"), "a tournament")
    return cap(f"{winner} won {event} in {variant.get('place') or 'a crowded city'}.")


def _placed_story(world, variant, viewer) -> str:
    person = who(world, variant.get("actor"), viewer)
    event = KIND_NAMES.get(variant.get("kind"), "a tournament")
    return cap(f"{person} finished {PLACES.get(variant.get('place'), 'well')} at {event}.")


SPECIAL_PHRASES.update({"bested": _bested_story, "won_tournament": _won_story, "placed": _placed_story})



def _lei_tai_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} held the lei tai in {variant.get('place') or 'a market town'} "
               "until dusk and took the purse.")


SPECIAL_PHRASES["held_lei_tai"] = _lei_tai_story



def _disgraced_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} killed {who(world, variant.get('target'), viewer)} "
               f"on the platform in {variant.get('place') or 'a tournament'} and was thrown out in disgrace.")


SPECIAL_PHRASES["disgraced"] = _disgraced_story


@outcome("registered", body_facts=False)
def _registered(world, event):
    d = event.data
    kind = world.entity(d["occurrence"]).data["type"]
    if d["preside"]:
        return [f"You will preside over {KIND_NAMES[kind]}."], {}
    bond = f" You post a bond of {d['bond']} silver." if d["bond"] else ""
    return [f"You are entered in {KIND_NAMES[kind]}.{bond}"], {}


@summary("registered")
def _registered_line(world, entry, names, place, other):
    kind = world.entity(entry.data["occurrence"]).data["type"]
    return f"{'Presided over' if entry.data['preside'] else 'Entered'} {KIND_NAMES[kind]} in {place}."


@outcome("bond_refunded", body_facts=False)
def _refunded(world, event):
    return [f"Your bond of {event.data['silver']} silver is returned."], {}


@summary("bond_refunded")
def _refunded_line(world, entry, names, place, other):
    return f"Had a tournament bond of {entry.data['silver']} silver returned."


@outcome("match_resolved", body_facts=False)
def _resolved(world, event):
    d = event.data
    me = world.get_meta("player_id")
    if d["how"] == "forfeit":
        return ([f"You forfeit your bout."] if d["loser"] == me else [f"{world.entity(d['loser']).name} forfeits."]), {}
    if d["how"] == "disqualified":
        return ["The judges strike your name from the bracket."], {}
    if d["how"] == "void":
        return ["The final is declared void: no one is crowned."], {}
    won = d["winner"] == me
    other = world.entity(d["loser"] if won else d["winner"]).name
    return [f"You win the bout against {other}." if won else f"{other} wins the bout."], {}


@summary("match_resolved")
def _resolved_line(world, entry, names, place, other):
    d = entry.data
    me = world.get_meta("player_id")
    if d["how"] == "disqualified":
        return f"Was disqualified from a tournament in {place}."
    if d["how"] == "void":
        return f"Saw the final in {place} declared void."
    if d["winner"] == me:
        return f"Won a bout in round {d['round'] + 1} in {place}."
    return f"Lost a bout in round {d['round'] + 1} in {place}."


@outcome("tournament_won", body_facts=False)
def _won(world, event):
    return [f"You are crowned: {event.data['title']}. The prize is {event.data['prize']} silver."], {}


@summary("tournament_won")
def _won_line(world, entry, names, place, other):
    return f"Won the tournament in {place}: {entry.data['title']}."


@outcome("disqualified", body_facts=False)
def _dq(world, event):
    return [f"You have killed {world.entity(event.data['victim']).name} on the platform."], {}


@summary("disqualified")
def _dq_line(world, entry, names, place, other):
    return f"Killed an opponent in a bout in {place}, and was disgraced."


@outcome("lei_tai_challenged", body_facts=False)
def _lei_tai(world, event):
    holder = world.entity(event.actors[1]).name
    return [f"You take the platform from {holder}." if event.data["won"] else f"{holder} keeps the platform."], {}


@summary("lei_tai_challenged")
def _lei_tai_line(world, entry, names, place, other):
    return f"{'Took' if entry.data['won'] else 'Failed to take'} the lei tai in {place} from {other}."


@outcome("lei_tai_held", body_facts=False)
def _held(world, event):
    return [f"You hold the platform at dusk. The patron pays you {event.data['purse']} silver."], {}


@summary("lei_tai_held")
def _held_line(world, entry, names, place, other):
    return f"Held the lei tai in {place} and took the purse."



def _fixed_story(world, variant, viewer) -> str:
    if variant.get("how"):  # a fixed bout (spec §5.4), not a bet against oneself
        victim, rival = who(world, variant.get("actor"), viewer), who(world, variant.get("target"), viewer)
        done = "was poisoned before" if variant["how"] == "poisoned" else "was paid to lose"
        return cap(f"{victim} {done} the bout against {rival} at "
                   f"{KIND_NAMES.get(variant.get('kind'), 'a tournament')} in {variant.get('place') or 'a crowded city'}.")
    return cap(f"{who(world, variant.get('actor'), viewer)} bet against themselves in {variant.get('place') or 'a tournament'} "
               "and lost the bout. People are talking about a fix.")


SPECIAL_PHRASES["fixed"] = _fixed_story


@outcome("bet_placed", body_facts=False)
def _bet(world, event):
    d = event.data
    return [f"You stake {d['stake']} silver on {world.entity(d['on']).name} at {d['odds']:.2f} to 1."], {}


@summary("bet_placed")
def _bet_line(world, entry, names, place, other):
    return f"Bet {entry.data['stake']} silver on {world.entity(entry.data['on']).name} in {place}."


@outcome("bet_settled", body_facts=False)
def _settled(world, event):
    d = event.data
    if d["void"]:
        return [f"The bet is void; your {d['payout']} silver is returned."], {}
    return [f"Your bet pays {d['payout']} silver." if d["payout"] else "Your bet is lost."], {}


@summary("bet_settled")
def _settled_line(world, entry, names, place, other):
    d = entry.data
    return "Had a bet voided." if d["void"] else f"Won {d['payout']} silver on a bet." if d["payout"] else "Lost a bet."



@outcome("watched", body_facts=False)
def _watched(world, event):
    d = event.data
    a, b = (world.entity(p).name for p in event.actors[1:])
    winner = world.entity(d["winner"]).name
    lines = [f"You watch {a} and {b} fight; {winner} wins."]
    for person, word in d["tendencies"].items():
        lines.append(f"{world.entity(int(person)).name} {word}.")
    if d["fragments"]:
        lines.append("You commit something of their forms to memory.")
    return lines, {}


@summary("watched")
def _watched_line(world, entry, names, place, other):
    return f"Watched {names[1]} and {names[2]} fight in {place}."


@outcome("noticed", body_facts=False)
def _noticed(world, event):
    elder, d = world.entity(event.actors[0]).name, event.data
    faction = world.entity(d["faction"]).name
    if d["offer"] == "invite":
        return [f"{elder} of the {faction} finds you afterwards: the {faction} would take you in, no trial asked."], {}
    if d["offer"] == "gift":
        return [f"{elder} of the {faction} presses {d['silver']} silver into your hand: well fought."], {}
    return [f"{elder} of the {faction} takes {world.entity(event.actors[1]).name} in."], {}


@summary("noticed")
def _noticed_line(world, entry, names, place, other):
    return f"Was noticed by {names[0]} of the {world.entity(entry.data['faction']).name} in {place}."



def _raided_story(world, variant, viewer) -> str:
    return cap(f"Demonic cultists stormed {KIND_NAMES.get(variant.get('kind'), 'a tournament')} "
               f"in {variant.get('place') or 'a crowded city'} on the day of the final.")


def _vanished_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} vanished the night before a bout at "
               f"{KIND_NAMES.get(variant.get('kind'), 'a tournament')}, and no one knows where.")


def _defended_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} stood against the cultists who stormed "
               f"{KIND_NAMES.get(variant.get('kind'), 'a tournament')} in {variant.get('place') or 'a crowded city'}.")


def _exposed_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} exposed a fixed bout: "
               f"{who(world, variant.get('target'), viewer)} had been got at.")


SPECIAL_PHRASES.update({"raided": _raided_story, "vanished": _vanished_story, "defended": _defended_story,
                        "exposed_fix": _exposed_story})


@outcome("raided", body_facts=False)
def _raided(world, event):
    fallen = [world.entity(p).name for p in event.data["fallen"]]
    lines = ["Cultists in black storm the platform before the final. The crowd breaks and runs."]
    if fallen:
        lines.append(f"{' and '.join(fallen)} {'falls' if len(fallen) == 1 else 'fall'} in the fighting; the final is void.")
    else:
        lines.append("The judges put the final off until tomorrow.")
    return lines, {}


@summary("raided")
def _raided_line(world, entry, names, place, other):
    return f"Saw cultists storm the final in {place}."


@outcome("vanished", body_facts=False)
def _vanished(world, event):
    return [f"{world.entity(event.actors[0]).name} is nowhere to be found on the morning of their bout."], {}


@summary("vanished")
def _vanished_line(world, entry, names, place, other):
    return f"Heard that {names[0]} vanished before a bout in {place}."


@outcome("defended", body_facts=False)
def _defended(world, event):
    cultist = world.entity(event.actors[1]).name
    if event.data["won"]:
        return [f"You cut down {cultist}; the stands that saw it will remember."], {}
    return [f"{cultist} gets the better of you, and melts into the fleeing crowd."], {}


@summary("defended")
def _defended_line(world, entry, names, place, other):
    return f"Fought the cultists who stormed the final in {place}."


@outcome("asked_bookmaker", body_facts=False)
def _asked(world, event):
    d = event.data
    if d["learned"]:
        fact = world.fact(d["fact"])
        done = "poisoned" if fact.variant.get("how") == "poisoned" else "paid to lose"
        return [f"The bookmaker leans close: {world.entity(d['victim']).name} has been {done}. "
                "The odds on that bout are a lie."], {}
    return ["The bookmaker shrugs: nothing crooked that they know of."], {}


@summary("asked_bookmaker")
def _asked_line(world, entry, names, place, other):
    return f"Asked the bookmaker in {place} what they had heard."


@outcome("exposed", body_facts=False)
def _exposed(world, event):
    victim = world.entity(event.actors[1]).name
    return [f"You tell anyone who will listen that {victim}'s bout was fixed. By evening the whole town is saying it."], {}


@summary("exposed")
def _exposed_line(world, entry, names, place, other):
    return f"Exposed a fixed bout in {place}."



@outcome("contest_rewarded", body_facts=False)
def _contest_rewarded(world, event):
    faction = world.entity(event.data["faction"]).name
    if world.entity(event.actors[0]).data.get("is_player"):
        return [f"The {faction} marks your win: {event.data['merit']} merit, and a step up in rank."], {}
    return [f"{world.entity(event.actors[0]).name} is raised a rank in the {faction}."], {}


@summary("contest_rewarded")
def _contest_rewarded_line(world, entry, names, place, other):
    return f"Was rewarded by the {world.entity(entry.data['faction']).name} for winning its contest."


@summary("contest_summarized")
def _contest_summarized_line(world, entry, names, place, other):
    return f"Won the {world.entity(entry.data['faction']).name}'s contest in {place}."



@outcome("champion_honoured", body_facts=False)
def _champion_honoured(world, event):
    champion = world.entity(event.actors[1]).name
    if event.data["how"] == "reward":
        return [f"Before the sect you press {event.data['silver']} silver on {champion}, the contest's champion."], {}
    return [f"Before the sect you take {champion}, the contest's champion, as your own disciple."], {}


@summary("champion_honoured")
def _champion_honoured_line(world, entry, names, place, other):
    return f"{'Rewarded' if entry.data['how'] == 'reward' else 'Took as a disciple'} {other}, champion of the contest in {place}."
