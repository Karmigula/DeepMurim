import pytest

from engine.game import Game
from systems.creation import CreationChoice
from systems.items import create_manual, manual_price, manuals_of, transfer_events
from systems.purse import payment_events, silver_of
from systems.techniques import create_technique, generate
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "merchant"))
    yield g
    g.close()


def merchant(game):
    pid = game.world.add_entity("person", "Rich Ma", {"occupation": "merchant", "traits": ["greedy"]}, seed_path="test:merchant")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def technique(game, grade=2):
    name, data = generate(rng_for(1, "t"), "martial", form="palm", grade=grade)
    return create_technique(game.world, name, data)


def test_npc_purses_are_seeded_and_stable(game):
    npc = merchant(game)
    first = silver_of(game.world, npc)
    assert 40 <= first <= 200 and silver_of(game.world, npc) == first
    assert game.world.entity(npc).data["silver"] == first
    assert silver_of(game.world, game.player.id) == 200  # merchant's runaway


def test_payment_moves_silver(game):
    npc = merchant(game)
    before = silver_of(game.world, npc)
    commit(game.world, payment_events(game.player.id, npc, game.place.id, 50, "test"))
    assert silver_of(game.world, game.player.id) == 150 and silver_of(game.world, npc) == before + 50


def test_paying_more_than_you_have_changes_nothing(game):
    npc = merchant(game)
    before = (silver_of(game.world, game.player.id), silver_of(game.world, npc))
    with pytest.raises(ValueError):
        commit(game.world, payment_events(game.player.id, npc, game.place.id, 5000, "test"))
    assert (silver_of(game.world, game.player.id), silver_of(game.world, npc)) == before


def test_manuals_are_owned_priced_and_handed_over(game):
    npc = merchant(game)
    item = create_manual(game.world, npc, technique(game, grade=2), 0.6)
    [manual] = manuals_of(game.world, npc)
    assert manual.item.id == item and manual.claimed == 1.0 and manual.true_completeness == 0.6
    assert manual.name.endswith(" manual") and manual_price(manual) == 15 * 4 + 10
    commit(game.world, transfer_events(npc, game.player.id, game.place.id, [item], "bought"))
    assert manuals_of(game.world, npc) == [] and [m.item.id for m in manuals_of(game.world, game.player.id)] == [item]
    with pytest.raises(ValueError):
        commit(game.world, transfer_events(npc, game.player.id, game.place.id, [item], "again"))
