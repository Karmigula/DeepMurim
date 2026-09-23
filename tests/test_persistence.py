from engine.game import Action, Game


def talk_choice(turn):
    return next(c for c in turn.all_choices if c.action.verb == "talk")


def test_npc_remembers_across_reload(tmp_path):
    path = tmp_path / "w.world"
    game = Game.new(path, "Tester", world_seed=42)
    choice = talk_choice(game.start())
    npc_name = game.world.entity(choice.action.target).name
    game.perform(choice.action)
    game.perform(Action("farewell"))
    digest = game.world.digest()
    game.close()

    game = Game.load(path)
    assert game.world.digest() == digest
    look = game.start()
    assert any("(knows you)" in text for text, _ in look.lines)
    turn = game.perform(choice.action)
    assert game.world.chronicle_about(game.player.id, limit=1)[0].kind == "conversed"
    assert any(npc_name in text for text, _ in turn.lines)
    game.close()


def test_same_seed_same_world(tmp_path):
    names = []
    for n in range(2):
        game = Game.new(tmp_path / f"{n}.world", "Tester", world_seed=7)
        names.append((game.place.name, [c.label for c in game.start().choices]))
        game.close()
    assert names[0] == names[1]


def test_there_and_back_again(tmp_path):
    game = Game.new(tmp_path / "w.world", "Tester", world_seed=42)
    home = game.place.id
    residents = {c.action.target for c in game.start().all_choices if c.action.verb == "talk"}
    north = next(c for c in game.look().all_choices if "north road" in c.label)
    game.perform(north.action)
    south = next(c for c in game.look().all_choices if "south road" in c.label)
    turn = game.perform(south.action)
    assert game.place.id == home
    assert residents and {c.action.target for c in turn.all_choices if c.action.verb == "talk"} == residents
    game.close()
