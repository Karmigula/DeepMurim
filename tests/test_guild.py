import pytest

import systems.alchemy as A
import systems.encounters as encounters
import systems.guild as G
import systems.herbs as H
import systems.lives as lives
import systems.recipe_trade as RT
from debug.invariants import check_alchemy_world
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.attitude import attitude
from systems.creation import CreationChoice
from systems.purse import silver_of
from systems.standing import standing
from world.events import Event, Witness, commit


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


def a_city(world):
    from world.gen.materialize import ensure_town
    from world.gen.region import region_spec
    from world.gen.town import town_spec
    for x in range(-3, 4):
        for y in range(-3, 4):
            for i in range(region_spec(world.world_seed, x, y).town_count):
                if town_spec(world.world_seed, x, y, i).kind == "city":
                    return ensure_town(world, x, y, i)
    raise AssertionError("no city near")


def go(game, place):
    world, me = game.world, game.player.id
    world.unrelate(me, "located_in")
    world.relate(me, place, "located_in")


def someone(game, tag, place=None, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:guild:{tag}")
    game.world.relate(pid, place or game.place.id, "located_in")
    return pid


def test_the_guild_keeps_its_branches_in_the_cities(game):
    world, me = game.world, game.player.id
    city = a_city(world)
    assert G.join_block(world, me, city) is None
    if world.entity(game.place.id).data["kind"] != "city":
        assert "cities" in G.join_block(world, me, game.place.id)
    commit(world, G.join_events(world, me, city))
    assert world.entity(me).data["guild_rank"] == 0
    assert "already" in G.join_block(world, me, city)


def test_an_examination_asks_a_recipe_of_its_grade_a_fee_and_a_roll(game, monkeypatch):
    world, me = game.world, game.player.id
    city = a_city(world)
    commit(world, G.join_events(world, me, city))
    assert "recipe of grade 1" in G.exam_block(world, me, city)
    world.relate(me, A.recipe_entity(world, "calming"), "knows_recipe", 0.5)
    assert G.exam_block(world, me, city) is None
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (1.0, 1.0))
    commit(world, G.exam_events(world, me, city))
    assert world.entity(me).data["guild_rank"] == 1 and silver_of(world, me) == 5000 - G.EXAM_FEE
    assert "once a season" in G.exam_block(world, me, city)
    world.set_time(world.time + lives.SEASON)
    assert G.exam_block(world, me, city) is None  # the second rank still asks grade 1
    commit(world, G.exam_events(world, me, city))
    world.set_time(world.time + lives.SEASON)
    assert "recipe of grade 2" in G.exam_block(world, me, city)  # calming is grade 1


def test_a_failed_examination_keeps_the_rank_and_the_fee(game, monkeypatch):
    world, me = game.world, game.player.id
    city = a_city(world)
    commit(world, G.join_events(world, me, city))
    world.relate(me, A.recipe_entity(world, "calming"), "knows_recipe", 0.1)
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (0.0, 0.0))
    commit(world, G.exam_events(world, me, city))
    assert world.entity(me).data["guild_rank"] == 0 and silver_of(world, me) == 5000 - G.EXAM_FEE
    assert not world.facts(predicate="guild_rank")


def test_a_rank_is_news_and_those_who_heard_it_think_better_of_you(game, monkeypatch):
    world, me = game.world, game.player.id
    city, home = a_city(world), game.place.id
    go(game, city)
    listener = someone(game, "listener", city)
    before = attitude(world, listener, me).score
    commit(world, G.join_events(world, me, city))
    world.relate(me, A.recipe_entity(world, "calming"), "knows_recipe", 0.5)
    monkeypatch.setattr(A, "CHANCE_BOUNDS", (1.0, 1.0))
    commit(world, G.exam_events(world, me, city))
    assert G.known_rank(world, listener, me) == 1
    assert attitude(world, listener, me).score == pytest.approx(before + G.RESPECT * 1 * 0.85, abs=0.01)
    if home != city:  # the news has not yet reached another town
        assert G.known_rank(world, someone(game, "far", home), me) is None


def test_the_herbalist_sells_cheaper_to_the_guilds_own(game):
    world, me = game.world, game.player.id
    town = game.place.id
    offer = H.stock(world, town)[0]
    plain = H.price(world, town, offer["herb"], offer["grade"])
    world.update_data(me, guild_rank=5)
    cheaper = H.price(world, town, offer["herb"], offer["grade"], me)
    assert cheaper < plain and abs(cheaper - plain * (1 - 5 * G.HERB_DISCOUNT)) <= 1
    commit(world, H.buy_events(world, me, town, offer["key"]))
    assert silver_of(world, me) == 5000 - H.price(world, town, offer["herb"], offer["grade"], me)


def test_npc_alchemists_carry_a_seeded_rank(game):
    world = game.world
    brewer = someone(game, "brewer", occupation="herbalist")
    seller = someone(game, "seller")
    rank = G.rank_of(world, brewer)
    assert G.NPC_RANKS[0] <= rank <= G.NPC_RANKS[1] and G.rank_of(world, brewer) == rank
    assert G.rank_of(world, seller) is None
    assert G.title(5) == "a fifth-rank alchemist"


