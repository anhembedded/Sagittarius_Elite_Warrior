"""`EPIC-028C` — which Binance websocket serves a market's klines.

@details Spot klines come from `stream.binance.com`, USD-M and COIN-M
Futures klines from `fstream`/`dstream`: three hosts, three prices for what
reads as the same symbol. `BinanceWebsocketService` runs one connection per
market and asks this module for that market's socket, so adding a market is
one entry in `_OPENERS` (`architecture-rule.md` §7.2.1). Plausible
extensions: a mainnet/testnet split per market when those diverge; an
options market; a mark-price kline stream for Futures.

Futures always goes through the multiplex socket, even for one key:
`python-binance`'s single-key `kline_futures_socket` subscribes to
`<pair>_perpetual@continuousKline_<interval>`, whose events are
`continuous_kline` with a `ps` pair field rather than the `kline` event
`BinanceWebsocketService._parse_kline` reads. The multiplex socket with
`<symbol>@kline_<interval>` streams emits the standard `kline` event on
every market, so one parser serves all of them.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from binance import BinanceSocketManager
from binance.enums import FuturesType
from binance.ws.reconnecting_websocket import ReconnectingWebsocket
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType

#: One subscribed `(symbol, interval)` pair on one market.
KlinePair = tuple[str, str]

_Opener = Callable[[BinanceSocketManager, Sequence[KlinePair]], ReconnectingWebsocket]


def kline_stream_names(pairs: Sequence[KlinePair]) -> list[str]:
    """Binance's combined-stream names: lower-case symbol, `@kline_`, interval."""
    return [f"{symbol.lower()}@kline_{interval}" for symbol, interval in pairs]


def _open_spot(
    bsm: BinanceSocketManager, pairs: Sequence[KlinePair]
) -> ReconnectingWebsocket:
    """One pair uses the plain kline socket; several share a multiplex one."""
    if len(pairs) == 1:
        symbol, interval = pairs[0]
        return bsm.kline_socket(symbol.upper(), interval=interval)
    return bsm.multiplex_socket(kline_stream_names(pairs))


def _open_usd_m(
    bsm: BinanceSocketManager, pairs: Sequence[KlinePair]
) -> ReconnectingWebsocket:
    return bsm.futures_multiplex_socket(
        kline_stream_names(pairs), futures_type=FuturesType.USD_M
    )


def _open_coin_m(
    bsm: BinanceSocketManager, pairs: Sequence[KlinePair]
) -> ReconnectingWebsocket:
    return bsm.futures_multiplex_socket(
        kline_stream_names(pairs), futures_type=FuturesType.COIN_M
    )


_OPENERS: dict[MarketType, _Opener] = {
    MarketType.SPOT: _open_spot,
    MarketType.FUTURES_USD_M: _open_usd_m,
    MarketType.FUTURES_COIN_M: _open_coin_m,
}


def open_kline_socket(
    bsm: BinanceSocketManager, market: MarketType, pairs: Sequence[KlinePair]
) -> ReconnectingWebsocket:
    """The socket streaming `pairs`' klines from `market`'s own host."""
    return _OPENERS[market](bsm, pairs)
