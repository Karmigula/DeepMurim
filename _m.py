import gc, time, tempfile
from pathlib import Path
import systems.encounters as e; e.CHALLENGE_CHANCE = e.ENCOUNTER_CHANCE = 0.0
import systems.lives as lives, systems.control as C, systems.npc_alchemy as N
from engine.game import Game
from systems.creation import CreationChoice
from world.gen.npc import OCCUPATIONS, REALMS
g = Game.new(Path(tempfile.mkdtemp()) / "g.world", "H", world_seed=11, creation=CreationChoice("origin", "hunter")); g.start(); w = g.world
people = []
for i in range(200):
    pid = w.add_entity("person", f"C {i}", {"occupation": OCCUPATIONS[i % len(OCCUPATIONS)], "traits": ["curious"], "age": 30,
          "silver": 200, "realm": REALMS[i % len(REALMS)], "portrait": {"hair": 0, "face": 0, "robe": 0}}, f"t:c:{i}")
    w.relate(pid, g.place.id, "located_in"); lives.lived_to(w, pid); people.append(pid)
every = list(lives.AGENDAS); before = [a for a in every if a not in (N.season_events, C.world_events)]
w.set_time(w.time + lives.SEASON)
class Undo(Exception): pass
def season(agendas):
    lives.AGENDAS[:] = agendas
    gc.collect(); s = time.process_time()
    try:
        with w.transaction():
            for p in people:
                lives.catch_up(w, p)
            spent = time.process_time() - s
            raise Undo
    except Undo:
        return spent
t = {"5b": [], "5c": []}
for i in range(12):
    t["5b" if i % 2 == 0 else "5c"].append(season(before if i % 2 == 0 else every))
print({k: [round(x, 3) for x in v] for k, v in t.items()}, "min ratio", round(min(t["5c"]) / min(t["5b"]), 3))
