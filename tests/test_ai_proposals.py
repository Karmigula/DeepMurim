import pytest

import systems.encounters as encounters
from ai import deeds as D
from ai.validate import DIALOGUE_KINDS, MAX_PROPOSALS, PER_TOWN, Scene, accept
from debug.invariants import check_ai
from engine.actions import Action, Choice
from engine.game import Game
from engine.journal import summarize
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit
from world.gen.materialize import people_at


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def scene(game, choices=(), salt="t1"):
    return Scene(game.world, game.player.id, game.place.id, list(choices), salt)


def someone(game):
    return people_at(game.world, game.place.id, exclude=game.player.id)[0]


def test_paying_moves_silver_and_never_more_than_you_have(game):
    npc, me = someone(game), game.player.id
    mine, theirs = silver_of(game.world, me), silver_of(game.world, npc.id)
    done = accept(scene(game), [{"kind": "pay", "to": npc.name, "amount": 2},
                                {"kind": "pay", "to": npc.name, "amount": mine},  # together, more than you have
                                {"kind": "pay", "to": "Nobody Here", "amount": 1}])
    assert [why for _, why in done.rejected] == ["you have not that much silver", "they are not here"]
    commit(game.world, done.events)
    assert silver_of(game.world, me) == mine - 2 and silver_of(game.world, npc.id) == theirs + 2
    assert check_ai(game.world) == []


def test_a_feeling_is_remembered_once_a_person_a_line_and_within_its_strength(game):
    npc = someone(game)
    done = accept(scene(game), [{"kind": "feeling", "who": npc.name, "feeling": "grateful", "strength": 0.4},
                                {"kind": "feeling", "who": npc.name, "feeling": "amused", "strength": 0.2},
                                {"kind": "feeling", "who": npc.name, "feeling": "adoring", "strength": 0.2}])
    assert [why for _, why in done.rejected] == ["one feeling a person a line", "no such feeling"]
    commit(game.world, done.events)
    assert any(m.feeling == "grateful" for m in game.world.memories(npc.id, about=game.player.id))
    too_strong = accept(scene(game), [{"kind": "feeling", "who": npc.name, "feeling": "fear", "strength": 0.9}])
    assert too_strong.events == [] and "strength" in too_strong.rejected[0][1]


def test_a_deed_names_only_the_known_and_becomes_a_tale(game):
    npc = someone(game)
    done = accept(scene(game), [{"kind": "deed", "text": f"You carried {npc.name}'s baskets to market.",
                                 "tone": "kind"},
                                {"kind": "deed", "text": "You bested Mo Tianlong at dice.", "tone": "bold"},
                                {"kind": "deed", "text": "You did a thing.", "tone": "sly"}])
    assert [why for _, why in done.rejected] == ["it names Mo Tianlong, whom you do not know", "no such tone"]
    commit(game.world, done.events)
    tales = game.world._conn.execute("select count(*) from facts where predicate = 'deed_kind'").fetchone()[0]
    assert tales == 1  # a tale of the world, to spread and be judged by its tone


def test_one_newcomer_a_line_and_only_of_the_worlds_trades(game):
    new = {"kind": "minor_npc", "occupation": "tea seller", "traits": ["cheerful"], "realm": "mortal"}
    done = accept(scene(game), [new, dict(new), {**new, "occupation": "astronaut"}])
    assert [why for _, why in done.rejected] == ["one newcomer a line", "no such trade"]
    before = len(people_at(game.world, game.place.id))
    commit(game.world, done.events)
    assert len(people_at(game.world, game.place.id)) == before + 1
    assert check_ai(game.world) == []


def test_hurt_and_time_stay_within_their_limits(game):
    start = game.world.time
    done = accept(scene(game), [{"kind": "hurt", "location": "left arm", "injury": "cut", "severity": 1},
                                {"kind": "hurt", "location": "left arm", "injury": "cut", "severity": 5},
                                {"kind": "time", "watches": 2}, {"kind": "time", "watches": 40}])
    assert len(done.events) == 2 and len(done.rejected) == 2
    commit(game.world, done.events)
    assert game.world.time == start + 2 and any(i.location == "left arm" for i in game.body().injuries)


def test_an_action_must_be_one_of_this_turns_choices(game):
    rest = Choice("Rest a while", Action("rest"))
    done = accept(scene(game, [rest]), [{"kind": "action", "choice": "Rest a while"},
                                        {"kind": "action", "choice": "Fly to the moon"}])
    assert done.action == Action("rest") and done.rejected[0][1] == "no such choice now"


