"""`EPIC-029E`, `EPIC-029J` J1b — `IOrderPacer` on the monotonic clock.

The clock and the sleep are injected so a test drives them (`testing-rule.md`:
no sleeps); the composition root takes the defaults, the process's own.

One pacer serves every bot of a venue (`VenueOrderPacers`), and each bot's worker is its own
thread, so a turn is reserved under a lock and waited for outside it: two threads never take
the same instant, and a long wait never holds the others' reservations.

A turn is the later of three instants: now, the spacing after the previous turn, and the window
after the turn `max_orders` places back (`BUG-238`). The third is what trading's
`owner_budget_rate` check enforces, so a ladder longer than the rate is laid at the rate instead
of being refused at its 61st order. A wait for the window blocks the bot's worker, including a
Stop asked meanwhile, for at most one window.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
    OrderPacing,
)

logger = logging.getLogger("App.Bots.OrderPacer")

#: Trading stamps an order when it judges it, a moment after the pacer's turn, and that moment
#: differs from order to order (a terms read, the lock). The window the pacer keeps is this much
#: longer than trading's, so two stamps a window apart by the pacer's clock are still a window
#: apart by trading's.
STAMP_JITTER = timedelta(seconds=2)


class MonotonicOrderPacer(IOrderPacer):
    """Gives each caller the next instant that keeps the venue's orders inside its pacing."""

    def __init__(
        self,
        pacing: OrderPacing,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._spacing = pacing.spacing.total_seconds()
        self._window = (pacing.window + STAMP_JITTER).total_seconds()
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        #: The instants of the last `max_orders` turns, oldest first.
        self._turns: deque[float] = deque(maxlen=pacing.max_orders)
        self._max_orders = pacing.max_orders
        #: Whether the last turn was held for the rate: a streak is logged once, not per order.
        self._held_for_rate = False

    def wait_turn(self) -> None:
        with self._lock:
            now = self._clock()
            turn = now
            if self._turns:
                turn = max(turn, self._turns[-1] + self._spacing)
            by_rate = len(self._turns) == self._max_orders and (
                self._turns[0] + self._window > turn
            )
            if by_rate:
                turn = self._turns[0] + self._window
            self._turns.append(turn)
            self._note_rate_hold(by_rate, turn - now)
        wait = turn - now
        if wait > 0:
            self._sleep(wait)

    def _note_rate_hold(self, by_rate: bool, wait: float) -> None:
        if by_rate and not self._held_for_rate:
            logger.info(
                "Order pacing: the venue's %d orders per window are spent; the next order "
                "waits %.1f s and the orders after it go at the budget's rate [order-pacing]",
                self._max_orders,
                wait,
            )
        elif self._held_for_rate and not by_rate:
            logger.info(
                "Order pacing: the window has room again; orders go at the spacing "
                "[order-pacing]"
            )
        self._held_for_rate = by_rate
