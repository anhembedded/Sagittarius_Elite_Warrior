"""`EPIC-029B`, `EPIC-034H` — "start this bot" (from DRAFT or STOPPED)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StartBotCommand:
    """The bot to start.

    `config` is **Save and Start** (decision D8): the parameters on screen,
    saved first when they differ from the saved ones, and only when the bot is
    ready to start with them (a refusal only the runner can give still leaves
    them saved). `None` starts the saved parameters.
    """

    bot_id: str
    config: Mapping[str, str] | None = None
