"""The two jobs of typed text (phase 6 spec 14.3-14.4): a typed action, and a line said in a conversation.

Each prompt is built on the game's thread (the world's connection belongs to it) from the state pack (6a), the
prefetch (6b), the paragraphs just shown, and the typed line; the backend answers in a worker thread. The replies'
proposals are the vocabulary of `ai/validate.py`, checked there.
"""

from ai.bridge import Job
from ai.pack import build_pack
from ai.prefetch import build_prefetch
from ai.validate import FEELINGS, HURTS, MAX_DEED, MAX_SEVERITY, MAX_STRENGTH, MAX_WATCHES, PROPOSALS, REALMS
from world.body import BODY_PARTS
from world.gen.npc import OCCUPATIONS, TRAITS

MODEL = "claude-sonnet-5"  # the menu's "Typed actions and talk" model replaces it (6b's per-job models)
TIMEOUTS = {"Claude Code": 30.0, "OpenCode": 90.0}  # OpenCode's free tier took 13-60 s (spec 14.2)
DEFAULT_TIMEOUT = 30.0
MAX_CHOICES = 40
TALK_LINES = 8
MAX_SUMMARY = 200

INTENT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["prose", "proposals"], "properties": {
    "prose": {"type": "string", "maxLength": 1500}, "proposals": PROPOSALS}}
DIALOGUE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["reply", "summary", "proposals"],
                   "properties": {"reply": {"type": "string", "maxLength": 1500},
                                  "summary": {"type": "string", "maxLength": MAX_SUMMARY}, "proposals": PROPOSALS}}


def _one_of(values) -> str:
    return "|".join(values)


VOCABULARY = (
    "CHANGES you may propose (each an object with \"kind\" and its fields; at most 4):\n"
    "- action: choice (exactly one of the CHOICES below), when the typed action is one of them\n"
    "- pay: to (a person here, by name), amount (silver, a whole number, at most what you carry)\n"
    "- give: to (a person here), item (the exact name of something you own and neither wield nor wear)\n"
    f"- feeling: who (a person here), feeling ({_one_of(FEELINGS)}), strength (0.1 to {MAX_STRENGTH})\n"
    f"- deed: text (what you did, at most {MAX_DEED} characters, naming only people you know), "
    "tone (kind|cruel|neutral|bold): a tale that may spread, weighed by heaven and your heart; one a line\n"
    "- tell: who (a person here), handle (the [handle] of a belief they hold, from the prompt): you learn it\n"
    f"- minor_npc: occupation ({_one_of(OCCUPATIONS)}), traits (1-2 of {_one_of(TRAITS)}), "
    f"realm ({_one_of(REALMS)}): someone new in the town\n"
    f"- hurt: location ({_one_of(BODY_PARTS)}), injury ({_one_of(HURTS)}), severity (1 to {MAX_SEVERITY}): you only\n"
    f"- time: watches (1 to {MAX_WATCHES}; four watches are a day)\n"
)
RULES = (
    "Propose only what the typed action itself causes; most actions cause one change or none. Name only people the "
    "prompt names; state no number the prompt does not carry or you do not propose, written as digits. Stay "
    "realistic for the player's state: their realm, their silver, what they own, where they are, what they know. "
    "Use a tool only for what the prompt lacks."
)
INTENT_SYSTEM = (
    "You are the game master of DeepMurim, a wuxia text game. The player types what their character does; you "
    "decide what happens. Write one paragraph of about 3-6 sentences of vivid second-person prose in the register "
    "of a wuxia novel, then propose the changes to the world it causes. If the typed action is one of the CHOICES, "
    "propose that choice as an action and tell only its beginning: the engine tells the rest. " + RULES + "\n\n"
    + VOCABULARY + "\nReply with JSON: {\"prose\": \"...\", \"proposals\": [...]}."
)
DIALOGUE_SYSTEM = (
    "You voice a person of DeepMurim, a wuxia text game: the one under TALKING TO. The player speaks to them; "
    "answer as they would, from what they are, what they remember and what they hold, and from nothing else. Write "
    "one paragraph of about 2-5 sentences: their words, and what they do as they say them, in the third person. "
    "Then sum up the exchange in one line, as they would remember it (at most 200 characters), and propose only "
    "what the words themselves cause (most talk causes none, or a feeling; passing on a belief they hold is a "
    "tell). There is no action and no newcomer in a conversation. " + RULES + "\n\n" + VOCABULARY
    + "\nReply with JSON: {\"reply\": \"...\", \"summary\": \"...\", \"proposals\": [...]}."
)


def timeout_for(bridge) -> float:
    return TIMEOUTS.get(getattr(bridge, "name", ""), DEFAULT_TIMEOUT)


def intent_job(timeout: float = DEFAULT_TIMEOUT) -> Job:
    return Job("intent", MODEL, timeout, INTENT_SCHEMA, INTENT_SYSTEM, tools=True)


def dialogue_job(timeout: float = DEFAULT_TIMEOUT) -> Job:
    return Job("dialogue", MODEL, timeout, DIALOGUE_SCHEMA, DIALOGUE_SYSTEM, tools=True)


def _told(recent: list[str]) -> str:
    return "\n".join(f"- {line}" for line in recent[-3:]) or "- (the story begins)"


def intent_prompt(game, typed: str, choices: list, recent: list[str]) -> str:
    labels = list(dict.fromkeys(c.label for c in choices))[:MAX_CHOICES]
    shown = "\n".join(f"- {label}" for label in labels) or "- (none)"
    return (f"STATE:\n{build_pack(game)}\n\n{build_prefetch(game, typed)}\n\nTOLD JUST BEFORE:\n{_told(recent)}\n\n"
            f"CHOICES (an action names one exactly):\n{shown}\n\nTHE PLAYER TYPES: {typed}")


def dialogue_prompt(game, typed: str, person: int, talk: list[str], recent: list[str]) -> str:
    name = game.world.entity(person).name
    said = "\n".join(f"- {line}" for line in talk[-TALK_LINES:]) or "- (they have just begun to talk)"
    return (f"STATE:\n{build_pack(game)}\n\n{build_prefetch(game, typed, focus=person)}\n\nTALKING TO: {name}\n\n"
            f"THIS CONVERSATION SO FAR:\n{said}\n\nTOLD JUST BEFORE:\n{_told(recent)}\n\nTHE PLAYER SAYS: {typed}")
