"""`EPIC-028E` — `GetAverageEntryPriceQueryHandler` checks the addressed
venue's holding against its fills, and answers only when the fills explain
it (closing `EPIC-027` ADR O6).

@details Both ports are their verified fakes: the holding comes from
`FakeTradingAccountReader`'s connection status, the fills from
`FakeAccountHistoryReader`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_average_entry_price import (
    GetAverageEntryPriceQuery,
    GetAverageEntryPriceQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_SPOT = TradingVenue.SPOT_TESTNET
_FUTURES = TradingVenue.FUTURES_TESTNET
_SINCE = datetime(2026, 9, 23, tzinfo=UTC)
_DUST = Decimal("0.00000001")


def _buy(hours: int, qty: str, price: str) -> TradeRecord:
    return TradeRecord(
        symbol="BTCUSDT",
        trade_id=hours,
        order_id=hours,
        side=OrderSide.BUY,
        price=Decimal(price),
        quantity=Decimal(qty),
        quote_quantity=Decimal(qty) * Decimal(price),
        fee=Decimal(0),
        fee_asset="BTC",
        time=_SINCE + timedelta(hours=hours),
    )


def _status(
    venue: TradingVenue, holdings: tuple[SpotHolding, ...] | None
) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=venue,
        reachable=True,
        failure=None,
        server_time_skew_ms=0,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
        holdings=holdings,
    )


def _btc(total: str) -> SpotHolding:
    return SpotHolding(
        asset="BTC", free=Decimal(total), locked=Decimal(0), dust_threshold=_DUST
    )


def _handler(
    venue: TradingVenue,
    holdings: tuple[SpotHolding, ...] | None,
    fills: list[TradeRecord],
) -> GetAverageEntryPriceQueryHandler:
    context = replace(
        fake_venue_context(
            venue, account_reader=FakeTradingAccountReader(_status(venue, holdings))
        ),
        history_reader=FakeAccountHistoryReader(trades=fills),
    )
    return GetAverageEntryPriceQueryHandler(FakeVenueContexts(context))


def _query(venue: TradingVenue = _SPOT) -> GetAverageEntryPriceQuery:
    return GetAverageEntryPriceQuery(venue=venue, symbol="BTCUSDT", since=_SINCE)


def test_fills_that_explain_the_holding_give_its_average_cost() -> None:
    handler = _handler(
        _SPOT, (_btc("2"),), [_buy(1, "1", "50000"), _buy(2, "1", "70000")]
    )

    answer = handler.execute(_query())

    assert answer is not None
    assert answer.price == Decimal(60000)
    assert answer.quantity == Decimal(2)


def test_a_holding_older_than_the_fills_gives_no_price() -> None:
    handler = _handler(_SPOT, (_btc("5"),), [_buy(1, "1", "50000")])

    assert handler.execute(_query()) is None


def test_no_holding_of_the_base_asset_gives_no_price() -> None:
    handler = _handler(_SPOT, (), [_buy(1, "1", "50000")])

    assert handler.execute(_query()) is None


def test_a_dust_holding_gives_no_price() -> None:
    """Even when a fill explains it exactly: dust is not a position."""
    handler = _handler(_SPOT, (_btc("0.00000001"),), [_buy(1, "0.00000001", "50000")])

    assert handler.execute(_query()) is None


def test_a_futures_venue_has_no_holdings_and_so_no_price() -> None:
    handler = _handler(_FUTURES, None, [_buy(1, "1", "50000")])

    assert handler.execute(_query(_FUTURES)) is None


@pytest.mark.parametrize("symbol", ["BTCBUSD", "USDT", "BTC"])
def test_a_pair_not_quoted_in_usdt_is_refused(symbol: str) -> None:
    with pytest.raises(ValueError, match="USDT"):
        GetAverageEntryPriceQuery(venue=_SPOT, symbol=symbol, since=_SINCE)


def test_a_naive_since_is_refused() -> None:
    with pytest.raises(ValueError, match="timezone"):
        GetAverageEntryPriceQuery(
            venue=_SPOT, symbol="BTCUSDT", since=_SINCE.replace(tzinfo=None)
        )
