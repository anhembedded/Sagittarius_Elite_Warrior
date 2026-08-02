import asyncio
import logging
from typing import List, Optional
from datetime import datetime, timezone

from binance import AsyncClient, BinanceSocketManager
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService
from Binace_Bot.src.application.contracts.i_live_stream_service import (
    ILiveStreamService,
)

from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent

logger = logging.getLogger("App.LiveStream")


class BinanceWebsocketService(IHostedService, ILiveStreamService):
    def __init__(self, event_bus: IEventBus, config: IConfig):
        self._event_bus = event_bus
        self._config = config
        self._client: Optional[AsyncClient] = None
        self._bsm: Optional[BinanceSocketManager] = None
        self._running = False
        self._task = None
        self._engine_context: Optional[IEngineContext] = None

    def start(self, context: IEngineContext) -> None:
        """
        @brief HostedService start. Called on boot.
        Stores context for later use but does NOT start the stream automatically.
        """
        self._engine_context = context
        logger.info("BinanceWebsocketService initialized and awaiting commands.")

    def start_stream(self, symbols: List[str], interval_str: str) -> bool:
        """
        @brief Triggers the stream. Safe to call multiple times (checks _running).
        """
        if self._running:
            logger.warning("Stream is already running. Stop it first.")
            return False

        if not self._engine_context:
            logger.error("Engine context not available.")
            return False

        interval = TimeFrame(interval_str)
        self._running = True
        logger.info(
            f"Starting Binance WebSocket stream for {symbols} at {interval.value}"
        )

        self._task = self._engine_context.async_runtime.run_coroutine(
            self._run_stream(symbols, interval)
        )
        return True

    async def _run_stream(self, symbols: List[str], interval: TimeFrame) -> None:

        # Initialize AsyncClient. API keys are not needed for public streams.
        self._client = await AsyncClient.create()
        self._bsm = BinanceSocketManager(self._client)

        # Create a multiplex socket if multiple symbols, or single socket if one.
        # kline format: <symbol>@kline_<interval>
        streams = [f"{symbol.lower()}@kline_{interval.value}" for symbol in symbols]

        while self._running:
            try:
                if len(streams) == 1:
                    socket = self._bsm.kline_socket(
                        symbols[0].upper(), interval=interval.value
                    )
                else:
                    socket = self._bsm.multiplex_socket(streams)

                async with socket as tscm:
                    while self._running:
                        res = await tscm.recv()

                        if res:
                            # Multiplex stream wraps the message in a "data" property
                            if "data" in res:
                                res = res["data"]

                            # 'e' == 'kline'
                            if res.get("e") == "kline":
                                market_data = self._parse_kline(res)

                                # Log data tick (this will be sent to the Log Viewer via TCP)
                                logger.info(
                                    f"[Live Stream] {market_data.symbol} | Price: {market_data.close_price} | Vol: {market_data.volume} | Closed: {market_data.is_closed}"
                                )

                                # Publish event to the bus
                                self._event_bus.emit(
                                    MarketTickEvent(market_data=market_data)
                                )

            except Exception as e:
                if self._running:
                    logger.error(
                        f"Error receiving from websocket: {e}. Reconnecting in 5 seconds..."
                    )
                    await asyncio.sleep(5)

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

    def stop_stream(self) -> bool:
        """
        @brief Stops the running stream.
        """
        if not self._running:
            logger.warning("Stream is not running.")
            return False

        logger.info("Stopping Binance WebSocket stream...")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                # Wait for the stream loop to actually finish cancelling
                self._task.result(timeout=2.0)
            except Exception:
                pass

        if self._client and self._engine_context:
            try:
                # Synchronously wait for the connection to close to prevent RuntimeWarning
                future = self._engine_context.async_runtime.run_coroutine(
                    self._client.close_connection()
                )
                future.result(timeout=2.0)
            except Exception:
                pass

        logger.info("Binance WebSocket stream stopped.")
        return True

    def stop(self, context: IEngineContext) -> None:
        """
        @brief HostedService stop. Called on engine shutdown.
        """
        if self._running:
            self.stop_stream()
