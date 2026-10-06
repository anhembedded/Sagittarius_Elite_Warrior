"""The contract suite for `IAccountHistoryReader` (HLD §10.3).

Three guarantees, each one a consumer depends on:

1. **one symbol.** A history asked for `BTCUSDT` holds no `ETHUSDT` row: the
   desk's "hide other pairs" filter and the Spot average entry price both
   read one symbol and would mix two otherwise;
2. **from `since` on, oldest first.** Paging newest-first
   (`GetOrderHistoryQuery`) and the average-cost walk
   (`average_entry_price`) both rely on the order and the lower bound;
3. **active symbols are sorted and name every symbol with a fill from
   `since` on,** so "every pair" never silently leaves out a pair the reader
   itself returned fills for. A pair with only unfilled orders may be
   missing; a real venue says so in `known_gaps()` (`EPIC-028Q`);
4. **at most `MAX_HISTORY_LOOKBACK` back.** A `since` further back is refused
   with `ValueError`; one exactly at the bound is read. A consumer test must
   not pass on a span the real readers refuse.

**One hook.** A subclass supplies `given_history`, because the fake is told
directly and a real reader is told by the exchange. The reader it returns
reads its clock as `CONTRACT_NOW`. The real readers are
exercised against the fake exchange server in `tests/integration/`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.active_symbol import (
    ActiveReason,
    ActiveSymbol,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    MAX_HISTORY_LOOKBACK,
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

#: Puts orders and fills where the implementation reads them, and returns the
#: reader to ask.
type GivenHistory = Callable[
    [Sequence[OrderRecord], Sequence[TradeRecord]], IAccountHistoryReader
]

_START = datetime(2026, 9, 20, tzinfo=UTC)
#: The moment a reader under contract takes as now: a week after the start.
CONTRACT_NOW = _START + timedelta(days=7)


def contract_order(symbol: str, hours: int) -> OrderRecord:
    """An order on `symbol` created `hours` after the suite's start."""
    return OrderRecord(
        order=Order(
            client_order_id=ClientOrderId(f"SEW-{symbol.lower()}{hours:04d}"),
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal(1),
            status=OrderStatus.FILLED,
        ),
        executed_quantity=Decimal(1),
        average_price=Decimal(100),
        created_at=_START + timedelta(hours=hours),
        exchange_order_id=hours,
    )


def contract_trade(symbol: str, hours: int) -> TradeRecord:
    """A fill on `symbol` `hours` after the suite's start."""
    return TradeRecord(
        symbol=symbol,
        trade_id=hours,
        order_id=hours,
        side=OrderSide.BUY,
        price=Decimal(100),
        quantity=Decimal(1),
        quote_quantity=Decimal(100),
        fee=Decimal("0.001"),
        fee_asset="BTC",
        time=_START + timedelta(hours=hours),
    )


class AccountHistoryReaderContract:
    """Inherit this and provide `given_history`. Both readers must pass it."""

    @pytest.fixture
    def given_history(self) -> GivenHistory:
        raise NotImplementedError(
            "an AccountHistoryReaderContract subclass must provide a "
            "`given_history` fixture"
        )

    def test_order_history_holds_only_the_asked_symbol(
        self, given_history: GivenHistory
    ) -> None:
        reader = given_history(
            [contract_order("BTCUSDT", 1), contract_order("ETHUSDT", 2)], []
        )

        rows = reader.order_history("BTCUSDT", _START)

        assert [row.order.symbol for row in rows] == ["BTCUSDT"]

    def test_order_history_starts_at_since_oldest_first(
        self, given_history: GivenHistory
    ) -> None:
        reader = given_history(
            [
                contract_order("BTCUSDT", 30),
                contract_order("BTCUSDT", 1),
                contract_order("BTCUSDT", 10),
            ],
            [],
        )

        rows = reader.order_history("BTCUSDT", _START + timedelta(hours=5))

        assert [row.created_at for row in rows] == [
            _START + timedelta(hours=10),
            _START + timedelta(hours=30),
        ]

    def test_trade_history_holds_only_the_asked_symbol_from_since_oldest_first(
        self, given_history: GivenHistory
    ) -> None:
        reader = given_history(
            [],
            [
                contract_trade("BTCUSDT", 20),
                contract_trade("ETHUSDT", 15),
                contract_trade("BTCUSDT", 2),
                contract_trade("BTCUSDT", 12),
            ],
        )

        rows = reader.trade_history("BTCUSDT", _START + timedelta(hours=5))

        assert [(row.symbol, row.trade_id) for row in rows] == [
            ("BTCUSDT", 12),
            ("BTCUSDT", 20),
        ]

    def test_active_symbols_are_sorted_once_each_and_cover_the_fills_since(
        self, given_history: GivenHistory
    ) -> None:
        reader = given_history(
            [contract_order("SOLUSDT", 1)],
            [
                contract_trade("ETHUSDT", 30),
                contract_trade("BTCUSDT", 10),
                contract_trade("BTCUSDT", 12),
            ],
        )

        active = reader.active_symbols(_START + timedelta(hours=5))

        symbols = [pair.symbol for pair in active]
        assert symbols == sorted(set(symbols))
        assert {"BTCUSDT", "ETHUSDT"} <= set(symbols)

    def test_active_symbols_state_why_each_pair_is_active(
        self, given_history: GivenHistory
    ) -> None:
        """`BOT-149`: the reason is the venue's fact, so a pair known only
        from a fill since `since` is `TRADED`; the order a capped page reads
        them in is the application's policy, so no order but the symbol's is
        promised."""
        reader = given_history([], [contract_trade("BTCUSDT", 10)])

        active = reader.active_symbols(_START + timedelta(hours=5))

        assert active == (ActiveSymbol("BTCUSDT", ActiveReason.TRADED),)

    def test_the_every_symbol_scan_limit_is_none_or_positive(
        self, given_history: GivenHistory
    ) -> None:
        """`BUG-145`: a limit of zero would read no pair and say nothing."""
        limit = given_history([], []).every_symbol_scan_limit()
        assert limit is None or limit > 0

    def test_active_symbols_refuse_a_since_past_the_lookback(
        self, given_history: GivenHistory
    ) -> None:
        reader = given_history([], [])

        with pytest.raises(ValueError):
            reader.active_symbols(
                CONTRACT_NOW - MAX_HISTORY_LOOKBACK - timedelta(seconds=1)
            )

    def test_a_since_past_the_lookback_is_refused(
        self, given_history: GivenHistory
    ) -> None:
        reader = given_history([], [])
        too_far = CONTRACT_NOW - MAX_HISTORY_LOOKBACK - timedelta(seconds=1)

        with pytest.raises(ValueError):
            reader.order_history("BTCUSDT", too_far)
        with pytest.raises(ValueError):
            reader.trade_history("BTCUSDT", too_far)

    def test_a_since_exactly_at_the_lookback_is_read(
        self, given_history: GivenHistory
    ) -> None:
        reader = given_history(
            [contract_order("BTCUSDT", 1)], [contract_trade("BTCUSDT", 1)]
        )
        oldest = CONTRACT_NOW - MAX_HISTORY_LOOKBACK

        assert len(reader.order_history("BTCUSDT", oldest)) == 1
        assert len(reader.trade_history("BTCUSDT", oldest)) == 1
