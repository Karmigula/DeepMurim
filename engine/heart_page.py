"""The heart page (phase 5e spec 8-9): the dao heart in words, its demons, daos, oaths, and a blade's spirit."""

import systems.blade_spirits as BS
import systems.daos as DA
import systems.demons as D
import systems.heart as HT
import systems.oaths as O

WEIGHT_WORDS = {1: "light", 2: "heavy", 3: "crushing"}
DAO_WORDS = ((1.0, "whole: you have returned to the origin"), (0.75, "profound"), (0.5, "deep"), (0.25, "grasped"),
             (0.0, "glimpsed"))


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _name(world, whom) -> str:
    entity = world.entity(whom) if isinstance(whom, int) else None
    return entity.name if entity is not None else "someone"


def demon_words(world, demon: dict) -> str:
    kind, whom = demon["kind"], demon["whom"]
    if kind == "fear":
        return "the fear of death"
    if kind == "guilt":
        return f"guilt over {_name(world, whom)}" if whom is not None else "guilt over an oath broken"
    return f"a grudge against {_name(world, whom)}" if kind == "grudge" else f"grief for {_name(world, whom)}"


def dao_name(name: str) -> str:
    if name in ("yin", "yang"):
        return f"the Dao of {name.capitalize()}"
    if name in DA.FORMS:
        return f"the Dao of the {name.capitalize()}"
    return f"the Dao of {name.capitalize()}"


def dao_words(value: float) -> str:
    return next(word for bound, word in DAO_WORDS if value >= bound)


def oath_words(world, oath: dict) -> str:
    if oath["kind"] == "vengeance":
        return f"vengeance on {_name(world, oath['whom'])}"
    if oath["kind"] == "protection":
        return f"to protect {_name(world, oath['whom'])}"
    return "to kill no one"


def spirit_words(world, player: int, item) -> str | None:
    if not BS.known(world, player, item.id):
        return None
    spirit = BS.spirit_of(world, item.id)
    if spirit.get("cursed"):
        return f"{item.name} is cursed: it thirsts for blood."
    if spirit["nature"] == "bloodthirsty":
        return f"{item.name} holds a bloodthirsty spirit."
    bound = "it knows your hand" if spirit["master"] == player else "it knows another's hand"
    return f"{item.name} holds a loyal spirit: {bound}."


def heart_lines(world, player: int) -> list:
    heart = HT.heart_of(world, player)
    lines = [("Your heart", "heading"),
             (f"  Your dao heart is {HT.steady_words(heart['steady'])}; your way is {HT.lean_words(heart['lean'])}.",
              "dim")]
    demons = sorted(heart["demons"], key=lambda d: (-d["weight"], d["since"]))
    lines.append(("Demons you carry:" if demons else "You carry no heart demons.", "heading"))
    lines += [(f"  {_cap(demon_words(world, d))} ({WEIGHT_WORDS[d['weight']]})", "dim") for d in demons]
    daos = sorted(heart["daos"].items(), key=lambda kv: -kv[1])
    if daos:
        lines.append(("Daos you have glimpsed:", "heading"))
        lines += [(f"  {_cap(dao_name(name))}: {dao_words(value)}", "dim") for name, value in daos]
    if heart["oaths"]:
        lines.append(("Oaths on your heart:", "heading"))
        for oath in heart["oaths"]:
            days = max(1, -(-(oath["until"] - world.time) // 4))
            lines.append((f"  {_cap(oath_words(world, oath))} ({days} day(s) left)", "dim"))
    item = BS.wielded(world, player)
    told = spirit_words(world, player, item) if item is not None else None
    if told:
        lines += [("Your blade:", "heading"), (f"  {told}", "dim")]
    return lines


def rising_lines(world, player: int) -> list:
    demon = D.rising(world, player)
    return [(f"As your qi presses at the gate, {demon_words(world, demon)} rises before you.", "system"),
            ("Will you face it, bury it, or turn back?", "system")]


def sheet_heart_lines(world, player: int) -> list:
    """Nothing for a heart never touched, as 5d's crafts (the sheet fits a 40-row screen)."""
    if world.entity(player).data.get("heart") is None:
        return []
    heart = HT.heart_of(world, player)
    line = f"  Dao heart {HT.steady_words(heart['steady'])}; way {HT.lean_words(heart['lean'])}"
    if heart["daos"]:
        best, value = max(heart["daos"].items(), key=lambda kv: kv[1])
        line += f"; {dao_name(best)} ({dao_words(value).split(':')[0]})"
    return [("", "default"), ("Heart:", "heading"), (line, "default")]


def oath_choices(world, player: int) -> list[tuple[str, str, int | None]]:
    """(label, kind, whom) of the oaths one may swear now: vengeance on a grudge, protection of kin, abstinence."""
    from systems.kin import kin_of
    out = [(f"Swear vengeance on {_name(world, w)}", "vengeance", w) for w in O.grudges(world, player)]
    out += [(f"Swear to protect {_name(world, k)}", "protection", k) for k, _ in kin_of(world, player)]
    out.append(("Swear to kill no one for a season", "abstinence", None))
    return [c for c in out if O.swear_block(world, player, c[1], c[2]) is None]
