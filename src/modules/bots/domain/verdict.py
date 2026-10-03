"""`EPIC-029B` — what a bot kind says about the user's parameters (ADR D2).

The user's rule, 2026-10-03: the parameters belong to the user; a bot computes
from them and says whether they are reasonable, it never fixes them to a number.
A `Verdict` is that answer for one check: a severity, a stable code a UI or a
test can key on, a sentence a person can read, and the numbers behind it, so a
warning shows the measured value next to the threshold it crossed.

Only `REFUSED` blocks a start. It is reserved for a certain loss or a certain
rejection by the exchange or by trading (`EPIC-029C` §2); everything the report
only advises against is a `WARNING`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from types import MappingProxyType


class VerdictSeverity(str, Enum):
    """How much one check objects to the parameters."""

    OK = "OK"
    WARNING = "WARNING"
    REFUSED = "REFUSED"


@dataclass(frozen=True, slots=True)
class Verdict:
    """One check's answer about one set of parameters."""

    severity: VerdictSeverity
    code: str
    reason: str
    numbers: Mapping[str, Decimal] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "numbers", MappingProxyType(dict(self.numbers)))

    @property
    def refuses(self) -> bool:
        return self.severity is VerdictSeverity.REFUSED


def any_refused(verdicts: tuple[Verdict, ...]) -> bool:
    """`True` when at least one verdict blocks a start."""
    return any(verdict.refuses for verdict in verdicts)
