import time
import logging
from Binace_Bot.src.application.ports.cqrs import ICommandHandler
from Binace_Bot.src.application.ports.i_market_data_repository import IMarketDataRepository
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from .command import RunBacktestCommand

class RunBacktestCommandHandler(ICommandHandler[RunBacktestCommand, None]):
    """
    @brief Handler for RunBacktestCommand. Simulates live market feed using historical data.
    """
    def __init__(
        self,
        repo: IMarketDataRepository,
        event_bus: IEventBus
    ) -> None:
        self.repo = repo
        self.event_bus = event_bus
        self.logger = logging.getLogger("App.RunBacktest")

    def execute(self, command: RunBacktestCommand) -> None:
        """
        @brief Executes the backtest simulation loop.
        """
        self.logger.info(
            f"Starting backtest simulation for {command.symbol} at interval {command.interval.value}"
        )

        # 1. Fetch historical data
        klines = self.repo.get_klines(
            symbol=command.symbol,
            interval=command.interval,
            limit=command.limit
        )

        if not klines:
            self.logger.warning(f"No historical data found for {command.symbol}. Please run sync first.")
            return

        self.logger.info(f"Loaded {len(klines)} historical candles. Starting simulation loop...")

        # 2. Simulation Loop with Throttling
        for i, kline in enumerate(klines):
            # Create a mock market tick event for each candle
            # Note: A real tick has current price, here we use the closed kline for the mock tick
            event = MarketTickEvent(market_data=kline)
            
            # Emit the event
            self.event_bus.emit(event)
            
            # Throttle the simulation
            if command.replay_speed_ms > 0:
                time.sleep(command.replay_speed_ms / 1000.0)

            if i % 100 == 0 and i > 0:
                self.logger.info(f"Simulated {i}/{len(klines)} candles...")

        self.logger.info("Backtest simulation completed.")
