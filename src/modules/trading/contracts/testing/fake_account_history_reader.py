"""`FakeAccountHistoryReader` — `IAccountHistoryReader`'s verified fake.

@details Holds the orders and fills a test gives it and answers the way the
port promises: one symbol at a time, from `since` on, oldest first.
`AccountHistoryReaderContract` runs against it, so a consumer test that uses
it cannot pass on an answer the real readers would never give (a row from
another symbol, a row older than `since`, newest-first order, a `since`
further back than `MAX_HISTORY_LOOKBACK`). `now` is required rather than read
from the wall clock, so a test built on fixed dates never starts failing a
month after it was written.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_lookback import (
    require_within_lookback,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)


class FakeAccountHistoryReader(IAccountHistoryReader):
    """The history a test says the account has."""

    def __init__(
        self,
        orders: Iterable[OrderRecord] = (),
        trades: Iterable[TradeRecord] = (),
        open_symbols: Iterable[str] = (),
        *,
        now: datetime,
    ) -> None:
        self._now = now
        self._orders = tuple(orders)
        self._trades = tuple(trades)
        self._active = tuple(
            sorted(
                set(open_symbols)
                | {record.order.symbol for record in self._orders}
                | {record.symbol for record in self._trades}
            )
        )

    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        require_within_lookback(since, self._now)
        rows = (
            record
            for record in self._orders
            if record.order.symbol == symbol and record.created_at >= since
        )
        return tuple(sorted(rows, key=lambda record: record.created_at))

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        require_within_lookback(since, self._now)
        rows = (
            record
            for record in self._trades
            if record.symbol == symbol and record.time >= since
        )
        return tuple(sorted(rows, key=lambda record: (record.time, record.trade_id)))

    def active_symbols(self) -> tuple[str, ...]:
        return self._active
