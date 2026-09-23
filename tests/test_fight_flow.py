import pytest

from app import App
from config import Config
from debug.replay import replay
from engine.commands import parse
from engine.game import Action, Game
from render.art import render_request
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def rival(game, traits=("proud", "loyal")):
    data = {"occupation": "wandering swordsman", "traits": list(traits), "realm": "mortal",
            "portrait": {"hair": 1, "face": 1, "robe": 1}}
    pid = game.world.add_entity("person", "Rival Kang", data, seed_path="test:rival")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def make_strong(game):
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years = 3, 20.0
    save_body(game.world, game.player.id, body)


def verbs(choices):
    return [c.action.verb for c in choices]


def challenge(game, npc):
    game.perform(Action("talk", npc))
    return game.perform(Action("challenge", npc))


def test_conversation_offers_a_challenge_and_later_a_spar(game):
    npc = rival(game)
    first = game.perform(Action("talk", npc))
    assert "challenge" in verbs(first.choices) and "spar" not in verbs(first.choices)
    game.perform(Action("farewell"))
    assert "spar" in verbs(game.perform(Action("talk", npc)).choices)


def test_a_challenge_starts_a_fight_with_its_own_screen(game):
    turn = challenge(game, rival(game))
    assert game.combat is not None and game.focus is None
    assert verbs(turn.choices) == ["intent"] * 4 + ["use_menu", "qi_output", "yield_duel", "flee"]
    assert turn.art["type"] == "duel" and "vs Rival Kang" in turn.status


def test_other_actions_are_refused_mid_fight(game):
    challenge(game, rival(game))
    time = game.world.time
    turn = game.perform(Action("meditate", 7))
    assert turn.lines[-1] == ("You are fighting Rival Kang. Finish the fight first.", "system")
    assert game.world.time == time and game.combat is not None
    assert game.perform(Action("verdict", "rob")).lines[-1][1] == "system"


def test_fighting_to_a_verdict_and_sparing(game):
    make_strong(game)
    challenge(game, rival(game, traits=("proud", "honest")))
    for _ in range(40):
        turn = game.perform(Action("intent", "strike"))
        if game.combat is None or game.combat.stage == "verdict":
            break
    assert game.combat.stage == "verdict"
    assert [c.action for c in turn.choices] == [Action("verdict", "spare"), Action("verdict", "rob"), Action("verdict", "cripple"), Action("verdict", "kill")]
    turn = game.perform(Action("verdict", "spare"))
    assert game.combat is None and any("You have beaten Rival Kang." == t for t, _ in turn.lines)


def test_technique_and_qi_output(game):
    challenge(game, rival(game))
    assert verbs(game.perform(Action("use_menu")).choices)[-1] == "back"
    game.perform(Action("use", "bare"))
    assert game.combat.technique is None
    game.perform(Action("qi_output"))
    assert game.combat.output == "full"


def test_yielding_ends_the_fight(game):
    challenge(game, rival(game))
    game.perform(Action("yield_duel"))
    assert game.combat is None


def test_a_fight_resumes_after_reload(tmp_path):
    path = tmp_path / "g.world"
    game = Game.new(path, "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    challenge(game, rival(game))
    game.perform(Action("intent", "guard"))
    if game.combat is None:
        pytest.skip("this seed ended the fight in one exchange")
    harm = dict(game.combat.harm)
    game.close()
    again = Game.load(path)
    assert again.combat is not None and again.combat.harm == harm
    assert again.perform(Action("intent", "probe")).lines
    again.close()


def test_duel_art_is_exact_size():
    art = render_request({"type": "duel", "parts": {"hair": 0, "face": 0, "robe": 0}, "beast": False,
                          "harm": 50.0, "condition": "hurt"}, 40, 18)
    assert len(art) == 18 and all(len(r) == 40 for r in art)
    assert any(cell and cell[0] == "#" for cell in art[-1])
    tiny = render_request({"type": "duel", "parts": None, "beast": True, "harm": 0.0, "condition": "fresh"}, 5, 1)
    assert len(tiny) == 1 and len(tiny[0]) == 5


def test_fight_words():
    for word, action in [("strike", Action("intent", "strike")), ("FLEE", Action("flee")),
                         ("yield", Action("yield_duel")), ("rob", Action("verdict", "rob")),
                         ("challenge", Action("challenge")), ("look", Action("look"))]:
        assert parse(word, []) == action


def test_a_fight_through_the_app_replays_exactly(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    target = next(c for c in app.choices + app.extra if c.action.verb == "talk")
    app.submit("talk " + target.label.split(" (")[0].removeprefix("Talk to "))
    app.submit("challenge")
    for word in ("strike", "guard", "probe", "strike", "feint", "yield"):
        app.submit(word)
    path = app.session.path
    app.shutdown()
    assert replay(path, tmp_path / "r").mismatches == []
