"""What the player can do (Action), how it is offered (Choice), and what comes back (Turn)."""

from dataclasses import dataclass, field

from narrate.base import Line


@dataclass(frozen=True)
class Action:
    verb: str
    target: object = None


@dataclass(frozen=True)
class Choice:
    label: str
    action: Action


@dataclass
class Turn:
    lines: list[Line]
    choices: list[Choice]
    art: dict
    status: str
    extra: list[Choice] = field(default_factory=list)  # valid now but folded off-screen

    @property
    def all_choices(self) -> list[Choice]:
        return self.choices + self.extra
