from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

CancellationCheck = Callable[[], bool]


class ExchangeRequestCancelledError(RuntimeError):
    """Raised when a cooperative exchange request is cancelled by its owner."""


class IExchangeClient(ABC):
    """
    @brief Port for communicating with an external cryptocurrency exchange.
    """

    @abstractmethod
    def get_historical_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_str: str | datetime,
        end_str: str | datetime | None = None,
        progress_callback: Callable[[int], None] | None = None,
        cancellation_requested: CancellationCheck | None = None,
    ) -> list[MarketData]:
        """
        @brief Fetches historical kline data for a symbol.
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
        @return An iterator of `MarketData` chunks, in chronological order.
        """

    @abstractmethod
    def get_available_symbols(self) -> list[str]:
        """
        @brief Lists every actively tradeable symbol on the exchange (BOT-102).
        @return Sorted list of symbol names (e.g. ["BTCUSDT", "ETHUSDT", ...]),
        restricted to symbols currently open for trading.
        """
