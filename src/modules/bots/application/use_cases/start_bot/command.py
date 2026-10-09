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

    `real_money_confirmed` is the answer to the question that names real money
    (`IRealMoneyConsent`), which only a screen can ask: the use case refuses a
    mainnet bot without it (`EPIC-035V`, L6), so a caller that never asked cannot
    start one. A testnet bot needs none.
    """

    bot_id: str
    config: Mapping[str, str] | None = None
    real_money_confirmed: bool = False
