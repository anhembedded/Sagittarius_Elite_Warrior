"""`BOT-176` — what writing a plan file answers: the path written, or why nothing was.

The result is a value, not an exception, so no caller lets an `OSError` cross its boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class PlanFileWritten:
    path: Path


@dataclass(frozen=True, slots=True)
class PlanFileRefused:
    """`exists`: a file is already there, untouched. `os_error`: the OS refused,
    and `detail` is its own message."""

    path: Path
    reason: Literal["exists", "os_error"]
    detail: str = ""
