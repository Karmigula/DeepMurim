"""Briefs: the engine's pre-digested account of one moment.

All recall and relevance judgement happens here, in tested code. A narrator,
whether a grammar or a small model like Haiku, only has to phrase these facts.
Rules: no entity ids, only what the player knows, ranked facts, short.
`outcome` is what the player must be told happened; `facts` is context.
"""

from dataclasses import dataclass, field

from narrate.outcomes import BODY_FACT_KINDS, OUTCOME_BUILDERS
from systems.attitude import attitude
from systems.beliefs import apparent_to, knows_identity
from systems.bodies import load_body
from systems.reputation import reputation
from systems.realms import REALMS, energy_words, realm_title, stage_of
from systems.talk import conversations_with, times_asked
from systems.techniques import compat_words
from systems.time import WATCH_NAMES, days_word, format_date, format_season_year, season_of
from world.body import body_of, unhealed
from world.db import Entity, World
from world.gen.materialize import people_at, region_of
from world.gen.town import town_path

MAX_FACTS = 6
MAX_OUTCOME = 4
MAX_PROMPT = 1200
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")
NUMBER_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
BODY_KINDS = frozenset({
    "began", "body_awakened", "cultivated", "practised", "opening_meridian", "rested", "breakthrough", "deviation",
})
INJURY_WORDS = {"bruise": "bruised", "cut": "cut", "fracture": "fractured", "internal": "hurt inside", "meridian": "damaged"}


@dataclass(frozen=True)
class PlaceBrief:
    name: str
    kind: str
    region: str
    terrain: str
    season: str
    watch: str


@dataclass(frozen=True)
class PersonBrief:
    name: str
    role: str
    traits: tuple[str, ...]
    realm: str
    toward_player: str


@dataclass(frozen=True)
class Brief:
    kind: str
    when: str
    place: PlaceBrief
    player: PersonBrief
    other: PersonBrief | None
    details: dict[str, str] = field(default_factory=dict)
    facts: tuple[str, ...] = ()
    seed: int = 0   # deterministic procedural text only; never shown to a model
    salt: str = ""
    outcome: tuple[str, ...] = ()

    def to_prompt(self) -> str:
        p = self.place
        lines = [
            f"EVENT: {self.kind}",
            f"WHEN: {self.when}",
            f"WHERE: {p.name} ({p.kind}) in {p.region}; {p.terrain}; {p.season}; {p.watch}",
            f"YOU: {self.player.name}, {self.player.realm}",
        ]
        if self.other is not None:
            o = self.other
            traits = ", ".join(o.traits) or "unremarkable"
            lines.append(f"THEM: {o.name}, {o.role}; {traits}; {o.realm}; to you: {o.toward_player}")
        if self.details:
            lines.append("DETAILS: " + "; ".join(f"{k}={v}" for k, v in sorted(self.details.items())))
        if self.outcome:
            lines.append("OUTCOME:")
            lines += [f"- {line}" for line in self.outcome[:MAX_OUTCOME]]
        lines.append("FACTS:")
        lines += [f"- {fact}" for fact in self.facts[:MAX_FACTS]]
        return "\n".join(lines)[:MAX_PROMPT]


def ordinal(n: int) -> str:
    return ORDINALS[n - 1] if 1 <= n <= len(ORDINALS) else f"{n}th"


