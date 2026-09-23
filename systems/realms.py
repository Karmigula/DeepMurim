"""The realm ladder (phase 2 spec §4): stages, bottlenecks, breakthrough conditions."""

from dataclasses import dataclass

from world.body import EXTRAORDINARY, Body


@dataclass(frozen=True)
class Realm:
    name: str
    threshold: float     # energy (years) at which this realm begins
    multiplier: float    # combat weight (phase 2b)
    label: str           # how data["realm"] spells it


REALMS = (
    Realm("Mortal", 0, 1, "mortal"),
    Realm("Third-rate", 1, 3, "third-rate"),
    Realm("Second-rate", 5, 6, "second-rate"),
    Realm("First-rate", 20, 12, "first-rate"),
    Realm("Peak", 40, 24, "peak"),
    Realm("Transcendent", 60, 48, "transcendent"),
    Realm("Profound", 120, 96, "profound"),
    Realm("Life-and-Death", 240, 192, "life-and-death"),
)
IMMORTAL_PATH = ("Foundation Establishment", "Core Formation", "Nascent Soul")  # locked in phase 2
MAX_REALM = len(REALMS) - 1
STAGES = ("early", "middle", "late", "peak")
LABEL_TO_INDEX = {r.label: i for i, r in enumerate(REALMS)}
NUMBER_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
EPS = 1e-9


def realm_index(label: str) -> int:
    return LABEL_TO_INDEX.get(label, 0)


def next_threshold(realm: int) -> float | None:
    return REALMS[realm + 1].threshold if realm < MAX_REALM else None


def stage_of(body: Body) -> str:
    low = REALMS[body.realm].threshold
    high = next_threshold(body.realm) or low * 2
    fraction = (body.energy_years - low) / (high - low) if high > low else 0.0
    return STAGES[max(0, min(3, int(fraction * 4)))]


def realm_title(body: Body) -> str:
    if body.realm == 0:
        return "Mortal"
    return f"{REALMS[body.realm].name} ({stage_of(body)} stage)"


def add_energy(body: Body, years: float) -> float:
    """Add energy up to the bottleneck; returns what was actually added."""
    high = next_threshold(body.realm)
    before = body.energy_years
    body.energy_years = before + years if high is None else min(high, before + years)
    body.bottleneck = high is not None and body.energy_years >= high - EPS
    return body.energy_years - before


def requirement(body: Body, arts) -> tuple[bool, str]:
    """Whether the condition for the next realm is met, and what it is, in words."""
    target = body.realm + 1
    flags = body.flags

    def is_open(name: str) -> bool:
        return body.meridians[name].state == "open"

    martial = [a for a in arts if a.category == "martial"]
    if target > MAX_REALM:
        return False, "The way beyond is not yet open to you."
    if target == 1:
        return "sensed_qi" in flags, "You must first sense the qi within you."
    if target == 2:
        return is_open("Governing") or is_open("Conception"), "Open the Governing or Conception meridian."
    if target == 3:
        met = is_open("Governing") and is_open("Conception") and any(a.mastery >= 0.67 for a in martial)
        return met, "Open the Governing and Conception meridians and bring a martial art to Major Success."
    if target == 4:
        met = any(a.mastery >= 1.0 for a in martial) and "life_and_death_insight" in flags
        return met, "Bring a martial art to Great Completion and survive a true life-or-death fight."
    if target == 5:
        met = all(is_open(m) for m in EXTRAORDINARY) and body.insight >= 200
        return met, "Open all eight extraordinary meridians and gather deep martial insight."
    if target == 6:
        return any(a.source == "created" and a.mastery >= 1.0 for a in arts), "Create your own art and bring it to Great Completion."
    return "returned_to_origin" in flags, "Return to the origin of your martial way."


def breakthrough_chance(body: Body, met: bool) -> float:
    chance = 0.35 + 0.05 * (body.physique["comprehension"] - 10) + 0.1 * body.purity + min(0.2, body.insight / 500)
    chance = max(0.05, min(0.95, chance))
    return round(chance if met else chance * 0.1, 3)


def energy_words(years: float) -> str:
    if years < 0.05:
        return "barely a trace of internal energy"
    if years < 1:
        return "less than a year of internal energy"
    n = int(years)
    count = NUMBER_WORDS[n - 1] if n <= len(NUMBER_WORDS) else str(n)
    return f"about {count} year{'s' if n != 1 else ''} of internal energy"
