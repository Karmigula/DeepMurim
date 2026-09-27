import pytest

import systems.alchemy as A
import systems.poison_path as PP
import systems.toxins as X
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.herbs import make_herb
from systems.techniques import create_technique, generate, teach
from world.events import Event, commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=5000)
    yield g
    g.close()


def poison_art(game, mastery=0.6, form="palm"):
    world, me = game.world, game.player.id
    name, data = generate(rng_for(world.world_seed, "test:poison_art"), "martial", form=form, grade=2, element="poison")
    teach(world, me, create_technique(world, name, data), completeness=1.0, known_completeness=1.0,
          source="test", mastery=mastery)


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "mortal", "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:pp:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_a_poison_art_turns_poison_into_qi_and_venom(game):
    world, me = game.world, game.player.id
    poison_art(game)
    body = load_body(world, me)
    body.realm, body.energy_years, body.bottleneck = 2, 6.0, False
    save_body(world, me, body)
    share = PP.conversion(world, me, load_body(world, me))
    assert share == pytest.approx(min(0.9, 0.3 + 0.5 * 0.6 + 0.05 * 2))
    X.poison(world, me, 4, 10, "test")
    after = load_body(world, me)
    assert after.venom == pytest.approx(share * 40) and after.energy_years > 6.0
    assert after.poisons and after.poisons[0]["strength"] == int(10 * (1 - share))


def test_without_the_art_a_poison_is_suffered_whole(game):
    world, me = game.world, game.player.id
    X.poison(world, me, 4, 10, "test")
    assert load_body(world, me).venom == 0 and load_body(world, me).poisons[0]["strength"] == 10


def test_enough_venom_turns_the_body_and_the_world_hears(game):
    world, me = game.world, game.player.id
    poison_art(game, mastery=1.0)
    body = load_body(world, me)
    body.venom = 55.0
    save_body(world, me, body)
    X.poison(world, me, 5, 10, "test")
    assert load_body(world, me).constitution == PP.POISON_BODY and world.facts(predicate="poison_body", subject=me)


def test_a_poison_body_shrugs_off_lesser_poisons_and_its_blood_poisons(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.constitution = PP.POISON_BODY
    save_body(world, me, body)
    assert X.poison(world, me, 3, 10, "test") == "absorbed" and load_body(world, me).poisons == []
    striker = someone(game, "striker")
    striker_body = load_body(world, striker)
    PP._strikes(world, striker, me, "fist", striker_body, load_body(world, me))
    assert striker_body.poisons and striker_body.poisons[0]["grade"] == PP.BLOOD_GRADE


def test_a_poison_arts_wound_poisons(game):
    world, me = game.world, game.player.id
    poison_art(game, form="palm")
    target = someone(game, "target")
    body = load_body(world, target)
    PP._strikes(world, me, target, "palm", load_body(world, me), body)
    assert body.poisons and body.poisons[0]["grade"] == 1 + int(0.6 * 3)
    clean = load_body(world, target)
    PP._strikes(world, me, target, "sword", load_body(world, me), clean)
    assert clean.poisons == []  # another art's wound carries none


def test_healing_works_at_half_on_a_poison_body(game):
    import systems.pills as P
    from world.body import add_injury
    world, me = game.world, game.player.id
    key = next(k for k, r in A.RECIPES.items() if r["effect"] == "healing")

    def healed_by_a_pill(poison_body: bool) -> int:
        body = load_body(world, me)
        body.injuries = []
        body.constitution = PP.POISON_BODY if poison_body else None
        for location in ("left arm", "right arm", "left leg"):
            add_injury(body, location, "cut", 3, world.time, "test")
        save_body(world, me, body)
        before = [i.heals_at for i in load_body(world, me).injuries]
        item = A.make_pill(world, me, A.recipe_entity(world, key), 2, 1.0)
        commit(world, P.swallow_events(world, me, game.place.id, item))
        return sum(1 for a, b in zip(before, (i.heals_at for i in load_body(world, me).injuries)) if b < a)
    assert healed_by_a_pill(False) == 2 and healed_by_a_pill(True) == 1


def test_an_unorthodox_keeper_sells_a_poison_art(game):
    world, me = game.world, game.player.id
    clan = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "unorthodox_clan")
    seat = halls.seat_of(world, clan)
    [keeper] = halls.staff_at(world, clan, seat, roles=("keeper",))[:1]
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    assert PP.art_block(world, me, keeper) is None
    commit(world, PP.art_events(world, me, keeper, seat))
    from systems.items import manuals_of
    [manual] = manuals_of(world, me)
    assert manual.technique.data["element"] == "poison"


