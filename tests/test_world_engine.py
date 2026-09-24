import time

import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.world_clock as clock
from engine.actions import Action
from engine.game import Game
from systems import founding, travel
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import people_at
from world.gen.town import town_path


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)


def texts(turn):
    return [t for t, _ in turn.lines]


def local(game, path, **data):
    pid = founding.make_person(game.world, path, game.place.id, **data)
    lives.lived_to(game.world, pid)
    return pid


def test_arriving_catches_up_the_town(game):
    game.world.set_time(game.world.time + 4 * lives.SEASON)
    game.perform(Action("look"))
    now = lives.current_season(game.world)
    residents = people_at(game.world, game.place.id, exclude=game.player.id)
    assert residents and all(p.data["lived_to"] == now for p in residents)


def test_talking_catches_someone_up(game):
    pid = local(game, "test:talker", occupation="innkeeper", age=30)
    game.world.set_time(game.world.time + 4 * lives.SEASON)
    game.perform(Action("talk", pid))
    assert game.world.entity(pid).data["lived_to"] == lives.current_season(game.world)
    assert game.world.entity(pid).data["age"] == 31.0


def test_a_season_of_meditation_moves_the_world(game):
    turn = game.perform(Action("meditate", 90))
    assert clock.world_tick(game.world) == lives.current_season(game.world)
    assert any(t.startswith("The world moved on") for t in texts(turn))


def test_returning_brings_news_and_the_journal_remembers(game):
    home = game.place.id
    friend = local(game, "test:friend", occupation="tea seller", age=40)
    game.perform(Action("talk", friend))
    game.perform(Action("farewell"))
    route = travel.routes_from(game.world, game.place)[0]
    game.perform(Action("travel", route.dest))
    commit(game.world, [Event("died", (friend, friend), home, {"cause": "age", "world": True})])
    back = next(r for r in travel.routes_from(game.world, game.place)
                if (game.world.entity_by_seed(town_path(*r.dest)) or game.place).id == home)
    turn = game.perform(Action("travel", back.dest))
    lines = texts(turn)
    name = game.world.entity(friend).name
    assert any(t.startswith("Much has changed here.") and f"{name} died." in t for t in lines)
    assert any(f"{name} has died" in t for t in lines)
    assert any(b.variant.get("actor") == friend for b in game.world.beliefs(game.player.id))
    journal = texts(game.perform(Action("journal")))
    assert any(t.endswith(f"Heard: {name} died.") for t in journal)


def test_children_cannot_be_challenged_or_recruited(game):
    child = local(game, "test:child", occupation="child", age=6)
    game.perform(Action("look"))
    turn = game.perform(Action("talk", child))
    verbs = {c.action.verb for c in turn.all_choices}
    assert not verbs & {"challenge", "spar", "ask_follow", "sect_invite"}
    assert texts(game.perform(Action("challenge", child)))[-1] == "They are only a child."


def test_presence_shows_ages_and_parents(game):
    parent = local(game, "test:parent", occupation="blacksmith", age=33)
    child = local(game, "test:kid", occupation="child", age=6)
    game.world.relate(child, parent, "kin_of", data={"role": "parent"})
    game.world.relate(parent, child, "kin_of", data={"role": "child"})
    game.world.set_time(game.world.time + 1)
    here = next(t for t in texts(game.perform(Action("look"))) if t.startswith("Here:"))
    assert "(33)" in here and f"(6, child of {game.world.entity(parent).name})" in here


def test_briefs_carry_age_and_family(game):
    a = local(game, "test:wife", occupation="herbalist", age=31)
    b = local(game, "test:husband", occupation="hunter", age=33)
    commit(game.world, [Event("married", (a, b), game.place.id, {"season": lives.current_season(game.world)})])
    game.perform(Action("talk", a))
    facts = " ".join(game.last_briefs[-1].facts)
    assert "31 years old" in facts and "married" in facts


def test_an_old_save_starts_the_clocks_now(tmp_path):
    path = tmp_path / "old.world"
    old = Game.new(path, "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    old.start()
    ages = {p.id: p.data.get("age") for p in people_at(old.world, old.place.id, exclude=old.player.id)}
    for pid in ages:  # a save from before 4a has no life clock
        old.world._conn.execute("update entities set data = json_remove(data, '$.lived_to') where id = ?", (pid,))
    old.world.set_meta("world_tick", None)
    old.world.set_time(old.world.time + 40 * lives.SEASON)
    old.close()
    game = Game.load(path)
    game.start()
    now = lives.current_season(game.world)
    assert clock.world_tick(game.world) == now
    for pid, age in ages.items():
        entity = game.world.entity(pid)
        assert entity.data["lived_to"] == now and entity.data.get("age") == age
    game.close()


def test_arriving_in_a_busy_town_eight_seasons_on_is_quick(game):
    for i in range(30):
        local(game, f"test:crowd:{i}", occupation="tea seller", age=30)
    game.world.set_time(game.world.time + 8 * lives.SEASON)
    start = time.process_time()  # the work's own time, not the machine's other load
    game.perform(Action("look"))
    elapsed = time.process_time() - start
    assert elapsed < 0.15, f"arriving took {elapsed * 1000:.0f} ms"


def test_arriving_catches_the_town_up_in_one_commit(game, monkeypatch):
    """Each commit waits on the disk; one per townsperson made arrival slow under load."""
    for i in range(10):
        local(game, f"test:crowd:{i}", occupation="tea seller", age=30)
    game.world.set_time(game.world.time + 8 * lives.SEASON)
    world, outermost = game.world, []
    inner = type(world).transaction

    def counting(self):
        if self._depth == 0:
            outermost.append(1)
        return inner(self)
    monkeypatch.setattr(type(world), "transaction", counting)
    game.perform(Action("look"))
    assert len(outermost) <= 3, f"{len(outermost)} commits"
