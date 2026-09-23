import pytest

import systems.telling as telling
from engine.commands import parse
from engine.game import Action, Game
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.gen.materialize import ensure_town, people_at


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("kind", "honest"), occupation="innkeeper", town=None):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": occupation, "traits": list(traits), "realm": "mortal", "surname": surname, "given": given,
        "gender": "man", "age": 40, "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, town or game.place.id, "located_in")
    return pid


def lines(turn):
    return [text for text, _ in turn.lines]


def test_asking_for_news_passes_on_a_story(game):
    teller, a, b = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    fid = record_fact(game.world, a, "robbed", b, place=game.place.id,
                      variant=make_variant("robbed", a, b, place=game.place.name))
    game.perform(Action("talk", teller))
    turn = game.perform(Action("news"))
    assert any(text.startswith("Old Wu tells you: Ma Bo robbed Hu Mei") for text in lines(turn))
    [belief] = [x for x in game.world.beliefs(game.player.id) if x.fact_id == fid]
    assert belief.source == teller and belief.hops == 3
    assert "They have heard nothing new." in lines(game.perform(Action("news")))


def test_news_wears_out_patience(game):
    teller = person(game, "Old Wu", traits=("hot-tempered", "lazy"))
    game.perform(Action("talk", teller))
    for _ in range(4):
        game.perform(Action("news"))
    assert game.focus is None


def test_asking_about_someone_by_name(game):
    teller, a, far = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    record_fact(game.world, a, "robbed", far, place=game.place.id, variant=make_variant("robbed", a, far))
    turn = game.perform(Action("talk", teller))
    action = parse("ask about hu mei", turn.choices, turn.extra)
    assert action == Action("ask_about", far)
    assert any("Ma Bo robbed Hu Mei" in text for text in lines(game.perform(action)))
    assert "They have never heard of you." in lines(game.perform(Action("ask_about", game.player.id)))


def test_the_conversation_menu_never_shows_more_than_nine(game):
    for npc in people_at(game.world, game.place.id, exclude=game.player.id):
        for _ in range(3):
            turn = game.perform(Action("talk", npc.id))
            assert len(turn.choices) <= 9 and turn.choices[-1].action == Action("farewell")
            assert {"news", "tell_menu"} <= {c.action.verb for c in turn.choices}
            game.perform(Action("farewell"))


def test_telling_a_true_story_spreads_it(game, monkeypatch):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 1.0)
    listener, a, b = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    fid = record_fact(game.world, a, "robbed", b, place=None, variant=make_variant("robbed", a, b))
    game.world.upsert_belief(game.player.id, fid, make_variant("robbed", a, b), None, 1.0, 0, "witness")
    game.perform(Action("talk", listener))
    turn = game.perform(Action("tell_menu"))
    tell = next(c for c in turn.choices if c.action.verb == "tell")
    assert tell.label.startswith("Tell them: Ma Bo robbed Hu Mei")
    assert "Old Wu takes it in and nods." in lines(game.perform(tell.action))
    assert [x.channel for x in game.world.beliefs(listener) if x.fact_id == fid] == ["told"]
    assert any(x.fact_id == fid for x in game.world.beliefs(game.place.id))


def test_a_story_they_reject_annoys_them(game, monkeypatch):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 0.0)
    listener, a, b = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    fid = record_fact(game.world, a, "robbed", b, place=None, variant=make_variant("robbed", a, b))
    game.world.upsert_belief(game.player.id, fid, make_variant("robbed", a, b), None, 1.0, 0, "witness")
    game.perform(Action("talk", listener))
    turn = game.perform(Action("tell", (fid, game.world.beliefs(game.player.id)[0].variant_key)))
    assert "Old Wu doesn't believe you." in lines(turn)
    assert any(m.feeling == "annoyed" for m in game.world.memories(listener))


def test_a_lie_told_where_its_victim_lives_is_found_out(game, monkeypatch):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 1.0)
    listener, victim, other = person(game, "Old Wu"), person(game, "Ma Bo"), person(game, "Hu Mei")
    for someone in (victim, other):
        game.perform(Action("talk", someone))
        game.perform(Action("farewell"))
    game.perform(Action("talk", listener))
    game.perform(Action("invent_menu"))
    game.perform(Action("invent_pred", "robbed"))
    game.perform(Action("invent_subject", victim))
    turn = game.perform(Action("invent_object", other))
    [lie] = game.world.facts(is_true=False)
    assert (lie.subject, lie.predicate, lie.object) == (victim, "robbed", other)
    assert lie.data["liar"] == game.player.id and lie.source_event is not None
    assert not any(b.fact_id == lie.id for b in game.world.beliefs(game.player.id))
    assert any(b.fact_id == lie.id for b in game.world.beliefs(listener))
    assert "Ma Bo has learned that you lied about them." in lines(turn)
    assert game.world.facts(predicate="lied_about")[0].object == victim
    assert any(m.feeling == "wronged" for m in game.world.memories(victim))


def test_a_lie_about_someone_far_away_is_not_found_out_yet(game, monkeypatch):
    monkeypatch.setattr(telling, "acceptance", lambda *args, **kwargs: 1.0)
    far_town = ensure_town(game.world, 3, 0, 0)
    victim = person(game, "Ma Bo", town=far_town)
    other = person(game, "Hu Mei")
    fid = record_fact(game.world, victim, "spared", other, place=None, variant=make_variant("spared", victim, other))
    game.world.upsert_belief(game.player.id, fid, make_variant("spared", victim, other), None, 1.0, 0, "witness")
    listener = person(game, "Old Wu")
    game.perform(Action("talk", listener))
    game.perform(Action("invent_menu"))
    game.perform(Action("invent_pred", "killed"))
    game.perform(Action("invent_subject", victim))
    turn = game.perform(Action("invent_object", other))
    assert game.world.facts(is_true=False)
    assert not any("lied about" in text for text in lines(turn))
    assert game.world.facts(predicate="lied_about") == []


def test_the_rumours_page_groups_stories_and_shows_doubt(game):
    a, b, teller = person(game, "Ma Bo"), person(game, "Hu Mei"), person(game, "Old Wu")
    fid = record_fact(game.world, a, "robbed", b, place=None, variant=make_variant("robbed", a, b))
    game.world.upsert_belief(game.player.id, fid, make_variant("robbed", a, b), teller, 0.85, 1, "told")
    game.world.upsert_belief(game.player.id, fid, dict(make_variant("robbed", a, b), count=3), game.place.id, 0.4, 5,
                             "distance")
    page = lines(game.perform(Action("rumours")))
    assert "About Ma Bo:" in page
    assert "  Ma Bo robbed Hu Mei. (from a witness, told by Old Wu) Settled." in page
    assert f"    or: Ma Bo robbed Hu Mei and two others. (doubtful, gossip in {game.place.name})" in page
    assert parse("rumours", [], []) == Action("rumours")
    assert "rumours" in {c.action.verb for c in game.perform(Action("look")).all_choices}
