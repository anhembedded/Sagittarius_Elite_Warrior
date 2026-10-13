"""`EPIC-029E` — what a bot's handlers copy out of trading's events (ADR D9).

A handler runs on the websocket thread. It copies the few facts the bot needs
into one of these frozen values, posts it to the bot's queue and returns; the
bus's event object is never shared with the worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


@dataclass(frozen=True, slots=True)
class BotOrderFill:
    """One fill of one of the bot's orders."""

    client_order_id: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    fee_amount: Decimal | None = None
    fee_asset: str | None = None
    #: `EPIC-035P` — the exchange's id of this fill, `None` where the venue
    #: reports none. With the order id it names the fill, so a report delivered
    #: twice is counted once.
    trade_id: int | None = None
    #: `EPIC-039G` — Futures' realized profit of this trade, quote asset, gross of the
    #: commission; `None` where the report carries none (Spot). Carried for the position
    #: executor (`EPIC-039H`); the Grid's own cycle accounting does not read it.
    realized_profit: Decimal | None = None


@dataclass(frozen=True, slots=True)
class BotFundingCharge:
    """`EPIC-039G` — the exchange settled a funding fee on the bot's symbol; `amount` is
    the wallet's signed change in the quote asset (negative: paid)."""

    symbol: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class BotOrderEnd:
    """One of the bot's orders ended without filling whole; `rejection` is the
    exchange's reason when it refused the order outright."""

    client_order_id: str
    rejection: str | None = None
