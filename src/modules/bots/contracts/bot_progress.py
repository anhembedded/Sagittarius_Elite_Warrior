"""`EPIC-029F` — what a bot's run has done so far, as its kind records it.

The Bots tab shows it beside each bot. It is read from the runtime the kind's
executor saves (`StoredBot.runtime`), so it is the bot's own account and never
a safety input (ADR D6): the exchange's evidence is what trading acts on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_pnl import PnlSummary


@dataclass(frozen=True, slots=True)
class BotOrderLine:
    """One order the bot has resting, as its runtime records it: the Bots
    tab's "orders" table, read without asking the exchange."""

    level: int
    #: `"BUY"` or `"SELL"`.
    side: str
    price: Decimal
    quantity: Decimal
    executed: Decimal
    client_order_id: str
    #: The level's state as the runtime recorded it (`RESTING`, `PARTIAL`, ...); empty when
    #: the reader of the record does not carry one. A record, not what the exchange says.
    state: str = ""


@dataclass(frozen=True, slots=True)
class BotProgress:
    """One run's account: profit booked, cycles, what rests and what is held.

    `reason` names why the bot halted, stopped or exited, empty when nothing
    did; the UI shows it beside the state."""

    realised_profit: Decimal
    completed_cycles: int
    open_orders: int
    inventory: Decimal
    average_cost: Decimal | None
    reason: str
    reason_detail: str
    #: The orders resting now, lowest level first.
    orders: tuple[BotOrderLine, ...] = ()
    #: The last price the bot heard (`EPIC-035M`); `None` before it heard one.
    mark_price: Decimal | None = None
    #: `BUG-196` — base earlier runs left that this run does not trade, and its cost.
    earlier_runs_base: Decimal = Decimal(0)
    earlier_runs_cost: Decimal = Decimal(0)
    #: What the held `inventory` cost, as the run's record has it (`BOT-174`).
    cost: Decimal = Decimal(0)
    #: What the run has earned: the total, its parts and the HODL benchmark.
    pnl: PnlSummary | None = None
    #: When the bot heard `mark_price` (its own clock); `None` before it heard one, and for a
    #: record an earlier build wrote (`BOT-193`).
    mark_price_at: datetime | None = None
    #: `BOT-194` - the maker rate the run's start recorded; `None` when the record holds none.
    maker_fee: Decimal | None = None
