"""`EPIC-029E` — keeps a bot's orders the budget's spacing apart (ADR D6 check 4, D21).

Trading refuses a budgeted owner's order sent sooner than `min_order_spacing`
after its previous one. The bot therefore waits its turn before each order it
sends: the slices of a market order, the levels of a ladder. The clock is
injected (`testing-rule.md`: no sleeps in tests); a test's pacer records the
waits and advances a fake clock.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IOrderPacer(ABC):
    """Blocks until the next order may be sent, then counts it as sent."""

    @abstractmethod
    def wait_turn(self) -> None:
        """Return once `min_order_spacing` has passed since the last turn."""
