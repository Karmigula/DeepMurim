"""Phase 5b final review: what a player meets at the furnace, the herbalist and the bath."""
import pytest

import systems.alchemy as A
import systems.encounters as encounters
import systems.herbs as H
import systems.pills as P
import systems.poison_path as PP
import systems.toxins as X
from debug.invariants import check_toxins
from engine.actions import Action
from engine.alchemy_page import poison_words
from engine.game import Game
from narrate.outcomes import OUTCOME_BUILDERS
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import PHYSIQUE, WATCHES_PER_DAY
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=5000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:review5b:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def pill(world, me, key, grade=2):
    return A.make_pill(world, me, A.recipe_entity(world, key), grade, 0.8)


def test_tasting_the_most_toxic_herb_does_not_kill_a_new_hero(game):
    world, me = game.world, game.player.id
    worst = max(H.HERBS, key=lambda n: H.props(n)["toxicity"])
    herb = H.make_herb(world, worst, 0, me)
    game.perform(Action("taste", herb))
    assert load_body(world, me).poisons  # it still sickens
    world.set_time(world.time + 3 * WATCHES_PER_DAY)
    game.perform(Action("rest"))
    assert not (world.entity(me).data.get("dying") or world.entity(me).data.get("dead"))


def test_the_page_tells_what_a_poison_will_do(game):
    world, me = game.world, game.player.id
    X.poison(world, me, 5, 40, "a hidden needle")
    X.poison(world, me, 2, 10, "tasting black lotus")
    words = poison_words(load_body(world, me))
    assert any("it will kill you within 2 day(s)" in w for w in words)
    assert any("grade 2" in w and "3 day(s) of it left" in w for w in words)  # 2.5 days is not told as 2


def test_a_bare_swallow_never_drinks_a_poison(game):
    world, me = game.world, game.player.id
    pill(world, me, "yin_poison", 4)
    turn = game.perform(Action("swallow"))
    assert "You have no pill to swallow." in [t for t, _ in turn.lines]
    assert not load_body(world, me).poisons
    qi = pill(world, me, "earth_qi")
    game.perform(Action("swallow"))
    assert qi not in world.targets(me, "owns")


def test_a_bath_takes_a_treasure_herb_only_when_asked(game):
    world, me, here = game.world, game.player.id, game.place.id
    herb = H.make_herb(world, "ginseng", 3, me)
    pill(world, me, "fire_tempering")
    game.perform(Action("bath_menu"))
    game.perform(Action("bathe", PHYSIQUE[0]))
    assert herb in world.targets(me, "owns")  # a plain bath leaves the herb alone
    pill(world, me, "fire_tempering")
    labels = [c.label for c in game.perform(Action("bath_menu")).all_choices]
    assert any("with ginseng" in label for label in labels)


def test_a_bath_awakens_nothing_in_a_body_already_awake(game, monkeypatch):
    world, me, here = game.world, game.player.id, game.place.id
    monkeypatch.setattr(PP, "AWAKEN", 1.0)
    body = load_body(world, me)
    body.constitution, body.constitution_known = "Nine Yin Body", True
    save_body(world, me, body)
    herb = H.make_herb(world, "ginseng", 3, me)
    draught = pill(world, me, "fire_tempering")
    assert PP.bath_events(world, me, here, PHYSIQUE[0], draught, herb)[0].data["awaken"] is None
    pill(world, me, "fire_tempering")
    labels = [c.label for c in game.perform(Action("bath_menu")).all_choices]
    assert not any("with ginseng" in label for label in labels)  # no herb is offered where it can do nothing


def test_a_weak_slipped_poison_is_not_told_as_a_death(game):
    world, me = game.world, game.player.id
    leader = someone(game, "leader")
    weak = Event("poison_slipped", (me, leader), game.place.id, {"faction": None, "vial": 0, "grade": 2})
    strong = Event("poison_slipped", (me, leader), game.place.id, {"faction": None, "vial": 0, "grade": 4})
    assert "does not see the dawn" not in " ".join(OUTCOME_BUILDERS["poison_slipped"](world, weak)[0])
    assert "does not see the dawn" in " ".join(OUTCOME_BUILDERS["poison_slipped"](world, strong)[0])


def test_the_alchemy_menu_shows_the_furnace_first_and_each_herb_once(game):
    world, me = game.world, game.player.id
    for _ in range(2):
        pill(world, me, "earth_qi")
    herbs = [H.make_herb(world, "frost lotus leaf", 0, me) for _ in range(5)]
    game.perform(Action("alchemy"))
    game.perform(Action("add_herb", herbs[0]))
    turn = game.perform(Action("add_herb", herbs[1]))
    shown = [c.label for c in turn.choices]
    assert "Light the furnace (2 herbs)" in shown and "Empty the furnace" in shown
    assert len(shown) == len(set(shown))  # identical herbs and pills are offered once
    assert any(label.startswith("Taste frost lotus leaf") for label in shown)
    assert any(label.startswith("Put frost lotus leaf") for label in shown)


def test_the_herbalist_offers_the_furnace_first(game):
    shown = [c.label for c in game.perform(Action("herbalist")).choices]
    assert shown[0].startswith("Buy a bronze furnace")


def test_a_sludge_teaches_nothing(game):
    world, me = game.world, game.player.id
    tray = [H.make_herb(world, name, 0, me) for name in ("black lotus", "willow bark")]
    mix = A.combine(["black lotus", "willow bark"])
    assert A.best_match(mix)[0] is None or not all(A.met(A.RECIPES[A.best_match(mix)[0]], mix).values())
    events = A.experiment_events(world, me, game.place.id, tray)
    assert events[0].data["result"] != "discovered"
    commit(world, events)
    assert not H.known(world, me, "black lotus")  # only a success teaches (spec 2.2)


def test_a_failed_refining_teaches_nothing(game, monkeypatch):
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (0.0, 0.0))
    world, me = game.world, game.player.id
    recipe = A.recipe_entity(world, "earth_qi")
    world.relate(me, recipe, "knows_recipe", 0.1)
    batch = [H.make_herb(world, name, 0, me) for name in ("ginseng", "tiger bone vine", "willow bark")]
    commit(world, A.refine_events(world, me, game.place.id, recipe, batch))
    assert not H.known(world, me, "ginseng")


def test_an_heir_leaves_the_poisoned_index(game):
    from systems import agendas
    from systems.succession import succession_events
    world, old = game.world, game.player.id
    heir = someone(game, "heir", age=20)
    agendas._pair(world, old, heir, "child")
    X.poison(world, heir, 2, 8, "a hidden needle")
    assert heir in world.get_meta("poisoned")
    commit(world, succession_events(world, old, heir))
    assert heir not in (world.get_meta("poisoned") or [])
    assert check_toxins(world) == []
    X.poison(world, heir, 5, 40, "a hidden needle")  # the heir, now the player, dies at a turn's end, not a season's
    world.set_time(world.time + 4 * WATCHES_PER_DAY)
    assert X.season_hook(world, 0) == []