def test_talk_proposes_no_action_and_no_newcomer(game):
    rest = Choice("Rest a while", Action("rest"))
    done = accept(scene(game, [rest]), [{"kind": "action", "choice": "Rest a while"},
                                        {"kind": "minor_npc", "occupation": "tea seller", "traits": ["cheerful"]}],
                  kinds=DIALOGUE_KINDS)
    assert done.action is None and [why for _, why in done.rejected] == ["not while talking"] * 2


def test_at_most_four_proposals_are_weighed(game):
    many = [{"kind": "time", "watches": 1}] * (MAX_PROPOSALS + 2)
    done = accept(scene(game), many)
    assert len(done.events) == MAX_PROPOSALS and [why for _, why in done.rejected] == ["too many changes"] * 2


def test_what_was_talked_of_is_remembered_and_summarised(game):
    npc, me = someone(game), game.player.id
    commit(game.world, [D.talked(me, npc.id, game.place.id, "You asked after the bandits on the marsh road.",
                                 "Any news of bandits?")])
    memory = [m for m in game.world.memories(npc.id, about=me) if m.event.kind == "talked"]
    assert memory and "bandits on the marsh road" in summarize(game.world, memory[-1].event)
    assert check_ai(game.world) == []


def test_every_accepted_change_has_its_engine_line(game):
    npc = someone(game)
    done = accept(scene(game), [{"kind": "feeling", "who": npc.name, "feeling": "grateful", "strength": 0.3},
                                {"kind": "time", "watches": 1}])
    lines = game._commit(done.events)
    assert f"{npc.name} is grateful." in [t for t, _ in lines] and "A watch passes." in [t for t, _ in lines]


def test_check_ai_finds_a_change_past_its_limits(game):
    npc = someone(game)
    commit(game.world, [Event("ai_felt", (game.player.id, npc.id), game.place.id,
                              {"feeling": "fear", "strength": 0.9, "ai": True, "proposal": {}})])
    commit(game.world, [Event("parted", (game.player.id, npc.id), game.place.id, {"ai": True})])
    problems = check_ai(game.world)
    assert any("feeling past its limits" in p for p in problems)
    assert any("of no proposal kind" in p for p in problems)


def test_a_town_takes_at_most_six_newcomers(game):
    town = game.place.id
    game.world.update_data(town, ai_people=PER_TOWN)
    done = accept(scene(game), [{"kind": "minor_npc", "occupation": "tea seller", "traits": ["cheerful"]}])
    assert done.rejected[0][1] == "enough newcomers here for now"


def test_a_deed_is_weighed_by_heaven_and_the_heart_by_its_tone(game):
    from systems.heart import heart_of
    from systems.karma import karma_of
    world, me = game.world, game.player.id
    merit, lean = karma_of(world, me)["merit"], heart_of(world, me)["lean"]
    commit(world, accept(scene(game), [{"kind": "deed", "text": "You fed a starving beggar.", "tone": "kind"}]).events)
    assert karma_of(world, me)["merit"] > merit and heart_of(world, me)["lean"] > lean
    sin, lean = karma_of(world, me)["sin"], heart_of(world, me)["lean"]
    commit(world, accept(scene(game), [{"kind": "deed", "text": "You kicked a beggar.", "tone": "cruel"}]).events)
    assert karma_of(world, me)["sin"] > sin and heart_of(world, me)["lean"] < lean


def test_one_deed_a_line(game):
    done = accept(scene(game), [{"kind": "deed", "text": "You helped an old woman.", "tone": "kind"},
                                {"kind": "deed", "text": "You helped another.", "tone": "kind"}])
    assert len(done.events) == 1 and [why for _, why in done.rejected] == ["one deed a line"]


def test_check_ai_reads_only_the_models_events_however_long_the_history(game):
    import gc
    import time
    world = game.world
    with world.transaction():
        world._conn.executemany("insert into chronicle(time, kind, actors, place, data) values (?, ?, ?, ?, ?)",
                                [(0, "rested", "[]", None, '{"days": 1}')] * 100_000)
    commit(world, accept(scene(game), [{"kind": "time", "watches": 1}]).events)
    check_ai(world)
    gc.collect()
    best = float("inf")
    for _ in range(5):
        began = time.perf_counter()
        check_ai(world)
        best = min(best, time.perf_counter() - began)
    assert best < 0.005  # the soak's check of the whole world has 0.3 s for everything
