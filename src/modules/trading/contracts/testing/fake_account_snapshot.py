"""`FakeAccountSnapshot` — `IAccountSnapshot`'s verified fake.

Wraps the same default `FakeTradingAccountReader` uses, for the same reason:
an unconfigured fake reports **not reachable**, so a test that forgot to seed
fails rather than passing against a venue that was never asked.
"""

from __future__ import annotations

from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_UNCONFIGURED = ExchangeConnectionStatus(
    venue=TradingVenue.DISABLED,
    reachable=False,
    failure=ConnectionFailureKind.NOT_CONFIGURED,
    server_time_skew_ms=None,
    usdt_balance=None,
    position_mode=None,
    margin_type=None,
    open_position_count=None,
)


class FakeAccountSnapshot(IAccountSnapshot):
    """The account state a test says the venue reports."""

    def __init__(
        self,
        status: ExchangeConnectionStatus = _UNCONFIGURED,
        positions: Iterable[LivePosition] = (),
    ) -> None:
        self._status = status
        self._positions = tuple(positions)
        self._positions_error: Exception | None = None
        #: Both are network round trips on the real adapter, so a caller doing
        #: either per candle is a defect a test should be able to see.
        self.connection_checks = 0
        self.position_reads = 0
        #: The priority each `open_positions` read named (`BOT-226`).
        self.position_priorities: list[RequestPriority] = []

    def answer_with(self, status: ExchangeConnectionStatus) -> None:
        self._status = status

    def holding(self, positions: Iterable[LivePosition]) -> None:
        """Replaces the open-position set. Replaces rather than appends: the
        real read is a fresh account snapshot, so a position the venue closed
        stops being reported."""
        self._positions = tuple(positions)

    def check_connection(self) -> ExchangeConnectionStatus:
        self.connection_checks += 1
        return self._status

    def positions_raise(self, error: Exception | None) -> None:
        """From now on the position read raises `error` (the venue did not answer);
        `None` lets it answer again. The real adapter answers empty instead, so this is
        for a caller that must not trust either."""
        self._positions_error = error

    def open_positions(
        self, priority: RequestPriority = RequestPriority.ROUTINE
    ) -> tuple[LivePosition, ...]:
        self.position_reads += 1
        self.position_priorities.append(priority)
        if self._positions_error is not None:
            raise self._positions_error
        return self._positions
