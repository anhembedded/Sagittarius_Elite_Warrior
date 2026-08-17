import logging
from collections.abc import Callable
from datetime import UTC, datetime

from binance.client import Client

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    CancellationCheck,
    ExchangeRequestCancelled,
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

logger = logging.getLogger("App.ExchangeClient")


class PythonBinanceClient(IExchangeClient):
    """
    @brief Infrastructure Adapter for python-binance.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        client: Client | None = None,
    ) -> None:
        """
        @param client Optional pre-built binance.client.Client (or a test double). Lets
        callers (and unit tests) inject a client directly instead of this class always
        constructing the concrete SDK client itself — Dependency Inversion. Defaults to
        constructing the real Client from api_key/api_secret when not provided, so
        existing call sites (and app_bootstrapper's container wiring) are unaffected.
        """
        self.client = client if client is not None else Client(api_key, api_secret)

    def _format_time(self, time_val: str | datetime | None) -> str | None:
        if isinstance(time_val, datetime):
            return time_val.astimezone(UTC).strftime("%d %b %Y %H:%M:%S")
        return time_val

    def _fetch_raw_klines(
        self,
        symbol: str,
        interval: str,
        start_str: str,
        end_str: str | None,
        progress_callback: Callable[[int], None] | None,
        cancellation_requested: CancellationCheck | None,
    ) -> list[list]:
        try:
            self._raise_if_cancelled(cancellation_requested)
            raw_klines = []
            generator = self.client.get_historical_klines_generator(
                symbol, interval, start_str, end_str
            )
            for i, k in enumerate(generator):
                self._raise_if_cancelled(cancellation_requested)
                raw_klines.append(k)
                # Binance usually returns up to 1000 klines per request chunk.
                # We can update the UI roughly every 1000 items to avoid UI blocking while still keeping it smooth.
                if (i + 1) % 1000 == 0:
                    logger.debug(f"[{symbol}] Downloaded {i + 1} klines so far...")
                    if progress_callback:
                        progress_callback(i + 1)

            # One final progress update at the end
            if progress_callback:
                progress_callback(len(raw_klines))

            logger.info(f"Successfully fetched {len(raw_klines)} klines for {symbol}.")
            return raw_klines
        except ExchangeRequestCancelled:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch historical klines for {symbol}: {e}")
            raise

    @staticmethod
    def _raise_if_cancelled(
        cancellation_requested: CancellationCheck | None,
    ) -> None:
        if cancellation_requested is not None and cancellation_requested():
            raise ExchangeRequestCancelled("Historical kline request cancelled")

    def _map_to_market_data(
        self, raw_klines: list[list], symbol: str, interval: str
    ) -> list[MarketData]:
        market_data_list = []
        for k in raw_klines:
            market_data_list.append(
                MarketData(
                    symbol=symbol,
                    interval=interval,
                    open_time=datetime.fromtimestamp(k[0] / 1000.0, tz=UTC),
                    open_price=float(k[1]),
                    high_price=float(k[2]),
                    low_price=float(k[3]),
                    close_price=float(k[4]),
                    volume=float(k[5]),
                    close_time=datetime.fromtimestamp(k[6] / 1000.0, tz=UTC),
                    quote_asset_volume=float(k[7]),
                    number_of_trades=int(k[8]),
                    taker_buy_base_asset_volume=float(k[9]),
                    taker_buy_quote_asset_volume=float(k[10]),
                )
            )
        return market_data_list

    def get_historical_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_str: str | datetime,
        end_str: str | datetime | None = None,
        progress_callback: Callable[[int], None] | None = None,
        cancellation_requested: CancellationCheck | None = None,
    ) -> list[MarketData]:
        # Convert datetime to string or millisecond timestamp for python-binance if needed
        # python-binance accepts datetime, string ('1 day ago UTC'), or ms timestamp

        formatted_start = self._format_time(start_str)
        formatted_end = self._format_time(end_str)

        logger.info(
            f"Fetching historical klines for {symbol} at {interval.value} from {formatted_start} to {formatted_end or 'NOW'}"
        )

        raw_klines = self._fetch_raw_klines(
            symbol,
            interval.value,
            formatted_start,
            formatted_end,
            progress_callback,
            cancellation_requested,
        )

        return self._map_to_market_data(raw_klines, symbol, interval.value)
