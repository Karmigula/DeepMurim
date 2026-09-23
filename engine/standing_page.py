"""The standing page (F6, phase 3b spec 9): memberships, duties, how known factions see you, bounties."""

import systems.duties as duties
import systems.law as law
from narrate.base import Line
from systems import factions as F
from systems import halls
from systems.beliefs import apparent_to, known_people
from systems.standing import standing

WATCHES_PER_DAY = 4


def known_factions(world, player: int, town: int) -> list[int]:
    """Factions the player belongs to, has heard of, has met staff of, or sees a hall of here."""
    ids = [fid for fid, _, _ in F.memberships(world, player)]
    ids += halls.halls_here(world, town)
    for belief in world.beliefs(player):
        target = belief.variant.get("target")
        if isinstance(target, int) and (entity := world.entity(target)) is not None and entity.kind == "faction":
            ids.append(target)
    for other in world.acquaintances(player):
        ids += [fid for fid, _, data in F.memberships(world, other) if data.get("status", "member") == "member"]
    return list(dict.fromkeys(i for i in ids if world.entity(i) is not None and world.entity(i).kind == "faction"))


def _article(text: str) -> str:
    return ("an " if text[:1] in "aeiou" else "a ") + text


def faction_facts(world, player: int, other) -> list[str]:
    """Up to two short facts for a brief: the player's rank, and the other person's faction."""
    facts = []
    rows = [r for r in F.memberships(world, player) if r[2].get("status", "member") == "member"]
    rows.sort(key=lambda r: r[2].get("role") != "leader")  # your own sect first
    if rows:
        fid, rank, data = rows[0]
        if data.get("role") == "leader":
            count = len([p for p in F.members_of(world, fid) if p != player])
            facts.append(f"You lead the {world.entity(fid).name}, {count} disciples strong.")
        else:
            facts.append(f"You are {_article(F.title(world, fid, rank))} of the {world.entity(fid).name}.")
    if other is not None and not other.data.get("is_player"):
        town = next(iter(world.targets(other.id, "located_in")), None)
        tag = halls.faction_tag(world, other.id, town) if town else None
        if tag:
            facts.append(f"{other.name} is of the {tag}.")
    return facts[:2]


def standing_lines(world, player: int, town: int) -> list[Line]:
    lines: list[Line] = [("Your standing", "heading")]
    sect = world.entity(player).data.get("sect")
    if sect and not world.entity(sect).data.get("dissolved"):
        s = world.entity(sect)
        count = len([p for p in F.members_of(world, sect) if p != player])
        lines.append((f"Your sect: {s.name} at {world.entity(s.data['seat']).name}, {count} disciples, power {s.data['power']}.", "dim"))
    lines.append(("Your factions:", "heading"))
    mine = [(fid, rank, data) for fid, rank, data in F.memberships(world, player)]
    if not mine:
        lines.append(("  none", "dim"))
    for fid, rank, data in mine:
        name = world.entity(fid).name
        status = data.get("status", "member")
        if status != "member":
            lines.append((f"  {name}: {status}", "red"))
            continue
        sponsor = world.entity(data["sponsor"]).name if data.get("sponsor") else "none"
        secret = " (secret)" if data.get("secret") else ""
        lines.append((f"  {name}: {F.title(world, fid, rank)}, {data.get('merit', 0)} merit, sponsor {sponsor}{secret}", "dim"))
    duty = duties.open_duty(world, player)
    if duty is not None:
        days = max(0, (duty.data["deadline"] - world.time) // WATCHES_PER_DAY)
        lines.append((f"  Open duty: {duty.data['kind']} for the {world.entity(duty.data['faction']).name}, {days} days left", "dim"))
    trial = world.entity(player).data.get("trial")
    if trial:
        lines.append((f"  Trial: the {world.entity(trial['faction']).name} ({trial['kind']})", "dim"))
    lines += [("", "default"), ("How factions see you:", "heading")]
    for fid in known_factions(world, player, town):
        view = standing(world, fid, apparent_to(world, town, player))
        why = f" ({view.reasons[0]})" if view.reasons else ""
        lines.append((f"  {world.entity(fid).name}: {view.word}{why}", "dim"))
    lines += [("", "default"), ("Bounties:", "heading")]
    here = law.bounty(world, town, apparent_to(world, town, player))
    lines.append((f"  Here: {here} silver" if here else "  none here", "red" if here else "dim"))
    met = set(known_people(world, player))
    rivals = {f: r for f, r in (world.entity(player).data.get("rivals") or {}).items() if r in met}
    if rivals:
        lines += [("", "default"), ("Rivals:", "heading")]
        for fid, rival in rivals.items():
            lines.append((f"  {world.entity(rival).name} of the {world.entity(int(fid)).name}", "dim"))
    return lines
