"""`EPIC-029B` — "stop this bot", keeping or selling its base asset (ADR O3)."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)


@dataclass(frozen=True, slots=True)
class StopBotCommand:
    """The bot to stop, and what to do with the base it holds.

    The dialog asks every time with the last choice preselected (ADR O3). The
    choice travels to the executor in `EPIC-029E`; here it is carried so the
    command's shape does not change when it does.

    `BUG-274`: a person's Stop (the Bots screen's) carries the answer to the real-money question,
    as Resume does (a testnet is never asked), and only such a Stop opens the venue's order session
    when it is closed: the stop's cancels and its exit are refused while it is. An automated Stop
    (the loss cap, the host's shutdown policy, the operator's after its own opening) carries none
    and opens nothing, so a late order cannot undo an Emergency Stop.
    """

    bot_id: str
    base: ExposureHandling
    real_money_confirmed: bool = False
