import logging
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import requests
from binance.client import Client
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    CancellationCheck,
    ExchangeRequestCancelledError,
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.binance.market_metadata_parser import (
    DEFAULT_STATUS,
    BinanceMetadataKey,
)

logger = logging.getLogger("App.ExchangeClient")

#: Top-level key in Binance's GET /api/v3/exchangeInfo payload holding the
#: per-symbol entries — distinct from BinanceMetadataKey.FILTERS, which is
#: the nested filter list *inside* one such entry (BOT-102).
_EXCHANGE_INFO_SYMBOLS_KEY = "symbols"

#: Klines per yielded chunk in `stream_historical_klines` (BUG-025) — matches
#: Binance's own per-request page size, so a chunk boundary always lines up
#: with a page boundary already paid for over the network.
_KLINE_STREAM_CHUNK_SIZE = 1000

#: BUG-063 — python-binance's own default read timeout is 10s. A multi-day
#: 1-second-interval sync needs hundreds of sequential requests, so at that
#: default, an ordinary slow response (not an outage) was enough to fail the
#: whole sync. 30s is still bounded — a genuinely dead connection fails loud
#: well within human patience — but stops treating an occasional slow page as
#: fatal.
_DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0

#: BUG-063 — consecutive transient network failures (no kline received
#: between them) tolerated before `_generate_raw_klines_with_retry` gives up.
#: Any failure that a retry DOES make progress past resets this counter, so
#: a flaky-but-working connection can keep going indefinitely; only a
#: connection that yields nothing across every retry is judged genuinely
#: down.
_MAX_TRANSIENT_RETRIES = 3

#: BUG-063 — base delay for the exponential backoff between retry attempts.
_RETRY_BACKOFF_BASE_SECONDS = 2.0

