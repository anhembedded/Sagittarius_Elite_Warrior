"""`EPIC-028C` — each market's klines come from that market's own socket.

@details `BinanceSocketManager` is `python-binance`'s, a third-party class
this module adapts; `Mock(spec=...)` records which of its methods was asked
for which streams, which is exactly the decision under test.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from binance import BinanceSocketManager
from binance.enums import FuturesType
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.kline_sockets import (
    open_kline_socket,
)


def test_one_spot_pair_uses_the_plain_kline_socket() -> None:
    bsm = Mock(spec=BinanceSocketManager)

    socket = open_kline_socket(bsm, MarketType.SPOT, [("BTCUSDT", "1m")])

    bsm.kline_socket.assert_called_once_with("BTCUSDT", interval="1m")
    bsm.multiplex_socket.assert_not_called()
    assert socket is bsm.kline_socket.return_value


def test_several_spot_pairs_share_the_multiplex_socket() -> None:
    bsm = Mock(spec=BinanceSocketManager)

    socket = open_kline_socket(
        bsm, MarketType.SPOT, [("BTCUSDT", "1m"), ("ETHUSDT", "5m")]
    )

    bsm.multiplex_socket.assert_called_once_with(
        ["btcusdt@kline_1m", "ethusdt@kline_5m"]
    )
    assert socket is bsm.multiplex_socket.return_value


@pytest.mark.parametrize(
    ("market", "futures_type"),
    [
        (MarketType.FUTURES_USD_M, FuturesType.USD_M),
        (MarketType.FUTURES_COIN_M, FuturesType.COIN_M),
    ],
)
def test_futures_klines_come_from_the_futures_host_even_for_one_pair(
    market: MarketType, futures_type: FuturesType
) -> None:
    """Never `kline_socket`, which is Spot's host, and never the single-pair
    `kline_futures_socket`, whose `continuous_kline` events the parser
    does not read."""
    bsm = Mock(spec=BinanceSocketManager)

    socket = open_kline_socket(bsm, market, [("BTCUSDT", "1m")])

    bsm.futures_multiplex_socket.assert_called_once_with(
        ["btcusdt@kline_1m"], futures_type=futures_type
    )
    bsm.kline_socket.assert_not_called()
    bsm.kline_futures_socket.assert_not_called()
    assert socket is bsm.futures_multiplex_socket.return_value


def test_every_market_has_a_socket() -> None:
    """A market added to `MarketType` without an opener is a `KeyError` at
    the first subscription; this makes it one here instead."""
    for market in MarketType:
        open_kline_socket(Mock(spec=BinanceSocketManager), market, [("X", "1m")])
