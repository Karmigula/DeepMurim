import pytest

from engine.game import Game
from narrate.gossip_text import rumour_text
from systems import factions as F
from systems import halls
from systems.attitude import attitude
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.standing import standing


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def person(game, name, town, occupation="innkeeper"):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {"occupation": occupation, "traits": ["curious", "lazy"],
                                                 "realm": "mortal", "surname": surname, "given": given})
    game.world.relate(pid, town, "located_in")
    return pid


def deed(game, actor, predicate, target, town, **story):
    return record_fact(game.world, actor, predicate, target, place=town,
                       variant=make_variant(predicate, actor, target, place=game.world.entity(town).name, **story))


def test_a_stranger_is_neutral(game):
    sect = of_type(game.world, "orthodox_sect")
    assert standing(game.world, sect, game.player.id).word == "neutral"


def test_righteous_sects_hate_cruelty_and_cults_admire_it(game):
    sect, cult = of_type(game.world, "orthodox_sect"), of_type(game.world, "demonic_cult")
    for fid in (sect, cult):
        seat = halls.seat_of(game.world, fid)
        for name in ("Wang Li", "Hu Mei"):
            deed(game, game.player.id, "killed", person(game, name, seat), seat)
    assert standing(game.world, sect, game.player.id).word in ("distrusted", "enemy")
    assert standing(game.world, cult, game.player.id).score > 0


def test_harming_one_of_ours_is_remembered_with_a_reason(game):
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    disciple = halls.staff_at(game.world, sect, seat, roles=("disciple",))[0]
    deed(game, game.player.id, "crippled", disciple, seat)
    result = standing(game.world, sect, game.player.id)
    assert result.score < 0 and "you harmed one of ours" in result.reasons


def test_being_known_as_a_cultist_makes_the_orthodox_your_enemies(game):
    sect, cult = of_type(game.world, "orthodox_sect"), of_type(game.world, "demonic_cult")
    seat = halls.seat_of(game.world, sect)
    deed(game, game.player.id, "member_of", cult, seat)
    result = standing(game.world, sect, game.player.id)
    assert result.score <= -2 and f"you are of the {game.world.entity(cult).name}" in result.reasons
    disciple = halls.staff_at(game.world, sect, seat, roles=("disciple",))[0]
    feeling = attitude(game.world, disciple, game.player.id)
    assert feeling.word in ("wary", "hostile") and feeling.reason == f"you are of the {game.world.entity(cult).name}"


def test_masked_deeds_stay_with_the_mask(game):
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    deed(game, persona, "killed", person(game, "Wang Li", seat), seat, masked=True)
    assert standing(game.world, sect, game.player.id).word == "neutral"
    assert standing(game.world, sect, persona).score < 0
    deed(game, persona, "is", game.player.id, seat)
    assert standing(game.world, sect, game.player.id).score < 0


def test_expelled_members_are_enemies(game):
    sect = of_type(game.world, "orthodox_sect")
    game.world.relate(game.player.id, sect, "member_of", 0, {"role": "member", "status": "expelled"})
    assert standing(game.world, sect, game.player.id).word == "enemy"


def test_a_recruiter_says_how_their_faction_regards_you(game):
    from engine.actions import Action
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, seat, "located_in")
    keeper = halls.keeper_at(game.world, sect, seat)
    game.perform(Action("talk", keeper))
    turn = game.perform(Action("faction_menu"))
    view = next(c for c in turn.choices if c.action == Action("faction_view", sect))
    name = game.world.entity(sect).name
    assert view.label == f"Ask how the {name} regards you"
    text = [t for t, _ in game.perform(view.action).lines]
    assert any(f"the {name} holds you neutral" in line for line in text)


def test_membership_reads_as_a_rumour(game):
    sect = of_type(game.world, "orthodox_sect")
    name = game.world.entity(sect).name
    assert rumour_text(game.world, make_variant("member_of", game.player.id, sect), game.player.id) == f"You are of the {name}."
