"""What an AI may *suggest*. Nothing here writes state; the engine validates first.

Phase 1 only defines the shapes so phase 6 plugs in without reshaping the engine.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol

ProposalKind = Literal["prose", "dialogue", "npc", "rumor", "action"]


@dataclass(frozen=True)
class Proposal:
    kind: ProposalKind
    payload: dict = field(default_factory=dict)
    source: str = "claude"


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    reason: str = ""


class Validator(Protocol):
    def validate(self, world, proposal: Proposal) -> Verdict: ...


class RejectAll:
    """The phase 1 validator: nothing from outside the engine is trusted yet."""

    def validate(self, world, proposal: Proposal) -> Verdict:
        return Verdict(False, f"No validator for {proposal.kind} proposals yet")
