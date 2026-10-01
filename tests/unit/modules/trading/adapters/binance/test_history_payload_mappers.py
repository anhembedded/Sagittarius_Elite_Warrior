"""`EPIC-028E` — Futures and Spot history rows map to `OrderRecord` and
`TradeRecord` exactly as Binance reports them.

@details Payloads follow Binance's documented `allOrders`, `userTrades` and
`myTrades` rows (the same disclosure as the adapters: not re-verified against
a live call).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_payload_mapper import (
    map_futures_history_order,
    map_futures_trade,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_history_payload_mapper import (
    map_spot_history_order,
    map_spot_trade,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)

_T0 = 1_790_000_000_000


def _futures_order(**overrides: object) -> dict:
    row = {
        "orderId": 1,
        "clientOrderId": "web_abc",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "status": "PARTIALLY_FILLED",
        "origQty": "0.010",
        "executedQty": "0.004",
        "avgPrice": "64000.5",
        "price": "64001",
        "stopPrice": "0",
        "timeInForce": "GTC",
        "reduceOnly": False,
        "time": _T0,
        "updateTime": _T0 + 5000,
    }
    row.update(overrides)
    return row


def _spot_order(**overrides: object) -> dict:
    row = {
        "symbol": "ETHUSDT",
        "orderId": 7,
        "clientOrderId": "SEW-a91f4c72e0b8",
        "price": "0.00000000",
        "origQty": "2.00000000",
        "executedQty": "2.00000000",
        "cummulativeQuoteQty": "6001.00000000",
        "status": "FILLED",
        "timeInForce": "GTC",
        "type": "MARKET",
        "side": "BUY",
        "time": _T0,
        "updateTime": _T0,
    }
    row.update(overrides)
    return row


def test_a_futures_order_row_keeps_the_exchanges_own_fill_figures() -> None:
    record = map_futures_history_order(_futures_order())

    assert record.order.client_order_id == "web_abc"
    assert record.order.status is OrderStatus.PARTIALLY_FILLED
    assert record.executed_quantity == Decimal("0.004")
    assert record.average_price == Decimal("64000.5")
    assert record.created_at == datetime.fromtimestamp(_T0 / 1000, tz=UTC)
    assert record.order.order_time == datetime.fromtimestamp(
        (_T0 + 5000) / 1000, tz=UTC
    )


@pytest.mark.parametrize("avg_price", ["0", "0.00000"])
def test_an_unfilled_futures_order_has_no_average_price(avg_price: str) -> None:
    record = map_futures_history_order(
        _futures_order(executedQty="0", avgPrice=avg_price, status="CANCELED")
    )

    assert record.average_price is None
    assert record.order.status is OrderStatus.CANCELED


def test_a_futures_fill_row_carries_its_fee_and_realized_pnl() -> None:
    trade = map_futures_trade(
        {
            "symbol": "BTCUSDT",
            "id": 698759,
            "orderId": 25851813,
            "side": "SELL",
            "price": "7819.01",
            "qty": "0.002",
            "quoteQty": "15.63802",
            "commission": "-0.07819010",
            "commissionAsset": "USDT",
            "realizedPnl": "-0.91539999",
            "time": _T0,
            "buyer": False,
            "maker": False,
        }
    )

    assert trade.side is OrderSide.SELL
    assert trade.quote_quantity == Decimal("15.63802")
    assert trade.fee == Decimal("-0.07819010")
    assert trade.fee_asset == "USDT"
    assert trade.realized_pnl == Decimal("-0.91539999")
    assert trade.trade_id == 698759


def test_a_spot_order_average_is_quote_spent_over_quantity_filled() -> None:
    record = map_spot_history_order(_spot_order())

    assert record.average_price == Decimal("3000.5")
    assert record.executed_quantity == Decimal(2)


def test_an_unfilled_spot_order_has_no_average_price() -> None:
    record = map_spot_history_order(
        _spot_order(executedQty="0.00000000", cummulativeQuoteQty="0.00000000")
    )

    assert record.average_price is None


def test_a_spot_order_whose_quote_spent_is_unavailable_has_no_average() -> None:
    """`EPIC-028Q` — Binance sends a negative `cummulativeQuoteQty` when the
    figure is not available (very old orders); it used to become a negative
    average price."""
    record = map_spot_history_order(_spot_order(cummulativeQuoteQty="-1.00000000"))

    assert record.average_price is None


@pytest.mark.parametrize(
    ("is_buyer", "side"), [(True, OrderSide.BUY), (False, OrderSide.SELL)]
)
def test_a_spot_fill_takes_its_side_from_is_buyer(
    is_buyer: bool, side: OrderSide
) -> None:
    trade = map_spot_trade(
        {
            "symbol": "BNBBTC",
            "id": 28457,
            "orderId": 100234,
            "orderListId": -1,
            "price": "4.00000100",
            "qty": "12.00000000",
            "quoteQty": "48.000012",
            "commission": "10.10000000",
            "commissionAsset": "BNB",
            "time": _T0,
            "isBuyer": is_buyer,
            "isMaker": False,
            "isBestMatch": True,
        }
    )

    assert trade.side is side
    assert trade.fee_asset == "BNB"
    assert trade.realized_pnl is None
