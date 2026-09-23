import pytest

from engine.game import Action, Game
from world.db import SaveError


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=42)
    yield g
    g.close()


def verbs(turn):
    return [c.action.verb for c in turn.choices]


def test_start_shows_opening_scene_and_choices(game):
    turn = game.start()
    assert any("Hero" in text for text, _ in turn.lines)  # the 'began' narration
    assert {"cultivate", "look", "journal"} <= set(verbs(turn))
    assert {"talk", "travel"} <= {c.action.verb for c in turn.all_choices}
    assert turn.art["type"] == "scene"
    assert "Hero" in turn.status and "Year 1" in turn.status


def test_talk_focuses_and_farewell_returns(game):
    talk = next(c for c in game.start().all_choices if c.action.verb == "talk")
    turn = game.perform(talk.action)
    assert turn.art["type"] == "portrait"
    assert {"ask", "farewell", "challenge"} <= set(verbs(turn)) <= {"ask", "farewell", "challenge", "spar", "learn_menu", "browse", "news", "tell_menu"}
    turn = game.perform(Action("ask", "work"))
    assert turn.lines
    turn = game.perform(Action("farewell"))
    assert turn.art["type"] == "scene"


def test_talk_to_someone_absent_commits_nothing(game):
    before = game.world.digest()
    turn = game.perform(Action("talk", 99999))
    assert turn.lines[-1][1] == "system"
    assert game.world.digest() == before


def test_travel_changes_place_and_time(game):
    start = game.place.id
    road = next(c for c in game.start().all_choices if c.action.verb == "travel" and "north" in c.label)
    turn = game.perform(road.action)
    assert game.place.id != start
    assert "Year 1, Spring day 4" in turn.status
    assert any(c.action.verb == "talk" for c in turn.all_choices)  # new town was populated


def test_journal_lists_history(game):
    talk = next(c for c in game.start().all_choices if c.action.verb == "talk")
    game.perform(talk.action)
    lines = [text for text, _ in game.perform(Action("journal")).lines]
    assert any("set out from" in line for line in lines)
    assert any("Met " in line for line in lines)


def test_unknown_and_ambiguous(game):
    assert game.perform(Action("unknown", "dance")).lines[-1][1] == "system"
    options = tuple(game.start().choices[:2])
    turn = game.perform(Action("ambiguous", options))
    assert turn.choices == list(options)


def test_load_missing_raises(tmp_path):
    with pytest.raises(SaveError):
        Game.load(tmp_path / "none.world")


def test_damaged_saves_raise_save_error(tmp_path):
    for damage in ("dangling_player", "nowhere", "bytes"):
        path = tmp_path / f"{damage}.world"
        g = Game.new(path, "Hero", world_seed=42)
        pid = g.world.get_meta("player_id")
        if damage == "dangling_player":
            g.world.set_meta("player_id", 99999)
        elif damage == "nowhere":
            g.world.unrelate(pid, "located_in")
        g.close()
        if damage == "bytes":
            data = bytearray(path.read_bytes())
            for offset in range(4096 * 2, len(data) - 4096, 7):
                data[offset] = 0xAB
            path.write_bytes(bytes(data))
        with pytest.raises(SaveError):
            Game.load(path).start()


def test_busy_town_keeps_every_way_out_reachable(tmp_path):
    g = Game.new(tmp_path / "busy.world", "Hero", world_seed=7)
    turn = g.start()
    assert len(turn.choices) <= 9
    verbs = [c.action.verb for c in turn.choices]
    assert {"look", "journal"} <= set(verbs)
    assert sum("road" in c.label for c in turn.all_choices) == 4
    people = [c for c in turn.all_choices if c.action.verb == "talk"]
    assert len(people) == g.world.entity(g.place.id).data["npc_count"]
    if "people" in verbs:
        sub = g.perform(next(c.action for c in turn.choices if c.action.verb == "people"))
        assert [c.action for c in sub.choices if c.action.verb == "talk"] == [c.action for c in people]
        assert sub.choices[-1].action.verb == "back" and len(sub.choices) <= 9
        assert "road" in " ".join(c.label for c in g.perform(sub.choices[-1].action).all_choices)
    g.close()
