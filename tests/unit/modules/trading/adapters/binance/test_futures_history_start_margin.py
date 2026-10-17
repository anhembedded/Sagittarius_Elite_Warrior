"""`BUG-223` - a Futures read of a run that began a moment ago, and a refused read that says which.

@details The start of a read is the run's start on the exchange's clock, which is the machine's
plus a one-off estimate; a start ahead of the exchange's clock is refused (-4181), so the start
sent keeps a margin under "now" and the rows before the start asked for are dropped. A refused
read names the endpoint and the window it sent. The reader is the real one over a `Mock` client.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_window import (
    START_MARGIN_MS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)

from .test_history_readers import _NOW, _api_error, _futures


@pytest.mark.parametrize(
    ("call", "read", "endpoint"),
    [
        (
            "futures_get_all_orders",
            lambda reader, since: reader.order_history("BTCUSDT", since),
            "GET /fapi/v1/allOrders",
        ),
        (
            "futures_get_all_algo_orders",
            lambda reader, since: reader.order_history("BTCUSDT", since),
            "GET /fapi/v1/allAlgoOrders",
        ),
        (
            "futures_account_trades",
            lambda reader, since: reader.trade_history("BTCUSDT", since),
            "GET /fapi/v1/userTrades",
        ),
    ],
)
def test_a_refused_futures_read_names_the_endpoint_and_the_window_it_sent(
    call: str, read: Any, endpoint: str
) -> None:
    """`BUG-223` - the owner's log said "order history could not be read" and nothing of which of
    the calls behind it the exchange refused, or for what window."""
    client = Mock()
    client.futures_get_all_orders.return_value = []
    client.futures_get_all_algo_orders.return_value = []
    getattr(client, call).side_effect = _api_error()
    since = _NOW - timedelta(hours=1)

    with pytest.raises(AccountHistoryUnavailableError) as raised:
        read(_futures(client), since)

    start = int(since.timestamp() * 1000)
    assert endpoint in str(raised.value)
    assert f"startTime={start}" in str(raised.value)


def _trade_row(trade_id: int, time_ms: int) -> dict[str, Any]:
    return {
        "symbol": "BTCUSDT",
        "id": trade_id,
        "orderId": 7,
        "side": "BUY",
        "price": "40000",
        "qty": "0.1",
        "quoteQty": "4000",
        "commission": "0.1",
        "commissionAsset": "USDT",
        "time": time_ms,
        "realizedPnl": "0",
    }


def test_a_run_that_began_a_moment_ago_is_read_from_a_margin_before_now() -> None:
    """`BUG-223` - a start ahead of the exchange's clock is refused, so the start sent keeps a
    margin under the estimate of "now"."""
    client = Mock()
    client.futures_get_all_orders.return_value = []
    client.futures_get_all_algo_orders.return_value = []
    now_ms = int(_NOW.timestamp() * 1000)

    _futures(client).order_history("BTCUSDT", _NOW - timedelta(milliseconds=20))

    for call in (client.futures_get_all_orders, client.futures_get_all_algo_orders):
        assert call.call_args.kwargs["startTime"] == now_ms - START_MARGIN_MS


def test_the_rows_before_the_start_asked_for_are_dropped() -> None:
    client = Mock()
    since = _NOW - timedelta(milliseconds=20)
    since_ms = int(since.timestamp() * 1000)
    client.futures_get_all_orders.return_value = []
    client.futures_get_all_algo_orders.return_value = []
    client.futures_account_trades.return_value = [
        _trade_row(trade_id=1, time_ms=since_ms - 3_000),
        _trade_row(trade_id=2, time_ms=since_ms + 3_000),
    ]

    fills = _futures(client).trade_history("BTCUSDT", since)

    assert [fill.trade_id for fill in fills] == [2]
