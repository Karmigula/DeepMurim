"""The F4 character sheet: exact numbers, for players who want them.

Never shows hidden truth: an art's real completeness and an undiscovered
constitution stay hidden; only what the character believes is printed.
"""

from narrate.base import Line
from render.body_chart import SYMBOL
from systems.bodies import load_body
from systems.realms import realm_title
from systems.techniques import compat_words, compatibility, known_arts, mastery_stage
from world.body import EXTRAORDINARY, REGULAR, max_qi, unhealed
from world.db import World


def sheet_lines(world: World, player_id: int) -> list[Line]:
    player = world.entity(player_id)
    body = load_body(world, player_id)
    now = world.time
    lines: list[Line] = [
        (f"{player.name} - {player.data.get('origin_title', 'Wanderer')}", "heading"),
        (f"Realm: {realm_title(body)} | energy {body.energy_years:.2f} years"
         f"{' | BOTTLENECK' if body.bottleneck else ''}", "default"),
        (f"Qi {body.qi:.1f} / {max_qi(body):.1f} | purity {body.purity:.2f} | deviation {body.deviation:.1f}", "default"),
        ("Nature: " + "  ".join(f"{k} {v:.2f}" for k, v in body.nature.items()), "dim"),
        ("Physique: " + "  ".join(f"{k} {v}" for k, v in body.physique.items()), "default"),
        (f"Insight {body.insight:.1f} | silver {player.data.get('silver', 0)}", "default"),
        (f"Constitution: {body.constitution if body.constitution and body.constitution_known else 'unknown'}", "default"),
        ("", "default"),
        ("Arts:", "heading"),
    ]
    for art in known_arts(world, player_id):
        data = art.technique.data
        compat = compatibility(body, data)
        kind = "heart method" if art.category == "heart_method" else data["form"]
        lines.append((
            f"  {art.name} ({kind}, grade {data['grade']}): {mastery_stage(art.mastery)} {art.mastery:.2f}"
            f" | {compat_words(compat)} ({compat:.2f}) | completeness {art.known_completeness:.0%}", "default",
        ))
    lines += [("", "default"), ("Meridians:", "heading")]
    lines.append(("  " + "  ".join(f"{m} {SYMBOL[body.meridians[m].state]}{body.meridians[m].flow:.2f}" for m in REGULAR), "default"))
    extraordinary = []
    for m in EXTRAORDINARY:
        meridian = body.meridians[m]
        detail = f"{meridian.opening:.0%}" if meridian.state == "blocked" else f"{meridian.flow:.2f}"
        extraordinary.append(f"{m} {SYMBOL[meridian.state]}{detail}")
    lines.append(("  " + "  ".join(extraordinary), "default"))
    lines += [("", "default"), ("Injuries:", "heading")]
    injuries = unhealed(body, now)
    for injury in injuries:
        when = "permanent" if injury.permanent else f"{max(1, round((injury.heals_at - now) / 4))} days to heal"
        lines.append((f"  {injury.location}: {injury.kind} (severity {injury.severity}) - {when} - {injury.cause}",
                      "red" if injury.permanent else "default"))
    if not injuries:
        lines.append(("  none", "dim"))
    return lines
