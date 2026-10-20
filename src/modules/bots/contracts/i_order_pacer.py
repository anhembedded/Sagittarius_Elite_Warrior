"""`EPIC-029E` — keeps a bot's orders inside the budget's spacing and rate (ADR D6 checks 4 and 5, D21).

Trading refuses a budgeted owner's order sent sooner than `min_order_spacing` after its previous
one (`owner_budget_spacing`), and one that would be more than `max_orders_per_window` inside the
window (`owner_budget_rate`). The bot therefore waits its turn before each order it sends: the
slices of a market order, the levels of a ladder, the counter-orders of a burst of fills. The
clock is injected (`testing-rule.md`: no sleeps in tests); a test's pacer records the waits and
advances a fake clock.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class OrderPacing:
    """How fast a venue's bots may send: the figures of the owner budget they register
    (`grid_pacing`), so a pacer holds the bot to what trading will enforce (`BUG-238`)."""

    #: The shortest gap between two orders.
    spacing: timedelta
    #: Orders inside any `window`; an order past it waits for the window to move on.
    max_orders: int
    window: timedelta


class IOrderPacer(ABC):
    """Blocks until the next order may be sent, then counts it as sent."""

    @abstractmethod
    def wait_turn(self) -> None:
        """Return once the spacing has passed since the last turn and fewer than the rate's
        orders were sent inside its window."""
