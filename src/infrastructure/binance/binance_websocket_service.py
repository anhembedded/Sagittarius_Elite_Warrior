import asyncio
import logging
from datetime import datetime, timezone

from binance import AsyncClient, BinanceSocketManager
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle, ITaskManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken
from Binace_Bot.src.application.ports.i_live_stream_service import (
    ILiveStreamService,
)

from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

logger = logging.getLogger("App.LiveStream")


class BinanceWebsocketService(ILiveStreamService):
    """
    @brief Infrastructure implementation of ILiveStreamService.
    @details Manages a live Binance Kline WebSocket stream using the injected ITaskManager.
    """

    def __init__(self, event_bus: IEventBus, task_manager: ITaskManager) -> None:
        self._event_bus = event_bus
        self._task_manager = task_manager
        self._task_handle: ITaskHandle | None = None
        self._token: CancellationToken | None = None

    # -- ILiveStreamService ----------------------------------------------------

    def start_stream(self, symbols: list[str], interval_str: str) -> bool:
        """
        @brief Spawns the WebSocket stream as a background task via ITaskManager.
        @return True if started, False if already running.
        """
        if self._task_handle is not None:
            logger.warning("Stream is already running. Stop it first.")
            return False

        interval = TimeFrame(interval_str)
        self._token = CancellationToken()

        logger.info(
            f"Starting Binance WebSocket stream for {symbols} at {interval.value}"
        )

        self._task_handle = self._task_manager.spawn(
            self._run_stream(symbols, interval, self._token),
            name=f"BinanceStream[{','.join(symbols)}@{interval.value}]",
            token=self._token,
            critical=True,  # Đảm bảo Engine chờ task này close gracefully khi shutdown
        )
        return True

    def stop_stream(self) -> bool:
        """
        @brief Signals cooperative cancellation and cancels the background task.
        @return True if stopped, False if no stream was running.
        """
        if self._task_handle is None:
            logger.warning("Stream is not running.")
            return False

        logger.info("Stopping Binance WebSocket stream...")

        # Signal the stream loop to exit cooperatively via CancellationToken
        if self._token is not None:
            self._token.cancel()

        # Cancel the underlying future via ITaskHandle
        self._task_handle.cancel()

        self._task_handle = None
        self._token = None

        logger.info("Binance WebSocket stream stopped.")
        return True

    # -- Private ---------------------------------------------------------------

    async def _run_stream(
        self,
        symbols: list[str],
        interval: TimeFrame,
        token: CancellationToken,
    ) -> None:
        """
        @brief Main async stream loop. Runs inside the Engine background task pool.
        Exits cooperatively when the CancellationToken is cancelled.
        """
        is_closing = False
        client = None
        try:
            client = await AsyncClient.create()
            bsm = BinanceSocketManager(client)
            streams = [f"{symbol.lower()}@kline_{interval.value}" for symbol in symbols]

            while not token.is_cancelled():
                try:
                    socket = self._create_socket(bsm, symbols, streams, interval)
                    async with socket as tscm:
                        while not token.is_cancelled():
                            await self._process_socket_message(tscm)

                except asyncio.CancelledError:
                    logger.info("Stream task was cancelled.")
                    break
                except OSError as e:
                    if not token.is_cancelled():
                        logger.error(
                            f"WebSocket connection error: {e}. Reconnecting in 5s..."
                        )
                        await asyncio.sleep(5)
        except GeneratorExit:
            is_closing = True
            raise
        finally:
            if client is not None and not is_closing:
                try:
                    await client.close_connection()
                    logger.info("Binance AsyncClient connection closed.")
                except Exception as e:
                    logger.warning(f"Error closing Binance client: {e}")

    @staticmethod
    def _create_socket(
        bsm, symbols: list[str], streams: list[str], interval: TimeFrame
    ):
        """@brief A single symbol uses the plain kline socket; multiple share a multiplex socket."""
        if len(streams) == 1:
            return bsm.kline_socket(symbols[0].upper(), interval=interval.value)
        return bsm.multiplex_socket(streams)

    async def _process_socket_message(self, tscm) -> None:
        """@brief Receives one message, unwraps the multiplex envelope, and emits on a kline event."""
        res = await tscm.recv()
        if not res:
            return

        # Multiplex stream wraps data in a "data" property
        if "data" in res:
            res = res["data"]

        if res.get("e") == "kline":
            try:
                market_data = self._parse_kline(res)
                logger.info(
                    f"[Live Stream] {market_data.symbol}"
                    f" | Price: {market_data.close_price}"
                    f" | Vol: {market_data.volume}"
                    f" | Closed: {market_data.is_closed}"
                )
                self._event_bus.emit(MarketTickEvent(market_data=market_data))
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Error parsing kline message: {e} | Message: {res}")

    def _parse_kline(self, msg: dict) -> MarketData:
        k = msg["k"]
        return MarketData(
            symbol=k["s"],
            interval=k["i"],
            open_time=datetime.fromtimestamp(k["t"] / 1000.0, tz=timezone.utc),
            open_price=float(k["o"]),
            high_price=float(k["h"]),
            low_price=float(k["l"]),
            close_price=float(k["c"]),
            volume=float(k["v"]),
            close_time=datetime.fromtimestamp(k["T"] / 1000.0, tz=timezone.utc),
            quote_asset_volume=float(k["q"]),
            number_of_trades=int(k["n"]),
            taker_buy_base_asset_volume=float(k["V"]),
            taker_buy_quote_asset_volume=float(k["Q"]),
            is_closed=bool(k["x"]),
        )
