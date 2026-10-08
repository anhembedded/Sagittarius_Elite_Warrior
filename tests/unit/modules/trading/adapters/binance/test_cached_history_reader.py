"""`EPIC-028Q` — `CachedAccountHistoryReader` reads a span from the exchange at
most once per `ttl`, and still keeps every promise of the port.

@details The reader behind the cache is `FakeAccountHistoryReader`, the
port's verified fake, subclassed only to count the reads that reach it; the
fake exchange server counts real requests in
`tests/integration/infrastructure/binance/test_history_readers_against_fake_server.py`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.cached_history_reader import (
    HISTORY_CACHE_TTL,
    CachedAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.active_symbol import (
    ActiveSymbol,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_gaps import (
    HistoryGaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_account_history_reader import (
    CONTRACT_NOW,
    AccountHistoryReaderContract,
    GivenHistory,
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


class _CountingReader(FakeAccountHistoryReader):
    """The verified fake, counting the reads that reach it."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.reads: Counter[str] = Counter()
        self.fail_next = False

    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        self._count("orders")
        return super().order_history(symbol, since)

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        self._count("trades")
        return super().trade_history(symbol, since)

    def active_symbols(self, since: datetime) -> tuple[ActiveSymbol, ...]:
        self._count("symbols")
        return super().active_symbols(since)

    def _count(self, what: str) -> None:
        self.reads[what] += 1
        if self.fail_next:
            self.fail_next = False
            raise AccountHistoryUnavailableError("exchange down")


class TestCachedAccountHistoryReader(AccountHistoryReaderContract):
    @pytest.fixture
    def given_history(self) -> GivenHistory:
        def given(
            orders: Sequence[OrderRecord], trades: Sequence[TradeRecord]
        ) -> IAccountHistoryReader:
            return CachedAccountHistoryReader(
                FakeAccountHistoryReader(orders, trades, now=CONTRACT_NOW),
                clock=lambda: CONTRACT_NOW,
            )

        return given


class _Clock:
    def __init__(self) -> None:
        self.now = CONTRACT_NOW

    def __call__(self) -> datetime:
        return self.now


def _cached(
    inner: _CountingReader | None = None,
) -> tuple[CachedAccountHistoryReader, _CountingReader, _Clock]:
    inner = inner or _CountingReader(
        orders=[contract_order("BTCUSDT", h) for h in (1, 5, 9)],
        trades=[contract_trade("BTCUSDT", h) for h in (2, 6)],
        open_symbols=["ETHUSDT"],
        now=CONTRACT_NOW,
    )
    clock = _Clock()
    return CachedAccountHistoryReader(inner, clock=clock), inner, clock


def test_a_repeated_read_is_answered_without_the_exchange() -> None:
    reader, inner, _ = _cached()

    first = reader.order_history("BTCUSDT", _START)
    again = reader.order_history("BTCUSDT", _START)

    assert again == first
    assert inner.reads["orders"] == 1


def test_a_later_since_is_served_from_the_wider_read_with_older_rows_dropped() -> None:
    """A row exactly at the later `since` is kept, as the port promises."""
    reader, inner, _ = _cached()
    reader.order_history("BTCUSDT", _START)
    reader.trade_history("BTCUSDT", _START)

    orders = reader.order_history("BTCUSDT", _START + timedelta(hours=5))
    trades = reader.trade_history("BTCUSDT", _START + timedelta(hours=6))

    assert [row.created_at - _START for row in orders] == [
        timedelta(hours=5),
        timedelta(hours=9),
    ]
    assert [row.trade_id for row in trades] == [6]
    assert (inner.reads["orders"], inner.reads["trades"]) == (1, 1)


@pytest.mark.parametrize(
    ("kind", "read", "row_hours"),
    [
        ("orders", "order_history", lambda row: row.created_at - _START),
        ("trades", "trade_history", lambda row: row.time - _START),
    ],
)
def test_an_earlier_since_goes_to_the_exchange(
    kind: str, read: str, row_hours: Callable[[object], timedelta]
) -> None:
    """A read further back than the entry is never served from it: the
    entry holds nothing older than its own `since` (the PR #301 review)."""
    reader, inner, _ = _cached()
    getattr(reader, read)("BTCUSDT", _START + timedelta(hours=4))

    rows = getattr(reader, read)("BTCUSDT", _START)

    assert row_hours(rows[0]) < timedelta(hours=4)
    assert inner.reads[kind] == 2


