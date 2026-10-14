"""`BOT-176` — the one writer of a plan file, shared by `bot export` and the desktop's Export plan….

A plan is never written over another file: the create is exclusive, so the check and the
write are one step and a file made in between is still refused. The result is a value, not
an exception, so neither caller lets an `OSError` cross its boundary.
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


def write_new_plan_file(path: Path, text: str) -> PlanFileWritten | PlanFileRefused:
    """Write `text` to `path`, which must not exist."""
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text)
    except FileExistsError:
        return PlanFileRefused(path, "exists")
    except OSError as failure:
        return PlanFileRefused(
            path, "os_error", failure.strerror or type(failure).__name__
        )
    return PlanFileWritten(path)