def test_a_venomous_beast_bites_with_venom_and_can_be_butchered(game, monkeypatch):
    monkeypatch.setattr(PP, "BEAST_CHANCE", 1.0)
    world, me = game.world, game.player.id
    from world.gen.materialize import region_of
    region = region_of(world, game.place.id)
    world.update_data(region.id, terrain="marsh")
    beast = PP.venomous_beast(world, me, world.entity(region.id))
    assert world.entity(beast).data["venomous"]
    body = load_body(world, me)
    PP._strikes(world, beast, me, "claws", load_body(world, beast), body)
    assert any(p["grade"] == PP.BITE_GRADE for p in body.poisons)
    assert PP.butcher_block(world, me, beast, game.place.id) is not None  # it still lives
    commit(world, [Event("died", (me, beast), game.place.id, {"cause": "killed"})])
    assert PP.butcher_block(world, me, beast, game.place.id) is None
    commit(world, PP.butcher_events(world, me, beast, game.place.id, "blood"))
    assert load_body(world, me).resist == PP.BLOOD_RESIST
    assert PP.butcher_block(world, me, beast, game.place.id) == "There is nothing to take."


def test_a_tempering_bath_raises_a_stat_to_its_limit(game):
    world, me = game.world, game.player.id
    key = next(k for k, r in A.RECIPES.items() if r["effect"] == "tempering")
    before = load_body(world, me).physique["strength"]
    for n in range(PP.BATH_LIMIT):
        draught = A.make_pill(world, me, A.recipe_entity(world, key), 2, 1.0)
        assert PP.bath_block(world, me, game.place.id, "strength", draught) is None
        commit(world, PP.bath_events(world, me, game.place.id, "strength", draught))
    assert load_body(world, me).physique["strength"] == min(20, before + PP.BATH_LIMIT)
    draught = A.make_pill(world, me, A.recipe_entity(world, key), 2, 1.0)
    assert "no further" in PP.bath_block(world, me, game.place.id, "strength", draught)


def test_a_legendary_herb_in_the_bath_may_awaken_a_constitution(game, monkeypatch):
    monkeypatch.setattr(PP, "AWAKEN", 1.0)
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.constitution = None
    save_body(world, me, body)
    key = next(k for k, r in A.RECIPES.items() if r["effect"] == "tempering")
    draught = A.make_pill(world, me, A.recipe_entity(world, key), 2, 1.0)
    herb = make_herb(world, "snow lingzhi", 3, me)
    commit(world, PP.bath_events(world, me, game.place.id, "endurance", draught, herb))
    assert load_body(world, me).constitution == "Nine Yin Body"


def test_the_alchemy_rules_catch_a_malformed_pill(game):
    from debug.invariants import check_alchemy
    world, me = game.world, game.player.id
    key = next(k for k, r in A.RECIPES.items() if r["effect"] == "qi")
    item = A.make_pill(world, me, A.recipe_entity(world, key), 2, 1.0)
    make_herb(world, "ginseng", 1, me)
    assert check_alchemy(world) == []
    world.update_data(item, grade=9)
    assert any("malformed pill" in p for p in check_alchemy(world))
