"""`EPIC-029B` — "change this bot's parameters" (DRAFT or STOPPED only)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EditBotCommand:
    """The bot's new name and parameters. Kind, venue and symbol stay as created."""

    bot_id: str
    name: str
    config: Mapping[str, str] = field(default_factory=dict)