#: BUG-063 — chunk size for the cancellable backoff sleep, mirroring
#: `ThreadSafeRateLimiter.acquire()`'s own polling idiom so a cancellation
#: during backoff is honoured quickly instead of only between pages.
_CANCELLATION_POLL_INTERVAL_SEC = 0.05


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
        self.client = (
            client
            if client is not None
            else Client(
                api_key,
                api_secret,
                requests_params={"timeout": _DEFAULT_REQUEST_TIMEOUT_SECONDS},
            )
        )

    def _format_time(self, time_val: str | datetime | None) -> str | None:
        if isinstance(time_val, datetime):
            return time_val.astimezone(UTC).strftime("%d %b %Y %H:%M:%S")
        return time_val

    def _generate_raw_klines_with_retry(
        self,
        symbol: str,
        interval: str,
        start_str: str | int | None,
        end_str: str | None,
        cancellation_requested: CancellationCheck | None,
    ) -> Iterator[list]:
        """
        @brief Yields raw klines from `get_historical_klines_generator`,
        resuming past the last kline it actually delivered instead of
        failing the whole request on one transient network error (BUG-063).
        @details A multi-day 1-second-interval sync needs hundreds of
        sequential HTTP calls, and python-binance's own generator has no
        retry of its own — one `ReadTimeout` among hundreds of pages used to
        abort everything the current attempt had already fetched, including
        klines already pulled but not yet handed to the caller.

        Resumes via the last yielded kline's own `close_time + 1ms` (the
        same inclusive-close_time convention `BUG-022` established
        elsewhere), never by restarting `start_str` from the original
        request — a retry must not re-download klines this call already
        has.

        The retry budget resets on every kline actually yielded: a
        flaky-but-working connection can keep making forward progress
        indefinitely (the caller's own cancellation is the only bound on
        that), while a connection that yields nothing between attempts is
        judged genuinely down and gives up after `_MAX_TRANSIENT_RETRIES`
        consecutive failures.
        """
        current_start = start_str
        consecutive_failures = 0
        while True:
            self._raise_if_cancelled(cancellation_requested)
            generator = self.client.get_historical_klines_generator(
                symbol, interval, current_start, end_str
            )
            try:
                for k in generator:
                    self._raise_if_cancelled(cancellation_requested)
                    yield k
                    current_start = int(k[6]) + 1
                    consecutive_failures = 0
                return
            except ExchangeRequestCancelledError:
                raise
            except requests.exceptions.RequestException as exc:
                consecutive_failures += 1
                if consecutive_failures > _MAX_TRANSIENT_RETRIES:
                    logger.error(
                        f"[{symbol}] Giving up after {_MAX_TRANSIENT_RETRIES} "
                        f"consecutive transient network errors: {exc}"
                    )
                    raise
                delay = _RETRY_BACKOFF_BASE_SECONDS * (2 ** (consecutive_failures - 1))
                logger.warning(
                    f"[{symbol}] Transient network error ({exc}); resuming from "
                    f"{current_start} in {delay:.0f}s "
                    f"(attempt {consecutive_failures}/{_MAX_TRANSIENT_RETRIES})"
                )
                self._cancellable_sleep(delay, cancellation_requested)

    @staticmethod
    def _cancellable_sleep(
        seconds: float, cancellation_requested: CancellationCheck | None
    ) -> None:
        """Sleeps in small chunks so a cancellation during retry backoff is
        honoured within `_CANCELLATION_POLL_INTERVAL_SEC`, mirroring
        `ThreadSafeRateLimiter.acquire()`'s own polling idiom — otherwise
        cancelling right after a timeout would leave the caller waiting out
        the full backoff delay first."""
        if cancellation_requested is None:
            time.sleep(seconds)
            return
        remaining = seconds
        while remaining > 0:
            if cancellation_requested():
                raise ExchangeRequestCancelledError(
                    "Historical kline request cancelled"
                )
            chunk = min(_CANCELLATION_POLL_INTERVAL_SEC, remaining)
            time.sleep(chunk)
            remaining -= chunk

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
            raw_klines = []
            generator = self._generate_raw_klines_with_retry(
                symbol, interval, start_str, end_str, cancellation_requested
            )
            for i, k in enumerate(generator):
                raw_klines.append(k)
                # Update the UI roughly once per Binance request page
                # (_KLINE_STREAM_CHUNK_SIZE) to avoid UI blocking while
                # still keeping it smooth.
                if (i + 1) % _KLINE_STREAM_CHUNK_SIZE == 0:
                    logger.debug(f"[{symbol}] Downloaded {i + 1} klines so far...")
                    if progress_callback:
                        progress_callback(i + 1)

            # One final progress update at the end
            if progress_callback:
                progress_callback(len(raw_klines))

            logger.info(f"Successfully fetched {len(raw_klines)} klines for {symbol}.")
            return raw_klines
        except ExchangeRequestCancelledError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch historical klines for {symbol}: {e}")
            raise

    def stream_historical_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_str: str | datetime,
        end_str: str | datetime | None = None,
        progress_callback: Callable[[int], None] | None = None,
        cancellation_requested: CancellationCheck | None = None,
    ) -> Iterator[list[MarketData]]:
        formatted_start = self._format_time(start_str)
        formatted_end = self._format_time(end_str)

        logger.info(
            f"Streaming historical klines for {symbol} at {interval.value} from {formatted_start} to {formatted_end or 'NOW'}"
        )

        yield from self._stream_raw_klines_as_market_data(
            symbol,
            interval.value,
            formatted_start,
            formatted_end,
            progress_callback,
            cancellation_requested,
        )

    def _stream_raw_klines_as_market_data(
        self,
        symbol: str,
        interval: str,
        start_str: str,
        end_str: str | None,
        progress_callback: Callable[[int], None] | None,
        cancellation_requested: CancellationCheck | None,
    ) -> Iterator[list[MarketData]]:
        try:
            generator = self._generate_raw_klines_with_retry(
                symbol, interval, start_str, end_str, cancellation_requested
            )
            buffer: list = []
            total_fetched = 0
            for k in generator:
                buffer.append(k)
                if len(buffer) >= _KLINE_STREAM_CHUNK_SIZE:
                    total_fetched += len(buffer)
                    if progress_callback:
                        progress_callback(total_fetched)
                    yield self._map_to_market_data(buffer, symbol, interval)
                    buffer = []

            if buffer:
                total_fetched += len(buffer)
                if progress_callback:
                    progress_callback(total_fetched)
                yield self._map_to_market_data(buffer, symbol, interval)

            logger.info(f"Successfully streamed {total_fetched} klines for {symbol}.")
        except ExchangeRequestCancelledError:
            raise
        except Exception as e:
            logger.error(f"Failed to stream historical klines for {symbol}: {e}")
            raise

    @staticmethod
    def _raise_if_cancelled(
        cancellation_requested: CancellationCheck | None,
    ) -> None:
        if cancellation_requested is not None and cancellation_requested():
            raise ExchangeRequestCancelledError("Historical kline request cancelled")

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

    def get_available_symbols(self) -> list[str]:
        info = self.client.get_exchange_info()
        symbols_raw = info.get(_EXCHANGE_INFO_SYMBOLS_KEY, [])
        tradeable = {
            str(entry.get(BinanceMetadataKey.SYMBOL.value, "")).upper()
            for entry in symbols_raw
            if isinstance(entry, dict)
            and str(entry.get(BinanceMetadataKey.STATUS.value, "")).upper()
            == DEFAULT_STATUS
        }
        tradeable.discard("")
        return sorted(tradeable)

    def close(self) -> None:
        """Close the underlying requests.Session to unblock any pending network read.

        Helps prevent BUG-052/BUG-067 thread pool worker hangs during application shutdown.
        """
        session = getattr(self.client, "session", None)
        if session is not None:
            try:
                session.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Error closing binance requests session: %s", exc)