@pytest.mark.parametrize(
    ("elapsed", "reads"),
    [
        (HISTORY_CACHE_TTL - timedelta(microseconds=1), 1),
        (HISTORY_CACHE_TTL, 2),
        (-timedelta(seconds=1), 2),
    ],
    ids=["just-inside-ttl", "at-ttl", "clock-stepped-back"],
)
def test_an_entry_is_reused_only_inside_its_ttl(elapsed: timedelta, reads: int) -> None:
    reader, inner, clock = _cached()
    reader.trade_history("BTCUSDT", _START)

    clock.now = CONTRACT_NOW + elapsed
    reader.trade_history("BTCUSDT", _START)

    assert inner.reads["trades"] == reads


def test_each_symbol_and_each_kind_has_its_own_entry() -> None:
    reader, inner, _ = _cached()

    reader.order_history("BTCUSDT", _START)
    reader.order_history("ETHUSDT", _START)
    reader.trade_history("BTCUSDT", _START)

    assert (inner.reads["orders"], inner.reads["trades"]) == (2, 1)


def test_a_failed_read_is_not_cached() -> None:
    reader, inner, _ = _cached()
    inner.fail_next = True
    with pytest.raises(AccountHistoryUnavailableError):
        reader.order_history("BTCUSDT", _START)

    rows = reader.order_history("BTCUSDT", _START)

    assert len(rows) == 3
    assert inner.reads["orders"] == 2


def test_active_symbols_are_reused_for_the_same_since_only() -> None:
    reader, inner, _ = _cached()

    first = reader.active_symbols(_START)
    reader.active_symbols(_START)
    later = reader.active_symbols(_START + timedelta(hours=4))

    assert [pair.symbol for pair in first] == ["BTCUSDT", "ETHUSDT"]
    assert later == first
    assert inner.reads["symbols"] == 2


def test_a_since_past_the_lookback_is_refused_even_with_an_entry_cached() -> None:
    reader, _, clock = _cached()
    reader.trade_history("BTCUSDT", _START)

    clock.now = _START + timedelta(days=31)
    with pytest.raises(ValueError, match="days back"):
        reader.trade_history("BTCUSDT", _START)


def test_known_gaps_are_the_exchange_readers() -> None:
    gaps = HistoryGaps(order_history=("purged",))
    inner = _CountingReader(now=CONTRACT_NOW, gaps=gaps)

    assert CachedAccountHistoryReader(inner).known_gaps() is gaps


def test_a_discarded_symbol_is_read_from_the_exchange_again() -> None:
    """`EPIC-035B` — a reconciliation must read the account as it is now, not
    as it was up to `ttl` ago: after `discard_remembered` the next read of the
    symbol goes to the exchange and is cached again."""
    reader, inner, _ = _cached()
    reader.order_history("BTCUSDT", _START)
    reader.trade_history("BTCUSDT", _START)

    reader.discard_remembered("BTCUSDT")
    reader.order_history("BTCUSDT", _START)
    reader.trade_history("BTCUSDT", _START)
    reader.order_history("BTCUSDT", _START)
    reader.trade_history("BTCUSDT", _START)

    assert (inner.reads["orders"], inner.reads["trades"]) == (2, 2)


def test_discarding_one_symbol_keeps_the_others_remembered() -> None:
    reader, inner, _ = _cached()
    reader.order_history("BTCUSDT", _START)
    reader.order_history("ETHUSDT", _START)

    reader.discard_remembered("BTCUSDT")
    reader.order_history("ETHUSDT", _START)

    assert inner.reads["orders"] == 2


def test_discarding_what_was_never_read_is_harmless() -> None:
    reader, inner, _ = _cached()

    reader.discard_remembered("BTCUSDT")

    assert inner.reads["orders"] == 0
