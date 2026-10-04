"""`EPIC-029F` — one bot's fills, as the venue's order history records them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


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

    `truncated` says the history held more pages than one read scans."""

    fills: tuple[BotFill, ...] = ()
    problem: str = ""
    truncated: bool = False