def days_phrase(watches: int) -> str:
    days = max(1, watches // 4)
    if days == 1:
        return "a day"
    return f"{NUMBER_WORDS[days - 1] if days <= len(NUMBER_WORDS) else days} days"


def growth_words(gained: float) -> str:
    if gained < 0.02:
        return "by a trickle"
    if gained < 0.1:
        return "a little"
    if gained < 0.5:
        return "noticeably"
    return "greatly"


def progress_words(progress: float) -> str:
    if progress < 0.25:
        return "it barely stirs"
    if progress < 0.5:
        return "a thread of qi passes through"
    if progress < 0.75:
        return "it is half open"
    return "it is nearly open"


def _place(world: World, place_id: int) -> PlaceBrief:
    place = world.entity(place_id)
    town = world.entity(place.data["gate"]) if place.kind == "secret_realm" else place  # inside: the gate's land (4f)
    return PlaceBrief(
        place.name, town.data["kind"], region_of(world, town.id).name, town.data["terrain"],
        season_of(world.time), WATCH_NAMES[world.time % 4],
    )


def _toward(prior_conversations: int) -> str:
    if prior_conversations == 0:
        return "stranger"
    return "acquaintance" if prior_conversations < 5 else "familiar face"


def _person(entity: Entity, toward: str) -> PersonBrief:
    data = entity.data
    if data.get("is_player"):
        body = body_of(entity)
        realm, role = (realm_title(body) if body else data.get("realm", "mortal")), "you"
    else:
        realm, role = data.get("realm", "mortal"), data.get("occupation", "stranger")
    return PersonBrief(entity.name, role, tuple(data.get("traits", ())), realm, toward)


def _as_seen(world: World, npc: Entity, player: Entity, memories: list) -> list:
    """The memories this person connects to the player: while masked and unrecognised, only the mask's own."""
    persona = player.data.get("masked")
    if persona and not knows_identity(world, npc.id, persona):
        return [m for m in memories if m.event.data.get("as") == persona]
    return memories


def _relationship(world: World, npc: Entity, player: Entity) -> tuple[list[str], dict[str, str], int]:
    """Ranked facts about the player and this person, details, and the prior-conversation count.

    Salience order (spec §6.0): first meeting, then encounter count, then traits.
    Later phases insert indelible memories, grudges and obligations above these.
    Every event with another person happens inside a conversation whose opening
    greeting is already committed, so that greeting never counts as "before".
    """
    history = _as_seen(world, npc, player, conversations_with(world, npc.id, player.id))
    prior = max(0, len(history) - 1)
    facts: list[str] = []
    details: dict[str, str] = {}
    met = [m for m in history if m.event.kind == "met"]
    if met and prior:
        season = format_season_year(met[0].event.time)
        details["first_met_season"] = season
        facts.append(f"You first met {npc.name} in {season}.")
    if prior:
        facts.append(f"You have spoken with {npc.name} {prior} time{'s' if prior != 1 else ''} before.")
    traits = npc.data.get("traits")
    if traits:
        facts.append(f"{npc.name} is {' and '.join(traits)}.")
    _patience_facts(world, npc, player, history, facts, details)
    feeling = attitude(world, npc.id, apparent_to(world, npc.id, player.id))
    if feeling.reason and feeling.word != "neutral":
        details["attitude"] = feeling.word
        facts.insert(0, f"{npc.name} is {feeling.word} toward you: {feeling.reason}.")
    return facts, details, prior


def _patience_facts(world, npc, player, greetings, facts, details) -> None:
    """Did this person lose patience with the player in the previous conversation, or ever?"""
    if not greetings:
        return
    current_start = greetings[-1].event.id
    previous_start = greetings[-2].event.id if len(greetings) > 1 else None
    lost = [
        m.event.id for m in _as_seen(world, npc, player, world.memories(npc.id, about=player.id))
        if m.event.kind == "lost_patience" and m.event.id < current_start
    ]
    if not lost:
        return
    if previous_start is not None and lost[-1] > previous_start:
        details["annoyed_last_time"] = "yes"
        facts.insert(0, f"Last time, {npc.name} lost patience with your repeated questions.")
    else:
        facts.append(f"{npc.name} once lost patience with your repeated questions.")


def player_facts(world: World, player_id: int) -> list[str]:
    """What the player's own body says about them right now, most salient first."""
    if "body" not in world.entity(player_id).data:
        return []
    body = load_body(world, player_id)
    now = world.time
    facts = [f"Your {i.location} never healed from {i.cause}." for i in body.injuries if i.permanent]
    permanent_at = {i.location for i in body.injuries if i.permanent}
    facts += [f"Your {n} meridian is severed." for n, m in body.meridians.items() if m.state == "severed" and n not in permanent_at]
    facts += [f"Your {n} meridian is scarred." for n, m in body.meridians.items() if m.state == "scarred"]
    for injury in unhealed(body, now):
        if not injury.permanent:
            days = max(1, round((injury.heals_at - now) / 4))
            facts.append(f"Your {injury.location} is {INJURY_WORDS[injury.kind]} ({days} days to heal).")
    if body.deviation > 60:
        facts.append("Your qi feels unruly; a deviation may be near.")
    if body.constitution and body.constitution_known:
        facts.append(f"You have a {body.constitution}.")
    who = "You are still a mortal" if body.realm == 0 else f"You are a {REALMS[body.realm].name} warrior at the {stage_of(body)} stage"
    return facts[: MAX_FACTS - 1] + [f"{who}, with {energy_words(body.energy_years)}."]


def _body_outcome(event) -> tuple[list[str], dict[str, str]]:
    d, kind = event.data, event.kind
    out: list[str] = []
    details: dict[str, str] = {}
    if kind in ("began", "body_awakened"):
        details["origin"] = d.get("origin", "Wanderer")
        out.append(f"You begin as a {details['origin']}." if kind == "began" else "You take stock of your body and your training.")
        if d.get("arts"):
            out.append("You know the " + " and the ".join(d["arts"]) + ".")
    elif kind == "cultivated":
        details["days"] = days_word(d["days"])
        method = f" using the {d['method']}" if d.get("method") else ""
        out.append(f"You meditated for {details['days']}{method}.")
        if d["sensed_qi"]:
            out.append("For the first time, you sensed the qi within you.")
        out.append(f"Your internal energy grew {growth_words(d['energy_gained'])}." if d["energy_gained"] > 1e-9
                   else "Your internal energy did not grow.")
        if d["reached_bottleneck"]:
            out.append("Your qi has reached a bottleneck; it will not grow until you break through.")
        elif d["stage_after"] != d["stage_before"]:
            out.append(f"You advanced to the {d['stage_after']} stage.")
    elif kind == "practised":
        details.update(technique=d["technique"], days=days_word(d["days"]))
        out.append(f"You practised the {d['technique']} for {details['days']}.")
        if d["stage_after"] != d["stage_before"]:
            out.append(f"Your {d['technique']} reached {d['stage_after']}.")
        if d.get("mastered"):
            out.append(f"You have taken all the {d['technique']} can teach; practice now only keeps it sharp.")
        elif d["stalled"]:
            out.append(f"Your progress in the {d['technique']} has stalled; something in it feels wrong.")
        elif d["compat"] < 0.7:
            out.append(f"The {d['technique']} {compat_words(d['compat'])}.")
    elif kind == "opening_meridian":
        details.update(meridian=d["meridian"], days=days_word(d["days"]))
        if d["opened"]:
            out.append(f"Your {d['meridian']} meridian is now open!")
        else:
            out.append(f"You worked at your {d['meridian']} meridian; {progress_words(d['progress_after'])}.")
        if d["forced"] and d["forced_damage"]:
            out.append(f"You forced the flow and damaged your {d['forced_damage']} meridian.")
    elif kind == "rested":
        details["days"] = days_word(d["days"])
        out.append(f"You rested for {details['days']}.")
        out += [f"Your {location} has healed." for location in d["healed"][:2]]
    elif kind == "breakthrough":
        details.update(target=d["target"], success="yes" if d["success"] else "no")
        if d["success"]:
            out.append(f"You broke through to {d['target']}!")
        else:
            out.append(f"Your breakthrough to {d['target']} failed.")
            if not d["met"]:
                out.append(f"You were not ready: {d['requirement']}")
            out += [f"The backlash damaged your {m} meridian." for m in d["damaged"][:2]]
    elif kind == "deviation":
        details["cause"] = d["cause"]
        out.append(f"Your qi deviated: {d['cause']}.")
        if d.get("reveal"):
            out.append("You realise the manual was never complete.")
        for name, _before, after in d.get("changes", [])[:2]:
            out.append(f"Your {name} meridian is scarred for good." if after == "scarred" else f"It damaged your {name} meridian.")
        if d.get("energy_lost", 0) > 1e-9:
            out.append("You lost some of your internal energy.")
    if d.get("discovered"):
        out.insert(1, f"You discover that you have a {d['discovered']}.")
    return out, details


def event_brief(world: World, event_id: int, event) -> Brief:
    player = world.entity(event.actors[0])
    other = world.entity(event.actors[1]) if len(event.actors) > 1 else None
    facts: list[str] = []
    details: dict[str, str] = {}
    outcome: list[str] = []
    other_brief = None
    if other is not None:
        facts, details, prior = _relationship(world, other, player)
        other_brief = _person(other, _toward(prior))
        details["times_ordinal"] = ordinal(prior + 1)
    if "topic" in event.data:
        details["topic"] = str(event.data["topic"])
        if event.kind == "asked" and other is not None:
            repeats = times_asked(world, other.id, player.id, details["topic"]) - 1  # this question is committed
            if repeats > 0:
                details["asked_before"] = str(repeats)
                topic = details["topic"]
                about = {"work": "their work", "news": "the news"}.get(topic) \
                    or (topic[len("about "):] if topic.startswith("about ") else world.entity(event.place).name)
                plural = "s" if repeats != 1 else ""
                facts.insert(0, f"You have already asked {other.name} about {about} {repeats} time{plural} before.")
    place_id = event.place
    if event.kind == "travelled":
        dest = world.entity_by_seed(town_path(*event.data["to"]))
        details["dest"] = dest.name if dest else "a town"
        details["days"] = days_phrase(event.data["watches"])
        facts.insert(0, f"You travelled {details['days']} to reach {details['dest']}.")
        if dest is not None:
            place_id = dest.id
    if event.kind in BODY_KINDS:
        outcome, extra = _body_outcome(event)
        details.update(extra)
        facts = player_facts(world, player.id)
    from engine.standing_page import faction_facts  # the page owns the wording (phase 3b)
    facts = facts + [f for f in faction_facts(world, player.id, other) if f not in facts]
    if other is not None and not other.data.get("is_player"):
        from narrate.world_text import life_facts  # age and family (phase 4a)
        from narrate.lineage_text import relation_fact  # and how they stand to you (phase 4b)
        related = relation_fact(world, player.id, other)
        facts = ([related] if related else []) + facts + [f for f in life_facts(world, other) if f not in facts]
    if event.kind in OUTCOME_BUILDERS:
        more, extra = OUTCOME_BUILDERS[event.kind](world, event)
        outcome = list(outcome) + list(more)
        details.update(extra)
        if event.kind in BODY_FACT_KINDS:
            facts = player_facts(world, player.id)[:3] + facts
    return Brief(
        kind=event.kind,
        when=format_date(world.time),
        place=_place(world, place_id),
        player=_person(player, "self"),
        other=other_brief,
        details=details,
        facts=tuple(facts[:MAX_FACTS]),
        seed=world.world_seed,
        salt=f"event:{event_id}",
        outcome=tuple(outcome[:MAX_OUTCOME]),
    )


def scene_brief(world: World, place_id: int, player_id: int, salt: str) -> Brief:
    player = world.entity(player_id)
    present = people_at(world, place_id, exclude=player_id)
    facts = []
    if present:
        facts.append("Here: " + ", ".join(f"{p.name} the {p.data.get('occupation', 'stranger')}" for p in present) + ".")
    known = [p.name for p in present if conversations_with(world, p.id, player_id)]
    if known:
        facts.append("You already know " + ", ".join(known) + ".")
    from narrate.world_text import town_news  # the newest change here the player believes (phase 4a)
    news = town_news(world, place_id, player_id)
    from systems.market import town_line  # what is cheap and dear here (phase 4c)
    trade = town_line(world, place_id)
    if trade:
        facts.append(trade)
    from narrate.sky_text import sky_facts  # the sky over this place (phase 4d)
    facts += sky_facts(world, place_id)
    from narrate.tournament_text import tournament_facts  # a tournament here (phase 4e)
    facts += tournament_facts(world, place_id, player_id)
    from narrate.realm_text import realm_facts  # a secret realm's gate here (phase 4f)
    facts += realm_facts(world, place_id, player_id)
    ancestors = player.data.get("ancestors") or []
    if ancestors:
        facts.append(f"You are the heir of {world.entity(ancestors[-1]).name}.")
    if news:
        facts.append(f"Lately here: {news}")
    fame = reputation(world, place_id, apparent_to(world, place_id, player_id))
    if fame.epithet:
        facts.append(f"People here know you as the {fame.epithet}.")
    elif fame.renown > 0:
        facts.append(f"People here have heard of you; you are {fame.word} here.")
    return Brief(
        kind="scene",
        when=format_date(world.time),
        place=_place(world, place_id),
        player=_person(player, "self"),
        other=None,
        facts=tuple(facts[:MAX_FACTS]),
        seed=world.world_seed,
        salt=f"scene:{place_id}:{world.time}:{salt}",
    )
