"""`EPIC-029F` — one bot's fills, as the venue's order history records them.

Moved to `contracts/` by `EPIC-047H`: the host publishes it (`BotFillsRead`), and `operations` may import a
module's contracts and not its application. `application/queries/get_bot_fills/result.py` re-exports it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)


@dataclass(frozen=True, slots=True)
class BotFill:
    """One of the bot's orders that executed, fully or in part."""

    time: datetime
    #: `"BUY"` or `"SELL"`.
    side: str
    #: The average price it executed at, as the venue reports it; `None`
    #: when the venue reported none, never a guess.
    price: Decimal | None
    quantity: Decimal
    client_order_id: str


@dataclass(frozen=True, slots=True)
class BotFills:
    """The fills, newest first, or the problem that kept them from being read.

    `truncated` says the history held more pages than one read scans.
    `refused` is the venue's refusal of the read (a refused key, a skewed clock)
    when that is why there are no fills: the cause the Connect step reports, which
    the screen tells once, there, and never as a failure of the fills (`BUG-181`)."""

    fills: tuple[BotFill, ...] = ()
    problem: str = ""
    truncated: bool = False
    refused: ConnectFailure | None = None
