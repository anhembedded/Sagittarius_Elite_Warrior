from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    SymbolMarketMetadata,
)

CancellationCheck = Callable[[], bool]


class ExchangeRequestCancelledError(RuntimeError):
    """Raised when a cooperative exchange request is cancelled by its owner."""


class ExchangeRefusedKlinesError(RuntimeError):
    """The exchange refuses to serve these candles at all (`BUG-172`).

    A testnet is a smaller exchange than the mainnet: Futures has no `1s` klines
    (`-1120`) and each testnet lists fewer symbols (`-1121`). Retrying cannot
    change either answer, so this is not a transient failure: `reason` is a
    sentence a person can read ("Futures has no 1s candles on this exchange"),
    and a screen shows it instead of "try again".
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class IExchangeClient(ABC):
    """
    @brief Port for communicating with an external cryptocurrency exchange.
    """

    def close(self) -> None:
        """Releases what the client holds open (its HTTP session), so a request
        blocked on the network does not outlive the app (`BUG-052`, `BUG-172`).
        Idempotent; a client holding nothing keeps this default."""
        return

    @abstractmethod
    def get_historical_klines(
        self,
        market: MarketType,
        symbol: str,
        interval: TimeFrame,
        start_str: str | datetime,
        end_str: str | datetime | None = None,
        progress_callback: Callable[[int], None] | None = None,
        cancellation_requested: CancellationCheck | None = None,
    ) -> list[MarketData]:
        """
        @brief Fetches historical kline data for a symbol.
        @param market Which Binance market segment to fetch from (`EPIC-027A`).
        @param symbol The trading pair symbol (e.g. BTCUSDT)
        @param interval The timeframe interval (e.g. 1m)
        @param start_str The start time string (e.g. '1 day ago UTC') or datetime
        @param end_str Optional end time string or datetime
        @param cancellation_requested Optional cooperative cancellation check.
        @return A list of MarketData entities.
        """

    @abstractmethod
    def stream_historical_klines(
        self,
        market: MarketType,
        symbol: str,
        interval: TimeFrame,
        start_str: str | datetime,
        end_str: str | datetime | None = None,
        progress_callback: Callable[[int], None] | None = None,
        cancellation_requested: CancellationCheck | None = None,
    ) -> Iterator[list[MarketData]]:
        """
        @brief Fetches historical kline data for a symbol, yielded in bounded
        chunks as they arrive from the exchange (BUG-025).
        @details Unlike `get_historical_klines`, this never accumulates the
        full requested range in RAM — each yielded chunk can be persisted
        and discarded before the next one is fetched. Intended for callers
        whose requested range has no inherent upper bound (bulk/full-history
        sync); bounded, small requests should keep using
        `get_historical_klines`.
        @param market Which Binance market segment to fetch from (`EPIC-027A`).
        @return An iterator of `MarketData` chunks, in chronological order.
        """

    @abstractmethod
    def get_available_symbols(self, market: MarketType) -> list[str]:
        """
        @brief Lists every actively tradeable symbol on the exchange (BOT-102).
        @param market Which market's catalog (`EPIC-027D`): Spot and USD-M
        Futures list different symbols.
        @return Sorted list of symbol names (e.g. ["BTCUSDT", "ETHUSDT", ...]),
        restricted to symbols currently open for trading.
        """

    @abstractmethod
    def get_symbol_metadata(self, market: MarketType) -> list[SymbolMarketMetadata]:
        """
        @brief Every symbol's price, lot and notional filters (`BUG-127`).
        @param market Which market's filters (`EPIC-027C`): the same symbol has
        a different step size and minimum notional on Spot and on Futures.

        @details The same payload `get_available_symbols()` already fetches and
        then keeps only the names from. This is that discarded half, and it is a
        second method rather than a wider return on the first because the two
        have different callers: the symbol picker wants names, and only the
        Backtest screen's exchange-rule check wants filters. Widening the
        existing method would have made every name-reader carry a payload it
        never looks at.

        Neither method caches. `SymbolCatalogService` stores names through
        `ISymbolCatalogRepository` and `ISymbolMetadataProvider` stores filters
        through `ISymbolMarketMetadataCache`; a client that cached would be
        deciding freshness for both of them.

        @return One entry per symbol the exchange reports, in the exchange's own
        order. Filtering by status is the caller's, exactly as it already is for
        names.
        """
