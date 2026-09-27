"""Phase 5c review: what the first pass over the alchemy world missed."""

import pytest

import systems.control as C
import systems.encounters as encounters
from debug.invariants import check_alchemy_world
from engine.game import Game
from systems.creation import CreationChoice
from world.events import commit


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


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal", "age": 30,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:awreview:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_a_bound_heir_leaves_the_bound_index_and_a_bound_old_player_joins_it(game):
    from systems import agendas
    from systems.succession import succession_events
    world, old = game.world, game.player.id
    master = someone(game, "master", occupation="bandit", realm="first-rate")
    heir = someone(game, "heir", age=20)
    agendas._pair(world, old, heir, "child")
    C.bind(world, heir, master)
    C.bind(world, old, master)
    assert heir in world.get_meta("bound") and old not in (world.get_meta("bound") or [])
    commit(world, succession_events(world, old, heir))
    listed = world.get_meta("bound") or []
    assert heir not in listed  # the heir, now the player, is watched turn by turn
    assert old in listed or world.entity(old).data.get("dead")  # one who steps aside is watched with the world
    assert check_alchemy_world(world) == []


def test_the_worms_say_so_when_they_bite(game):
    from engine.actions import Action
    from world.body import WATCHES_PER_DAY
    world, me = game.world, game.player.id
    C.bind(world, me, someone(game, "master", occupation="bandit", realm="first-rate"))
    world.set_time(world.time + C.MONTH + 2 * WATCHES_PER_DAY)
    turn = game.perform(Action("look"))
    assert any(t.startswith("The worms bite: 2 day(s)") for t, _ in turn.lines)
    assert not any(t.startswith("The worms bite") for t, _ in game.perform(Action("journal")).lines)  # once a day


def test_an_alchemist_stranger_says_what_they_would_teach_and_why_not(game):
    import systems.recipe_trade as RT
    from engine.actions import Action
    world = game.world
    brewer = someone(game, "brewer", occupation="herbalist")
    game.perform(Action("talk", brewer))
    turn = game.perform(Action("remedies"))
    assert any("is a" in t and "alchemist" in t for t, _ in turn.lines)
    learn = next(c.action for c in turn.all_choices if c.action.verb == "learn_recipe")
    assert any("well enough" in t for t, _ in game.perform(learn).lines)
    assert not RT.scrolls_of(world, game.player.id)


def test_a_robbed_sect_says_it_was_robbed_not_that_its_armoury_was(game, monkeypatch):
    import systems.hall_theft as T
    from systems import factions as F
    from systems import halls
    from systems.standing import standing
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    while not T.night(world):
        world.set_time(world.time + 1)
    monkeypatch.setattr(T, "BOUNDS", (0.0, 0.0))
    commit(world, T.steal_events(world, me, sect, "garden", seat))
    assert "you stole from us" in standing(world, sect, me).reasons


def test_the_hall_menu_shows_the_best_of_each_pill_then_secrets_and_herbs(game):
    from engine.actions import Action
    from systems import factions as F
    from systems import halls
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.relate(me, sect, "member_of", 2, {"role": "disciple", "hall": 0, "merit": 500, "status": "member",
                                            "secret": False})
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    shown = [c.action.verb for c in game.perform(Action("pill_hall")).choices]
    assert "secret_scroll" in shown and "harvest" in shown
    kinds = [c.action.target[2] for c in game.perform(Action("pill_hall")).choices if c.action.verb == "draw_pill"]
    assert len(kinds) == len(set(kinds))  # one line for each kind of pill on the first page
