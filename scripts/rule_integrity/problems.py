"""One finding of one check: where it is and what is wrong there."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Problem:
    """A defect in the rule tree, ordered by check, file and line for a stable report."""

    check: str
    source: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.source}:{self.line}: {self.message}"
