"""Briefs: the engine's pre-digested account of one moment.

All recall and relevance judgement happens here, in tested code. A narrator,
whether a grammar or a small model like Haiku, only has to phrase these facts.
Rules: no entity ids, only what the player knows, ranked facts, short.
"""

from dataclasses import dataclass, field

from systems.talk import conversations_with
from systems.time import WATCH_NAMES, format_date, format_season_year, season_of
from world.db import Entity, World
from world.gen.materialize import people_at, region_of
from world.gen.town import town_path

MAX_FACTS = 6
MAX_PROMPT = 1200
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")
NUMBER_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


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


def _place(world: World, place_id: int) -> PlaceBrief:
    town = world.entity(place_id)
    return PlaceBrief(
        town.name, town.data["kind"], region_of(world, town.id).name, town.data["terrain"],
        season_of(world.time), WATCH_NAMES[world.time % 4],
    )


def _toward(prior_conversations: int) -> str:
    if prior_conversations == 0:
        return "stranger"
    return "acquaintance" if prior_conversations < 5 else "familiar face"


def _person(entity: Entity, toward: str) -> PersonBrief:
    data = entity.data
    role = "you" if data.get("is_player") else data.get("occupation", "stranger")
    return PersonBrief(entity.name, role, tuple(data.get("traits", ())), data.get("realm", "mortal"), toward)


def _relationship(world: World, npc: Entity, player: Entity, include_current: bool) -> tuple[list[str], dict[str, str], int]:
    """Ranked facts about the player and this person, details, and the prior-conversation count.

    Salience order (spec §6.0): first meeting, then encounter count, then traits.
    Later phases insert indelible memories, grudges and obligations above these.
    `include_current` is True when the event being narrated is itself a conversation
    that has already been committed, so it must not count as "before".
    """
    history = conversations_with(world, npc.id, player.id)
    prior = max(0, len(history) - 1) if include_current else len(history)
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
    return facts, details, prior


def event_brief(world: World, event_id: int, event) -> Brief:
    player = world.entity(event.actors[0])
    other = world.entity(event.actors[1]) if len(event.actors) > 1 else None
    facts: list[str] = []
    details: dict[str, str] = {}
    other_brief = None
    if other is not None:
        facts, details, prior = _relationship(world, other, player, event.kind in ("met", "conversed"))
        other_brief = _person(other, _toward(prior))
        details["times_ordinal"] = ordinal(prior + 1)
    if "topic" in event.data:
        details["topic"] = str(event.data["topic"])
    place_id = event.place
    if event.kind == "travelled":
        dest = world.entity_by_seed(town_path(*event.data["to"]))
        details["dest"] = dest.name if dest else "a town"
        details["days"] = days_phrase(event.data["watches"])
        facts.insert(0, f"You travelled {details['days']} to reach {details['dest']}.")
        if dest is not None:
            place_id = dest.id
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
    )


def scene_brief(world: World, place_id: int, player_id: int, salt: str) -> Brief:
    player = world.entity(player_id)
    present = [p for p in people_at(world, place_id, exclude=player_id)]
    facts = []
    if present:
        facts.append("Here: " + ", ".join(f"{p.name} the {p.data.get('occupation', 'stranger')}" for p in present) + ".")
    known = [p.name for p in present if conversations_with(world, p.id, player_id)]
    if known:
        facts.append("You already know " + ", ".join(known) + ".")
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
