from collections import Counter

import pytest

from engine.game import Action, Game
from systems import factions as F
from systems.creation import CreationChoice
from world.db import World
from world.events import Event, commit
from world.gen.materialize import ensure_region, region_of


@pytest.fixture
def world(tmp_path):
    w = World.create(tmp_path / "w.world", 11)
    yield w
    w.close()


def test_every_world_has_ten_great_factions(world):
    ids = F.ensure_roster(world)
    kinds = Counter(world.entity(i).data["type"] for i in ids)
    assert kinds == Counter({"orthodox_sect": 3, "demonic_cult": 1, "unorthodox_clan": 1, "martial_clan": 1,
                             "beggars": 1, "merchant_guild": 1, "imperial": 1, "alliance": 1})
    names = [world.entity(i).name for i in ids]
    assert len(set(names)) == 10
    assert F.ensure_roster(world) == ids


def test_the_roster_is_seeded(tmp_path):
    rosters = []
    for n in range(2):
        w = World.create(tmp_path / f"r{n}.world", 42)
        rosters.append([(w.entity(i).name, tuple(w.entity(i).data["home"])) for i in F.ensure_roster(w)])
        w.close()
    assert rosters[0] == rosters[1]


def test_a_sect_is_near_the_start_and_the_capital_powers_share_a_home(world):
    factions = [world.entity(i) for i in F.ensure_roster(world)]
    first_sect = next(f for f in factions if f.data["type"] == "orthodox_sect")
    assert F.gap(first_sect.data["home"], (0, 0)) <= 2
    capital = {tuple(f.data["home"]) for f in factions if f.data["type"] in ("beggars", "merchant_guild", "imperial", "alliance")}
    assert len(capital) == 1 and F.gap(next(iter(capital)), (0, 0)) <= 3
    assert all(F.gap(f.data["home"], (0, 0)) <= 6 for f in factions)
    assert first_sect.data["ranks"][0] == "outer disciple" and first_sect.data["path"] == "righteous"


def test_stances_are_symmetric_and_follow_the_old_feuds(world):
    ids = F.ensure_roster(world)
    by_type = {}
    for i in ids:
        by_type.setdefault(world.entity(i).data["type"], []).append(i)
    sect, cult = by_type["orthodox_sect"][0], by_type["demonic_cult"][0]
    assert F.stance(world, sect, cult) == F.stance(world, cult, sect) == -0.8
    assert F.stance(world, sect, by_type["orthodox_sect"][1]) == 0.6
    assert F.stance(world, sect, by_type["alliance"][0]) == 0.8
    assert F.stance(world, by_type["imperial"][0], cult) == -0.6
    assert F.stance(world, sect, by_type["beggars"][0]) == 0.0
    assert F.stance(world, sect, sect) == 1.0


def test_minor_factions_are_seeded_per_region(world):
    F.ensure_roster(world)
    seen = []
    for x in range(-3, 4):
        region = world.entity(ensure_region(world, x, 0))
        minors = F.minor_factions(world, region)
        assert len(minors) <= 2 and F.minor_factions(world, world.entity(region.id)) == minors
        for fid in minors:
            data = world.entity(fid).data
            assert data["tier"] == "minor" and data["type"] in ("school", "bandit_fort", "local_clan")
            assert region_of(world, data["seat"]).id == region.id
            seen.append(fid)
    assert seen
    forts = [f for f in seen if world.entity(f).data["type"] == "bandit_fort"]
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    for fort in forts:
        assert F.stance(world, fort, sect) == -0.5


def test_a_new_game_has_its_roster_and_a_bandit_backing_off_reads_in_the_journal(tmp_path):
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    game.start()
    assert len(game.world.get_meta("roster")) == 10
    bandit = game.world.add_entity("person", "Ma Bo", {"occupation": "bandit", "realm": "mortal"})
    commit(game.world, [Event("encounter_resolved", (game.player.id, bandit), game.place.id,
                              {"how": "backed_off", "kind": "bandit"})])
    assert any("Ma Bo" in text for text, _ in game.perform(Action("journal")).lines)
    game.close()
