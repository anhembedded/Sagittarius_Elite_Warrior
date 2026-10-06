"""`BUG-145` — `CachedAccountHistoryReader` joins a read already in flight.

@details A desk reads its histories when it opens and again when trading is
turned on, two seconds later. The first every-pair read was still going, so
the second missed the cache for every pair and asked Binance for the same
spans a second time. A read of the same key that arrives while one is in
flight now waits for it and is answered from its result.

The reader behind the cache is `FakeAccountHistoryReader`, the port's
verified fake, subclassed only to hold its first read open and count reads.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.cached_history_reader import (
    CachedAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.active_symbol import (
    ActiveSymbol,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_account_history_reader import (
    CONTRACT_NOW,
    contract_order,
    contract_trade,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

_START = contract_order("BTCUSDT", 0).created_at
_WAIT_S = 5.0


class _HeldReader(FakeAccountHistoryReader):
    """The verified fake, holding every read open until `release` is set."""

    def __init__(self) -> None:
        super().__init__(
            orders=[contract_order("BTCUSDT", 1)],
            trades=[contract_trade("BTCUSDT", 2)],
            open_symbols=["ETHUSDT"],
            now=CONTRACT_NOW,
        )
        self.reads: Counter[str] = Counter()
        self.entered = threading.Event()
        self.release = threading.Event()

    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        self._hold("orders")
        return super().order_history(symbol, since)

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        self._hold("trades")
        return super().trade_history(symbol, since)

    def active_symbols(self, since: datetime) -> tuple[ActiveSymbol, ...]:
        self._hold("symbols")
        return super().active_symbols(since)

    def _hold(self, what: str) -> None:
        self.reads[what] += 1
        self.entered.set()
        assert self.release.wait(_WAIT_S), "the test never released the read"


def _wait_until(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + _WAIT_S
    while not condition():
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(0.005)


_READS: dict[str, Callable[[CachedAccountHistoryReader], object]] = {
    "orders": lambda reader: reader.order_history("BTCUSDT", _START),
    "trades": lambda reader: reader.trade_history("BTCUSDT", _START),
    "symbols": lambda reader: reader.active_symbols(_START),
}


@pytest.mark.parametrize("what", list(_READS))
def test_a_read_arriving_while_the_same_read_is_in_flight_joins_it(
    what: str, caplog: pytest.LogCaptureFixture
) -> None:
    inner = _HeldReader()
    reader = CachedAccountHistoryReader(inner, clock=lambda: CONTRACT_NOW)
    read = _READS[what]
    answers: list[object] = []

    def run() -> None:
        answers.append(read(reader))

    with caplog.at_level(logging.DEBUG, logger="App.HistoryCache"):
        first = threading.Thread(target=run)
        first.start()
        assert inner.entered.wait(_WAIT_S)
        second = threading.Thread(target=run)
        second.start()
        _wait_until(
            lambda: (
                inner.reads[what] > 1
                or any("in flight" in record.getMessage() for record in caplog.records)
            )
        )
        inner.release.set()
        first.join(_WAIT_S)
        second.join(_WAIT_S)

    assert inner.reads[what] == 1
    assert len(answers) == 2
    assert answers[0] == answers[1]
