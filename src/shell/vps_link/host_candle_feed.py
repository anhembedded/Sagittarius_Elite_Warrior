"""`EPIC-047E` — a chart's candles, from the host instead of the exchange.

@details `ICandleFeed` is where a live chart gets its history and its stream. The Bots tab's feed fetches klines from
Binance into the desktop's store; the VPS tab's connects to nothing at Binance (decision record 2026-10-27, D1), so this
one asks the host over the bridge's `candles` call for the closed candles its recorder keeps, and lets the live candle
arrive as the ticks `HostEventPublisher` puts on the bus. One feed is one venue's market, as every feed is.

@par Offline and unpublished
A call that cannot be served is `CandlesUnavailableError` with a sentence the chart shows as it is: the link is down
("the chart keeps the candles it has"), the host keeps no store for the symbol, the host serves no candles. The chart
freezes at its last candle and says why; nothing is fetched from anywhere else (D5).

@par `sync` is the host's
The host's recorder fills its store (`EPIC-047H`); a `sync` from the desktop would be a Binance fetch, so it does
nothing here and returns at once.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_world import (
    NOT_PUBLISHED_BY_THE_HOST,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.closed_candle_window import (
    CandleWindow,
    StoredCandle,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_world import LinkHostWorld
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    CandleStreamStart,
    CandlesUnavailableError,
    ICandleFeed,
    OlderCandlesRequest,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_candles import (
    candle_venue_code,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    CallFailedError,
    CallTimedOutError,
    LinkLostError,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireDecodeError
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

OFFLINE_WORDS = "Not connected to the host: the chart keeps the candles it has until the link is back."
LIVE_WORDS = "The live candle comes from the host."
_ZERO = 0.0


class HostCandleFeed(ICandleFeed):
    def __init__(
        self, venue: TradingVenue, world: LinkHostWorld, roots: WireRoots
    ) -> None:
        self._venue = venue
        self._world = world
        self._roots = roots

    def sync(
        self,
        symbol: str,
        interval: TimeFrame,
        cancelled: Callable[[], bool],
        *,
        newest: int | None = None,
    ) -> None:
        """Nothing: the host's recorder keeps the store, and a desktop sync would fetch from Binance."""

    def load_history(
        self, symbol: str, interval: TimeFrame, limit: int
    ) -> Sequence[MarketData]:
        return self._candles(symbol, interval, limit, None)

    def load_older(
        self, request: OlderCandlesRequest, cancelled: Callable[[], bool]
    ) -> Sequence[MarketData]:
        return self._candles(
            request.symbol, request.interval, request.limit, request.before
        )

    def start_stream(
        self, owner_id: str, symbol: str, interval: TimeFrame
    ) -> CandleStreamStart:
        return CandleStreamStart(True, LIVE_WORDS)

    def stop_stream(self, owner_id: str) -> None:
        """Nothing was opened: the ticks are the host's, on the bus."""

    def _candles(
        self, symbol: str, interval: TimeFrame, limit: int, before: datetime | None
    ) -> Sequence[MarketData]:
        link = self._world.live_link()
        if link is None:
            raise CandlesUnavailableError(OFFLINE_WORDS)
        params: dict[str, object] = {
            "venue": candle_venue_code(self._venue),
            "symbol": symbol,
            "timeframe": interval.value,
            "limit": limit,
        }
        if before is not None:
            params["before"] = before.isoformat()
        try:
            data = link.call("candles", params)
        except LinkLostError:
            raise CandlesUnavailableError(OFFLINE_WORDS) from None
        except CallTimedOutError:
            raise CandlesUnavailableError(
                "The host did not answer for the candles in time."
            ) from None
        except CallFailedError as refused:
            raise CandlesUnavailableError(
                f"The host cannot serve these candles: {refused}"
            ) from None
        window = self._window_of(data)
        if not window.shard_found:
            raise CandlesUnavailableError(f"Candles: {NOT_PUBLISHED_BY_THE_HOST}.")
        span = timedelta(seconds=interval.to_seconds())
        return [_market_data(window.symbol, interval, c, span) for c in window.candles]

    def _window_of(self, data: dict[str, object]) -> CandleWindow:
        try:
            window = self._roots.decode(data.get("window"))
        except WireDecodeError:
            raise CandlesUnavailableError(
                "The host's candles could not be read by this build."
            ) from None
        if not isinstance(window, CandleWindow):
            raise CandlesUnavailableError(
                "The host's candles could not be read by this build."
            )
        return window


def _market_data(
    symbol: str, interval: TimeFrame, candle: StoredCandle, span: timedelta
) -> MarketData:
    return MarketData(
        symbol=symbol,
        interval=interval.value,
        open_time=candle.open_time,
        open_price=float(candle.open_price),
        high_price=float(candle.high_price),
        low_price=float(candle.low_price),
        close_price=float(candle.close_price),
        volume=float(candle.volume),
        close_time=candle.open_time + span - timedelta(milliseconds=1),
        quote_asset_volume=_ZERO,
        number_of_trades=0,
        taker_buy_base_asset_volume=_ZERO,
        taker_buy_quote_asset_volume=_ZERO,
        is_closed=True,
    )
