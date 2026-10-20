"""`BUG-238` - one virtual clock for the order pacer and for trading's rate window.

@details A journey about pacing cannot wait the minutes the pacer waits (`testing-rule.md`: no
sleeps). The production pacer takes its clock and sleep from here, so a wait advances the time;
trading reads `datetime.now(UTC)` at the moment it judges an order, so the journey gives it the
same time in place of the machine's.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.monotonic_order_pacer import (
    MonotonicOrderPacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
    OrderPacing,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order import (
    handler,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: Virtual seconds before which trading stamps late: the burst of the first 60 orders takes about
#: 15 s, and the next order waits for the window, so no two consecutive orders straddle it.
LAGGED_UNTIL = 30.0
EPOCH = datetime(2026, 10, 20, 6, 26, 17, tzinfo=UTC)


class VirtualTime:
    """One clock for the pacer and for trading's rate window; a sleep moves it."""

    def __init__(self, early_stamp_lag: float = 0.0) -> None:
        self.seconds = 0.0
        #: How much later than the pacer's turn trading stamps each of the first orders it
        #: judges (a cold terms read, the handler's lock): the later ones are stamped on the turn.
        #: The lag drops only where the pacer waits for the window, so the spacing between two
        #: consecutive orders is never shortened by it.
        self._early_stamp_lag = early_stamp_lag

    def monotonic(self) -> float:
        return self.seconds

    def sleep(self, seconds: float) -> None:
        self.seconds += seconds

    def now(self) -> datetime:
        lag = self._early_stamp_lag if self.seconds < LAGGED_UNTIL else 0.0
        return EPOCH + timedelta(seconds=self.seconds + lag)


def trading_reads(monkeypatch: pytest.MonkeyPatch, time: VirtualTime) -> None:
    """Trading judges every order at `time`'s moment instead of the machine's."""

    class _VirtualDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def,override]
            return time.now()

    monkeypatch.setattr(handler, "datetime", _VirtualDatetime)


def pacers_on(
    time: VirtualTime,
) -> Callable[[TradingVenue, OrderPacing], IOrderPacer]:
    """The production pacer, one per venue and pacing, on the virtual clock."""
    built: dict[tuple[TradingVenue, OrderPacing], IOrderPacer] = {}

    def of(venue: TradingVenue, pacing: OrderPacing) -> IOrderPacer:
        if (venue, pacing) not in built:
            built[(venue, pacing)] = MonotonicOrderPacer(
                pacing, clock=time.monotonic, sleep=time.sleep
            )
        return built[(venue, pacing)]

    return of
