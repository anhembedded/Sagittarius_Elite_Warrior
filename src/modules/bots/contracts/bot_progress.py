"""`EPIC-029F` — what a bot's run has done so far, as its kind records it.

The Bots tab shows it beside each bot. It is read from the runtime the kind's
executor saves (`StoredBot.runtime`), so it is the bot's own account and never
a safety input (ADR D6): the exchange's evidence is what trading acts on.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    #: What the run has earned: the total, its parts and the HODL benchmark.
    pnl: PnlSummary | None = None
