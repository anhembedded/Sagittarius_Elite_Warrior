"""`EPIC-029B` — "stop this bot", keeping or selling its base asset (ADR O3)."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)


@dataclass(frozen=True, slots=True)
class StopBotCommand:
    """The bot to stop, and what to do with the base it holds.

    The dialog asks every time with the last choice preselected (ADR O3). The
    choice travels to the executor in `EPIC-029E`; here it is carried so the
    command's shape does not change when it does.
    """

    bot_id: str
    base: BaseHandling
