from engine.commands import parse
from engine.game import Action, Choice

CHOICES = [
    Choice("Talk to Li Wei (innkeeper)", Action("talk", 1)),
    Choice("Talk to Li Mei (herbalist)", Action("talk", 2)),
    Choice("Talk to Lin Ho (monk)", Action("talk", 3)),
    Choice("Take the north road to Jade Town, the Misty Peaks (3 days)", Action("travel", (0, -1, 0))),
    Choice("Look around", Action("look")),
]


def test_empty_is_nothing():
    assert parse("", CHOICES) is None
    assert parse("   \t ", CHOICES) is None


def test_numbers():
    assert parse("4", CHOICES) == Action("travel", (0, -1, 0))
    assert parse("999", CHOICES).verb == "unknown"
    assert parse("0", CHOICES).verb == "unknown"


def test_global_words():
    assert parse("LOOK", CHOICES) == Action("look")
    assert parse("journal", CHOICES) == Action("journal")
    assert parse("bye", CHOICES) == Action("farewell")


def test_exact_word_beats_prefix():
    assert parse("talk to li wei", CHOICES) == Action("talk", 1)
    assert parse("talk monk", CHOICES) == Action("talk", 3)


def test_ambiguous_names():
    action = parse("talk li", CHOICES)
    assert action.verb == "ambiguous"
    assert {c.action.target for c in action.target} == {1, 2}


def test_travel_by_direction_and_prefix():
    assert parse("go north", CHOICES) == Action("travel", (0, -1, 0))
    assert parse("go jad", CHOICES) == Action("travel", (0, -1, 0))


def test_junk_never_crashes():
    for junk in ["говорить 🐉", "x" * 5000, "talk", "go ", "ask about", "!!!", "\x00\x01"]:
        action = parse(junk, CHOICES)
        assert action is None or action.verb in {"unknown", "ambiguous", "talk", "travel"}
