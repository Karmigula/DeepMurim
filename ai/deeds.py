"""What Claude's accepted proposals become (phase 6 spec 7.4, 14.5): ordinary events, each marked `ai: true`.

Nothing here decides whether a proposal may stand; `ai/validate.py` does, and builds these events. Their effects
are the engine's own: silver changes hands, an item changes owner, a person remembers, a deed is told, a belief is
passed on, someone new stands in the town, the body is hurt, time passes.
"""

from systems.beliefs import believe
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.founding import make_person
from systems.purse import silver_of
from systems.time import advance
from world.body import add_injury
from world.events import Event, Witness, effect, listen

KINDS = frozenset({"ai_paid", "ai_gave", "ai_felt", "ai_deed", "ai_told", "ai_arrived", "ai_hurt", "ai_waited",
                   "talked"})
TONES = ("kind", "cruel", "neutral", "bold")
DEED_WEIGHT = 1.0
# A told deed weighs little (spec 14.5): heaven counts it as a small kindness or cruelty (healing is 5), and the
# dao heart leans by it with the least weight. Bold and neutral deeds move neither.
DEED_KARMA = {"kind": ("merit", 3), "cruel": ("sin", 5)}
DEED_HEART = {"kind": (1, 1), "cruel": (-1, 1)}


def paid(player: int, npc: int, place: int, amount: int, proposal: dict) -> Event:
    return Event("ai_paid", (player, npc), place, {"amount": amount, "ai": True, "proposal": proposal})


def gave(player: int, npc: int, place: int, item: int, proposal: dict) -> Event:
    return Event("ai_gave", (player, npc), place, {"item": item, "ai": True, "proposal": proposal})


def felt(player: int, npc: int, place: int, feeling: str, strength: float, proposal: dict) -> Event:
    return Event("ai_felt", (player, npc), place, {"feeling": feeling, "strength": strength, "ai": True,
                                                    "proposal": proposal},
                 witnesses=(Witness(npc, feeling, strength),))


def deed(player: int, people: tuple, place: int, text: str, tone: str, proposal: dict) -> Event:
    return Event("ai_deed", (player, *people), place, {"text": text, "tone": tone, "ai": True, "proposal": proposal})


def told(npc: int, player: int, place: int, fact: int, proposal: dict) -> Event:
    return Event("ai_told", (npc, player), place, {"fact": fact, "ai": True, "proposal": proposal})


def arrived(player: int, place: int, path: str, occupation: str, traits: list, realm: str, proposal: dict) -> Event:
    return Event("ai_arrived", (player,), place, {"path": path, "occupation": occupation, "traits": list(traits),
                                                  "realm": realm, "ai": True, "proposal": proposal})


def hurt(player: int, place: int, location: str, kind: str, severity: int, proposal: dict) -> Event:
    return Event("ai_hurt", (player,), place, {"location": location, "kind": kind, "severity": severity, "ai": True,
                                               "proposal": proposal})


def talked(player: int, npc: int, place: int, summary: str, said: str) -> Event:
    """A line said in a conversation and its answer (spec 14.4): they remember it, as the summary tells it."""
    return Event("talked", (player, npc), place, {"summary": summary[:200], "said": said[:200], "ai": True},
                 witnesses=(Witness(npc, "engaged", 0.2),))


def waited(player: int, place: int, watches: int, proposal: dict) -> Event:
    return Event("ai_waited", (player,), place, {"watches": watches, "ai": True, "proposal": proposal})


@effect("ai_paid")
def _paid(world, event) -> None:
    player, npc = event.actors
    amount = event.data["amount"]
    world.update_data(player, silver=silver_of(world, player) - amount)
    world.update_data(npc, silver=silver_of(world, npc) + amount)


@effect("ai_gave")
def _gave(world, event) -> None:
    player, npc = event.actors
    world.unrelate(player, "owns", event.data["item"])
    world.relate(npc, event.data["item"], "owns")


@effect("ai_told")
def _told(world, event) -> None:
    npc, player = event.actors
    found = next(((b, f) for b, f in world.known_facts(npc) if f.id == event.data["fact"]), None)
    if found is not None:
        belief, _ = found
        believe(world, player, belief.fact_id, belief.variant, npc, belief.confidence * 0.9, belief.hops + 1, "told")


@effect("ai_arrived")
def _arrived(world, event) -> None:
    d = event.data
    make_person(world, d["path"], event.place, occupation=d["occupation"], traits=list(d["traits"]),
                realm=d["realm"], ai_made=True)
    world.update_data(event.place, ai_people=made_here(world, event.place) + 1,
                      ai_people_today=[world.time // 4, made_today(world, event.place) + 1])


def made_here(world, town: int) -> int:
    """How many people Claude has brought into this town."""
    return int(world.entity(town).data.get("ai_people", 0))


def made_today(world, town: int) -> int:
    """How many of them came today (a visit, plan ruling)."""
    mark = world.entity(town).data.get("ai_people_today") or [None, 0]
    return mark[1] if mark[0] == world.time // 4 else 0


@effect("ai_hurt")
def _hurt(world, event) -> None:
    d = event.data
    body = load_body(world, event.actors[0])
    add_injury(body, d["location"], d["kind"], d["severity"], world.time, "what you did")
    save_body(world, event.actors[0], body)


@effect("ai_waited")
def _waited(world, event) -> None:
    advance(world, event.data["watches"])


@effect("ai_felt")
def _felt_today(world, event) -> None:
    world.update_data(event.actors[1], ai_felt_day=world.time // 4)  # one feeling a person a day (6c review)


@effect("ai_deed")
def _deed_today(world, event) -> None:
    world.update_data(event.actors[0], ai_deed_day=world.time // 4)  # one deed a day (6c review)


@listen("ai_deed")
def _deed_weighed(world, event, event_id: int) -> None:
    """Heaven (5f) and the dao heart (5e) weigh a deed by its tone."""
    from systems import heart, karma
    tone = event.data["tone"]
    if tone in DEED_KARMA:
        side, amount = DEED_KARMA[tone]
        karma.add(world, event.actors[0], **{side: amount})
    if tone in DEED_HEART:
        heart.deed(world, event.actors[0], *DEED_HEART[tone])


@listen("ai_deed")
def _deed_told(world, event, event_id: int) -> None:
    """A deed is a tale like any other: it spreads, and is judged by its tone."""
    player, d = event.actors[0], event.data
    variant = {**make_variant(f"deed_{d['tone']}", player, None, place=place_name(world, event.place)),
               "text": d["text"]}
    record_fact(world, player, f"deed_{d['tone']}", None, place=event.place, source_event=event_id,
                weight=DEED_WEIGHT, variant=variant)
