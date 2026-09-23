import pytest

import systems.encounters as encounters
import systems.founding as founding
import systems.land as land
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event, Witness, commit
from world.gen.materialize import people_at


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


def home_town(game):
    """A town with a magistrate that the player owns."""
    for fid in [None]:
        pass
    from tests.test_land import buyable_town
    town = buyable_town(game)
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")
    commit(game.world, land.claim_events(game.player.id, town))
    return town


def renowned(game, town):
    for i in range(3):
        bandit = game.world.add_entity("person", f"Ma Da{i}", {"realm": "mortal", "occupation": "bandit"})
        record_fact(game.world, game.player.id, "killed", bandit, place=town,
                    variant=make_variant("killed", game.player.id, bandit, place=game.world.entity(town).name))


def friend(game, town, name):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {"realm": "mortal", "occupation": "farmer", "traits": ["kind", "honest"],
                                                 "surname": surname, "given": given,
                                                 "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, town, "located_in")
    commit(game.world, [Event("helped", (game.player.id, pid), town, {}, witnesses=(Witness(pid, "grateful", 1.0),))])
    return pid


def ready(game):
    town = home_town(game)
    renowned(game, town)
    game.world.update_data(game.player.id, realm="second-rate", silver=500)
    for name in ("Lu An", "Lu Bo", "Lu Chen"):
        game.world.update_data(friend(game, town, name), sworn_to=game.player.id)
    return town


def test_friends_can_be_asked_to_follow(game, monkeypatch):
    monkeypatch.setattr(founding, "follow_chance", lambda *args, **kwargs: 1.0)
    town = home_town(game)
    npc = friend(game, town, "Lu An")
    assert founding.can_ask_to_follow(game.world, npc, game.player.id)
    turn = game.perform(Action("talk", npc))
    assert Action("ask_follow", npc) in [c.action for c in turn.all_choices]
    game.perform(Action("ask_follow", npc))
    assert founding.followers(game.world, game.player.id) == [npc]
    assert not founding.can_ask_to_follow(game.world, npc, game.player.id)


def test_founding_is_refused_step_by_step(game):
    town = home_town(game)
    me = game.player.id
    assert founding.found_block(game.world, me, town) == "You must be renowned in this town."
    renowned(game, town)
    assert founding.found_block(game.world, me, town) == "You must be at least Second-rate."
    game.world.update_data(me, realm="second-rate")
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    game.world.relate(me, sect, "member_of", 0, {"role": "member", "status": "member", "secret": False})
    assert founding.found_block(game.world, me, town) == "You must leave your martial faction first."
    game.world.unrelate(me, "member_of", sect)
    assert founding.found_block(game.world, me, town) == "You need 3 sworn followers."
    for name in ("Lu An", "Lu Bo", "Lu Chen"):
        game.world.update_data(friend(game, town, name), sworn_to=me)
    game.world.update_data(me, silver=10)
    assert founding.found_block(game.world, me, town) == "The charter costs 200 silver."
    game.world.update_data(me, silver=500)
    assert founding.found_block(game.world, me, town) is None
    elsewhere = next(t.id for t in game.world.entities("town") if t.id != town)
    assert founding.found_block(game.world, me, elsewhere) == "You must own land here."


def test_founding_through_the_menus(game):
    town = ready(game)
    game.perform(Action("talk", land.magistrate_of(game.world, town)))
    game.perform(Action("found_menu"))
    name = founding.name_suggestions(game.world, game.player.id)[0]
    for action in (Action("found_name", name), Action("found_path", "righteous"),
                   Action("found_taboo", "never_rob"), Action("found_taboo", "never_kill_unarmed"),
                   Action("found_trial", "spar"), Action("found_ranks", "clan")):
        turn = game.perform(action)
    assert any(c.action.verb == "found_confirm" for c in turn.choices)
    turn = game.perform(Action("found_confirm"))
    sect = founding.my_sect(game.world, game.player.id)
    data = game.world.entity(sect).data
    assert game.world.entity(sect).name == name and data["type"] == "player_sect" and data["seat"] == town
    assert data["taboos"] == ["never_rob", "never_kill_unarmed"] and data["ranks"][0] == "retainer"
    assert F.membership(game.world, game.player.id, sect)[0] == 4
    members = [p for p in F.members_of(game.world, sect) if p != game.player.id]
    assert len(members) == 3 and all(game.world.entity(p).data["loyalty"] == 60 for p in members)
    assert all(game.world.targets(p, "located_in") == [town] for p in members)
    assert sect in halls.halls_here(game.world, town) and sect not in halls.recruits_for(game.world, members[0])
    assert game.world.facts(predicate="founded")[0].object == sect
    sect_orthodox = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    assert F.stance(game.world, sect, sect_orthodox) == 0.6
    assert any(name in text for text, _ in turn.lines)
    from debug.invariants import check_factions
    assert check_factions(game.world) == []  # the founder's rank 4 is the one rank above a member's 3
