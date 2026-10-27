"""`EPIC-048B` — what `ExportBotPlanToFileCommand` answers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class PlanFileExported:
    path: Path
    bot_count: int


@dataclass(frozen=True, slots=True)
class PlanFileNotExported:
    """`exists`: a file is already there, untouched. `os_error`: the OS refused, `detail` is its
    message. `unknown_bots`: an id names no stored bot, `detail` says which; nothing was written."""

    path: Path
    reason: Literal["exists", "os_error", "unknown_bots"]
    detail: str = ""


type PlanFileExport = PlanFileExported | PlanFileNotExported
