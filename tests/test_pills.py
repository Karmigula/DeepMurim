import pytest

import systems.alchemy as A
import systems.duel as duel
import systems.gear as gear
import systems.pills as P
import systems.toxins as X
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import add_injury
from world.events import Event, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def pill(game, effect, grade=2, purity=1.0):
    key = next(k for k, r in A.RECIPES.items() if r["effect"] == effect)
    return A.make_pill(game.world, game.player.id, A.recipe_entity(game.world, key), grade, purity)


def room_to_grow(game):
    """A second-rate body far from its bottleneck, so a qi pill's years all count."""
    body = load_body(game.world, game.player.id)
    body.realm, body.energy_years, body.bottleneck = 2, 6.0, False
    save_body(game.world, game.player.id, body)


def swallow(game, item):
    world, me = game.world, game.player.id
    assert P.swallow_block(world, me, item) is None
    commit(world, P.swallow_events(world, me, game.place.id, item))


def test_a_qi_pill_gives_energy_dulled_by_residue(game):
    world, me = game.world, game.player.id
    room_to_grow(game)
    before = load_body(world, me).energy_years
    swallow(game, pill(game, "qi", grade=2))
    after = load_body(world, me).energy_years
    assert after == pytest.approx(before + 1.0)
    body = load_body(world, me)
    body.residue = 75.0
    save_body(world, me, body)
    swallow(game, pill(game, "qi", grade=2))
    assert load_body(world, me).energy_years - after == pytest.approx(1.0 * (1 - 75 / 150), abs=0.05)


def test_a_pill_leaves_residue_by_its_impurity(game):
    world, me = game.world, game.player.id
    swallow(game, pill(game, "calming", grade=3, purity=0.5))
    assert load_body(world, me).residue == pytest.approx(15.0)


def test_a_treasure_pill_is_a_grade_two_qi_pill(game):
    world, me = game.world, game.player.id
    room_to_grow(game)
    item = world.add_entity("treasure", "a Nine-Turn Golden Pill", {"kind": "pill", "qi_years": 2.0, "used": False})
    world.relate(me, item, "owns")
    before = load_body(world, me).energy_years
    swallow(game, item)
    body = load_body(world, me)
    assert body.energy_years == pytest.approx(before + 2.0) and body.residue == pytest.approx(6.0)


def test_healing_mending_calming_cleansing_and_purity(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    add_injury(body, "left arm", "cut", 3, world.time, "test")
    body.meridians["Lung"].state = "damaged"
    body.deviation, body.residue = 40.0, 40.0
    save_body(world, me, body)
    heals = load_body(world, me).injuries[0].heals_at
    swallow(game, pill(game, "healing", grade=2))
    assert load_body(world, me).injuries[0].heals_at < heals
    swallow(game, pill(game, "mending", grade=2))
    assert load_body(world, me).meridians["Lung"].state == "open"
    swallow(game, pill(game, "calming", grade=2))
    assert load_body(world, me).deviation <= 40.0 - 10
    swallow(game, pill(game, "cleansing", grade=2))
    assert load_body(world, me).residue < 40.0
    purity = load_body(world, me).purity
    swallow(game, pill(game, "purity", grade=2))
    assert load_body(world, me).purity > purity


def test_a_breakthrough_pill_helps_the_next_attempt(game):
    world, me = game.world, game.player.id
    swallow(game, pill(game, "bottleneck", grade=3))
    assert load_body(world, me).breakthrough_aid == pytest.approx(0.3)


def test_an_antidote_cures_and_a_poison_poisons(game):
    world, me = game.world, game.player.id
    swallow(game, pill(game, "poison", grade=3))
    [p] = load_body(world, me).poisons
    assert p["grade"] == 3 and p["strength"] == 3 * P.POISON_STRENGTH
    swallow(game, pill(game, "antidote", grade=3))
    assert load_body(world, me).poisons == []


def test_venom_goes_on_a_blade_and_poisons_its_wounds(game):
    world, me = game.world, game.player.id
    venom = pill(game, "venom", grade=2)
    assert P.swallow_block(world, me, venom) == "Venom goes on a blade, not down the throat."
    if gear.weapon_of(world, me) is None:
        pytest.skip("a hand art")
    commit(world, P.coat_events(world, me, game.place.id, venom))
    assert world.entity(me).data["venom_coat"] == {"grade": 2, "strikes": 3}
    foe = world.add_entity("person", "A Foe", {"occupation": "bandit", "traits": ["greedy"], "realm": "mortal",
                                               "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:pill:foe")
    world.relate(foe, game.place.id, "located_in")
    form = duel.best_art(world, me).form
    target = load_body(world, foe)
    X.WOUND_HOOKS[0](world, me, foe, form, load_body(world, me), target)
    assert target.poisons and target.poisons[0]["grade"] == 2
    assert world.entity(me).data["venom_coat"]["strikes"] == 2


def test_a_weak_brewed_poison_sickens_a_master_rather_than_killing(game):
    import systems.scheming as S
    from systems import factions as F
    from systems import halls
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    pill(game, "poison", grade=2)
    events = S.poison_events(world, me, leader, seat)
    assert [e.kind for e in events] == ["poison_slipped"]
    commit(world, events)
    assert not world.entity(leader).data.get("dead") and load_body(world, leader).poisons
