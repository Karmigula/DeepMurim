"""What the player is told about secret realms (phase 4f)."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who


def _delved_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} went into {variant.get('realm_name') or 'a secret realm'} "
               f"and came out alive.")


def _took_story(world, variant, viewer) -> str:
    what = {"manual": "a martial manual", "pill": "a precious pill", "herb": "a spirit herb",
            "star_iron": "star iron"}.get(variant.get("prize"), "a treasure")
    return cap(f"{who(world, variant.get('actor'), viewer)} came out of {variant.get('realm_name') or 'a secret realm'} "
               f"with {what}.")


def _inherited_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} won the inheritance of {variant.get('master') or 'an ancient master'} "
               f"in {variant.get('realm_name') or 'a secret realm'}.")


def _sealed_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} did not come out of {variant.get('realm_name') or 'a secret realm'} "
               f"before the gate closed.")


SPECIAL_PHRASES.update({"delved": _delved_story, "took": _took_story, "inherited": _inherited_story,
                        "sealed": _sealed_story})



CHAMBERS = {
    "treasure": ("Something glints on an altar of black stone.", "An empty altar; someone was here before you."),
    "guardian": ("A {species} stands between you and the way on, and its eyes open.", "The {species} lies broken."),
    "trial": ("A trial chamber: {trial_words}", "The trial here has been passed."),
    "rivals": ("Voices ahead: others have come this way.", "Nobody bars the way now."),
    "stair": ("A stair goes down into the dark.", "A stair goes down into the dark."),
    "inheritance": ("A throne of jade, and on it the stillness of {master}.", "An empty throne of jade."),
}
TRIAL_WORDS = {"formation": "lines of an ancient array glow in the floor.",
               "pressure": "the qi here presses like deep water.",
               "mirror": "a bronze mirror as tall as a door."}


def chamber_line(world, realm, floor: int, c: int, room: dict) -> str:
    fresh, spent = CHAMBERS[room["kind"]]
    text = fresh if room["state"] == "untouched" else spent
    return text.format(species=room["contents"].get("species", "guardian"),
                       trial_words=TRIAL_WORDS.get(room["contents"].get("trial"), ""),
                       master=realm.data["master"]["name"])


def _trespassed_story(world, variant, viewer) -> str:
    return cap(f"{who(world, variant.get('actor'), viewer)} was caught slipping into "
               f"{variant.get('realm_name') or 'a secret realm'} past the sects' guards.")


SPECIAL_PHRASES["trespassed"] = _trespassed_story


@outcome("realm_entered", body_facts=False)
def _entered(world, event):
    realm = world.entity(event.data["realm"]).name
    how = {"token": "The jade token grows warm and crumbles as the gate lets you through.",
           "sponsor": "A sect's elder vouches for you, and the guards stand aside.",
           "sneak": "You slip past the guards while their eyes are elsewhere."}.get(event.data["how"], "")
    return [line for line in (how, f"You step through the gate into {realm}.") if line], {}


@summary("realm_entered")
def _entered_line(world, entry, names, place, other):
    return f"Entered {world.entity(entry.data['realm']).name} at {place}."


@outcome("sneak_caught", body_facts=False)
def _caught(world, event):
    return ["A sect guard catches your sleeve: \"Not without a place, friend.\" Word of it will spread."], {}


@summary("sneak_caught")
def _caught_line(world, entry, names, place, other):
    return f"Was caught slipping into {world.entity(entry.data['realm']).name}."


@outcome("delve_moved", body_facts=False)
def _moved(world, event):
    return [], {}


@outcome("realm_left", body_facts=False)
def _left(world, event):
    return [f"You come out of {world.entity(event.data['realm']).name} into daylight."], {}


@summary("realm_left")
def _left_line(world, entry, names, place, other):
    return f"Came out of {world.entity(entry.data['realm']).name} alive."


@outcome("chamber_looted", body_facts=False)
def _looted(world, event):
    prize = event.data["prize"]
    what = prize.get("name") or {"manual": "a martial manual", "star_iron": "a lump of star iron"}.get(prize["kind"], "a treasure")
    return [f"You take {what}."], {}


@summary("chamber_looted")
def _looted_line(world, entry, names, place, other):
    return f"Took a treasure in {world.entity(entry.data['realm']).name}."


@outcome("token_bought", body_facts=False)
def _bought(world, event):
    return [f"{world.entity(event.actors[1]).name} counts your {event.data['silver']} silver and hands over the jade token."], {}


@summary("token_bought")
def _bought_line(world, entry, names, place, other):
    return f"Bought a jade token from {other} in {place}."


@outcome("delve_rested", body_facts=False)
def _rested(world, event):
    return ["You sit against the cold wall and let your qi settle."], {}
