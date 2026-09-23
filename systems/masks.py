"""Masks and the identities behind them (phase 3a spec 8).

While the player wears a mask the engine stamps data["as"] = persona on their
events. Witnesses remember the persona, facts name it, and only those who
recognise the wearer (an `is` fact they believe) connect it to the player.
"""

from systems.beliefs import knows_identity
from systems.duel import best_art
from systems.facts import make_variant, place_name, record_fact
from systems.purse import payment_events
from world.events import Event, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

MASK_PRICE = 5
ART_CHANCE = 0.5      # someone who knows your art sees it through the mask
VOICE_CHANCE = 0.3    # someone who has talked with you often knows your voice
CHANGE_CHANCE = 0.5   # someone who knows the face sees the mask go on or come off
COLOURS = ("Grey", "White", "Black", "Crimson", "Jade", "Bronze", "Silver")
STYLES = {"sword": "Swordsman", "fist": "Fist", "palm": "Palm", "saber": "Blade", "spear": "Spear"}
VOICE_KINDS = frozenset({"met", "conversed", "asked", "heard", "told", "no_news"})
TALK_KINDS = frozenset({"met", "conversed", "asked"})
UNSTAMPED = frozenset({"mask_on", "mask_off", "recognised"})


def masks_of(world, person_id: int) -> list:
    owned = (world.entity(item) for item in world.targets(person_id, "owns"))
    return [item for item in owned if item is not None and item.kind == "mask"]


def worn_persona(world, player_id: int) -> int | None:
    return world.entity(player_id).data.get("masked")


def buy_mask_events(player: int, seller: int, place: int) -> list[Event]:
    return payment_events(player, seller, place, MASK_PRICE, "mask") + [Event("mask_bought", (player, seller), place, {})]


@effect("mask_bought")
def _bought(world, event) -> None:
    mask = world.add_entity("mask", "plain mask", {"persona": None})
    world.relate(event.actors[0], mask, "owns")


def persona_for(world, player_id: int, mask_id: int) -> int:
    """The identity this mask gives its wearer: made on first wearing, the same ever after."""
    mask = world.entity(mask_id)
    if mask.data.get("persona"):
        return mask.data["persona"]
    rng = rng_for(world.world_seed, f"persona:{mask_id}")
    art = best_art(world, player_id)
    style = STYLES.get(art.form if art else None, "Stranger")
    with world.transaction():
        persona = world.add_entity("persona", f"the {rng.choice(COLOURS)}-Masked {style}",
                                   {"of": player_id, "mask": mask_id})
        world.update_data(mask_id, persona=persona)
    return persona


def wear_events(world, player: int, place: int, mask_id: int) -> list[Event]:
    return [Event("mask_on", (player,), place, {"mask": mask_id, "persona": persona_for(world, player, mask_id)})]


def remove_events(world, player: int, place: int) -> list[Event]:
    return [Event("mask_off", (player,), place, {"persona": worn_persona(world, player)})]


@effect("mask_on")
def _on(world, event) -> None:
    world.update_data(event.actors[0], masked=event.data["persona"])


@effect("mask_off")
def _off(world, event) -> None:
    world.update_data(event.actors[0], masked=None)


def onlookers(world, player: int, place: int, persona: int | None, putting_on: bool) -> list[int]:
    """People here who know the identity being hidden (or, taking it off, the mask being dropped)."""
    out = []
    for someone in people_at(world, place, exclude=player):
        memories = world.memories(someone.id, about=player)
        if putting_on:
            knows = any(not m.event.data.get("as") for m in memories)
        else:
            knows = any(m.event.data.get("as") == persona for m in memories)
        if knows and not knows_identity(world, someone.id, persona):
            out.append(someone.id)
    return out


def _technique(world, duel_id):
    entry = world.chronicle_entry(duel_id)
    return entry.data.get("technique") if entry is not None and entry.kind == "duel_started" else None


def _clue(world, player: int, witness: int, event) -> str | None:
    unmasked = [m for m in world.memories(witness, about=player) if not m.event.data.get("as")]
    if event.kind == "duel_ended":
        art = _technique(world, event.data.get("duel"))
        if art is not None and any(m.event.kind == "duel_ended" and _technique(world, m.event.data.get("duel")) == art
                                   for m in unmasked):
            return "art"
    if event.kind in VOICE_KINDS and sum(1 for m in unmasked if m.event.kind in TALK_KINDS) >= 3:
        return "voice"
    return None


def _recognised(player: int, witness: int, place, persona: int, how: str) -> Event:
    return Event("recognised", (player, witness), place, {"persona": persona, "how": how})


def recognition_events(world, player: int, ids: list[int], events: list) -> list[Event]:
    """Anyone who, at these just-committed moments, sees through the player's mask."""
    found = []
    for event_id, event in zip(ids, events):
        if event.kind in ("mask_on", "mask_off"):
            persona = event.data["persona"]
            for witness in onlookers(world, player, event.place, persona, event.kind == "mask_on"):
                if rng_for(world.world_seed, f"recognise:{event_id}:{witness}").random() < CHANGE_CHANCE:
                    found.append(_recognised(player, witness, event.place, persona, "changing"))
            continue
        persona = event.data.get("as")
        if not persona or not event.actors or event.actors[0] != player:
            continue
        for witness in sorted(set(world.witnesses_of(event_id)) | set(event.actors[1:2])):  # [2] is only talked about
            entity = world.entity(witness)
            if entity is None or entity.kind != "person" or entity.data.get("dead") or entity.data.get("beast") \
                    or knows_identity(world, witness, persona):
                continue
            chance = {"art": ART_CHANCE, "voice": VOICE_CHANCE}.get(_clue(world, player, witness, event), 0.0)
            if chance and rng_for(world.world_seed, f"recognise:{event_id}:{witness}").random() < chance:
                found.append(_recognised(player, witness, event.place, persona, _clue(world, player, witness, event)))
    return found


@listen("recognised")
def _identity_fact(world, event, event_id: int) -> None:
    player, _witness = event.actors
    persona = event.data["persona"]
    record_fact(world, persona, "is", player, place=event.place, source_event=event_id,
                variant=make_variant("is", persona, player, place=place_name(world, event.place)))
