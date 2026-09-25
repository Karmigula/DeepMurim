"""What the player is told about tournaments (phase 4e)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

KIND_NAMES = {"grand_assembly": "the Grand Martial Assembly", "dragon_phoenix": "the Dragon-Phoenix Meet",
              "sect_contest": "the sect contest", "lei_tai": "the lei tai"}
PLACES = {2: "second", 3: "among the last four"}


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
    won = d["winner"] == me
    other = world.entity(d["loser"] if won else d["winner"]).name
    return [f"You win the bout against {other}." if won else f"{other} wins the bout."], {}


@summary("match_resolved")
def _resolved_line(world, entry, names, place, other):
    d = entry.data
    me = world.get_meta("player_id")
    if d["how"] == "disqualified":
        return f"Was disqualified from a tournament in {place}."
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
