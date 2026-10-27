"""`EPIC-048B` — "write the plan of these bots to a new file"."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ExportBotPlanToFileCommand:
    """The new file, the bots (every bot when `bot_ids` is empty) and whether each is
    written as stopped, as `ExportBotPlanQuery` takes them."""

    path: Path
    bot_ids: tuple[str, ...] = ()
    all_stopped: bool = False