def test_a_sects_pill_master_is_an_alchemist(game):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    [keeper] = halls.staff_at(world, sect, seat, roles=("keeper",))
    assert G.is_pill_master(world, keeper) and G.rank_of(world, keeper) is not None


def test_a_scroll_read_teaches_its_recipe_and_is_kept(game):
    world, me = game.world, game.player.id
    scroll = RT.make_scroll(world, me, "cleansing", "guild")
    assert RT.read_block(world, me, scroll) is None
    commit(world, RT.read_events(world, me, scroll, game.place.id))
    assert A.mastery(world, me, A.recipe_entity(world, "cleansing")) == A.DISCOVERED_MASTERY
    assert scroll in world.targets(me, "owns")
    assert "already" in RT.read_block(world, me, scroll)


def test_the_guild_sells_scrolls_up_to_the_readers_rank_and_buys_them_back_at_half(game):
    world, me = game.world, game.player.id
    city = a_city(world)
    assert RT.guild_offers(world, me) == []
    world.update_data(me, guild_rank=0)
    assert RT.guild_offers(world, me) == []  # an unranked member buys nothing yet
    world.update_data(me, guild_rank=1)
    offers = RT.guild_offers(world, me)
    assert offers and all(G.recipe_grade(k) == 1 for k in offers)
    key = offers[0]
    assert RT.buy_block(world, me, key, city) is None
    commit(world, RT.buy_events(world, me, key, city))
    [scroll] = RT.scrolls_of(world, me)
    assert silver_of(world, me) == 5000 - RT.price(key) and scroll.data["source"] == "guild"
    commit(world, RT.sell_events(world, me, scroll.id, city))
    assert silver_of(world, me) == 5000 - RT.price(key) // 2 and not RT.scrolls_of(world, me)


def test_a_sects_hall_gives_its_secret_scrolls_to_its_ranked_for_merit(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    secrets = RT.secret_recipes(world, sect)
    assert RT.SECRETS[0] <= len(secrets) <= RT.SECRETS[1] and RT.secret_recipes(world, sect) == secrets
    world.relate(me, sect, "member_of", 1, {"role": "disciple", "hall": 0, "merit": 500, "status": "member",
                                            "secret": False})
    assert "second rank" in RT.secret_block(world, me, sect, secrets[0], seat)
    world.relate(me, sect, "member_of", 2, {"role": "disciple", "hall": 0, "merit": 500, "status": "member",
                                            "secret": False})
    assert RT.secret_block(world, me, sect, secrets[0], seat) is None
    commit(world, RT.secret_events(world, me, sect, secrets[0], seat))
    [scroll] = RT.scrolls_of(world, me)
    assert scroll.data["faction"] == sect and scroll.data["source"] == "sect"
    assert F.membership(world, me, sect)[1]["merit"] == 500 - RT.secret_cost(secrets[0])
    assert "already" in RT.secret_block(world, me, sect, secrets[0], seat)


def test_an_alchemist_who_likes_you_teaches_a_recipe_for_silver(game):
    world, me = game.world, game.player.id
    brewer = someone(game, "teacher", occupation="herbalist")
    key = RT.npc_recipes(world, brewer)[0]
    assert "well enough" in RT.teach_block(world, me, brewer, key)
    commit(world, [Event("helped", (me, brewer), game.place.id, {}, witnesses=(Witness(brewer, "grateful", 1.0),))])
    assert RT.teach_block(world, me, brewer, key) is None
    commit(world, RT.teach_events(world, me, brewer, key, game.place.id))
    assert any(s.data["key"] == key and s.data["source"] == "master" for s in RT.scrolls_of(world, me))


def test_a_secret_sold_to_a_rival_fetches_triple_and_the_sect_hates_the_seller(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    rival = RT.rivals_of(world, sect)[0]
    rival_seat = halls.seat_of(world, rival)
    seat = halls.seat_of(world, sect)
    scroll = RT.make_scroll(world, me, RT.secret_recipes(world, sect)[0], "stolen", sect)
    assert RT.secret_sale_block(world, me, scroll, rival, rival_seat) is None
    assert RT.secret_sale_block(world, me, scroll, sect, seat) is not None
    before = standing(world, sect, me).score
    commit(world, RT.secret_sale_events(world, me, scroll, rival, rival_seat))
    assert silver_of(world, me) == 5000 + RT.price(world.entity(scroll).data["key"]) * RT.RIVAL_SHARE
    [fact] = world.facts(predicate="sold_secret")
    from systems.beliefs import believe
    believe(world, seat, fact.id, fact.variant, None, 1.0, 1, "gossip")
    assert standing(world, sect, me).score < before - 1


def test_the_rules_hold_ranks_within_nought_to_nine_and_scrolls_to_one_owner(game):
    world, me = game.world, game.player.id
    scroll = RT.make_scroll(world, me, "cleansing", "guild")
    assert check_alchemy_world(world) == []
    world.update_data(me, guild_rank=10)
    other = someone(game, "holder")
    world.relate(other, scroll, "owns")
    problems = " | ".join(check_alchemy_world(world))
    assert "rank" in problems and "owner" in problems
