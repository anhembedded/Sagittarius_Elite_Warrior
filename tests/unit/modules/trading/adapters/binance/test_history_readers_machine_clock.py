"""`BUG-189` — the history readers speak the machine's clock to their callers
and the exchange's to the exchange.

@details A machine whose clock is not Binance's (the owner's runs fast,
`BUG-111`) used to open every window after the bot's own first orders: the
reader sent `run_started_at` as it was and read back the exchange's own
stamps. The offset the signed session measured when it opened is applied both
ways. The request shapes against a real HTTP round trip are
`tests/integration/modules/bots/test_a_machine_clock_off_the_exchanges_on_the_fake_exchange.py`'s.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import Mock

from .test_history_readers import _NOW, _futures, _spot

#: `BUG-189` — the exchange's clock 90 s behind the machine's (a machine whose
#: clock runs fast), and the same machine's own time for a fill the exchange
#: stamped.
_FAST_MACHINE_MS = -90_000


def _spot_order_row(time_ms: int) -> dict[str, Any]:
    return {
        "symbol": "BTCUSDT",
        "orderId": 7,
        "clientOrderId": "SEW-abc123-0123456789",
        "side": "BUY",
        "type": "MARKET",
        "status": "FILLED",
        "origQty": "1",
        "executedQty": "1",
        "cummulativeQuoteQty": "100",
        "price": "0",
        "time": time_ms,
    }


def _spot_trade_row(time_ms: int) -> dict[str, Any]:
    return {
        "symbol": "BTCUSDT",
        "id": 9,
        "orderId": 7,
        "isBuyer": True,
        "price": "100",
        "qty": "1",
        "quoteQty": "100",
        "commission": "0.001",
        "commissionAsset": "BTC",
        "time": time_ms,
    }


def test_a_spot_read_asks_the_exchange_in_its_own_clock_and_answers_in_the_machines() -> (
    None
):
    """The window the exchange is asked for is the machine's `since`..`now`
    moved onto the exchange's clock, and a row it stamped comes back on the
    machine's, so `run_started_at` and a fill compare without a second clock."""
    on_exchange = int(_NOW.timestamp() * 1000) + _FAST_MACHINE_MS
    client = Mock()
    client.get_all_orders.return_value = [_spot_order_row(on_exchange)]
    client.get_my_trades.return_value = [_spot_trade_row(on_exchange)]
    reader = _spot(client, offset_ms=_FAST_MACHINE_MS)

    [order] = reader.order_history("BTCUSDT", _NOW - timedelta(hours=1))
    [trade] = reader.trade_history("BTCUSDT", _NOW - timedelta(hours=1))

    asked = client.get_all_orders.call_args.kwargs
    assert asked["endTime"] == on_exchange
    assert asked["startTime"] == on_exchange - 3_600_000
    assert order.created_at == _NOW
    assert trade.time == _NOW


def test_a_futures_read_asks_the_exchange_in_its_own_clock_and_answers_in_the_machines() -> (
    None
):
    on_exchange = int(_NOW.timestamp() * 1000) + _FAST_MACHINE_MS
    client = Mock()
    client.futures_get_all_orders.return_value = [
        {
            "symbol": "BTCUSDT",
            "orderId": 7,
            "clientOrderId": "SEW-abc123-0123456789",
            "side": "BUY",
            "type": "MARKET",
            "status": "FILLED",
            "origQty": "1",
            "executedQty": "1",
            "avgPrice": "100",
            "price": "0",
            "time": on_exchange,
        }
    ]
    client.futures_get_all_algo_orders.return_value = []
    client.futures_account_trades.return_value = [
        {
            **_spot_trade_row(on_exchange),
            "side": "BUY",
            "realizedPnl": "0",
        }
    ]
    reader = _futures(client, offset_ms=_FAST_MACHINE_MS)

    [order] = reader.order_history("BTCUSDT", _NOW - timedelta(hours=1))
    [trade] = reader.trade_history("BTCUSDT", _NOW - timedelta(hours=1))

    asked = client.futures_get_all_orders.call_args.kwargs
    assert asked["endTime"] == on_exchange
    assert asked["startTime"] == on_exchange - 3_600_000
    assert order.created_at == _NOW
    assert trade.time == _NOW
