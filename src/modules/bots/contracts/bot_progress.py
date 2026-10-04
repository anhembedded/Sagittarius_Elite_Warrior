"""`EPIC-029F` — what a bot's run has done so far, as its kind records it.

The Bots tab shows it beside each bot. It is read from the runtime the kind's
executor saves (`StoredBot.runtime`), so it is the bot's own account and never
a safety input (ADR D6): the exchange's evidence is what trading acts on.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


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
