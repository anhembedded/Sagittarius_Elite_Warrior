import logging
import time

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)

from .command import RunBacktestCommand


class BacktestState:
    """
    @brief Singleton state to manage the backtest running flag.
    """

    def __init__(self) -> None:
        self.is_running = False


class RunBacktestCommandHandler(ICommandHandler[RunBacktestCommand, None]):
    """
    @brief Handler for RunBacktestCommand. Simulates live market feed using historical data.
    """

    def __init__(
        self,
        repo: IMarketDataRepository,
        event_publisher: IEventPublisher,
        state: BacktestState,
    ) -> None:
        self.repo = repo
        self.event_publisher = event_publisher
        self.state = state
        self.logger = logging.getLogger("App.RunBacktest")

    def execute(self, command: RunBacktestCommand) -> None:
        """
        @brief Executes the backtest simulation loop.
        """
        if self.state.is_running:
            self.logger.warning("A backtest simulation is already running.")
            return

        self.logger.info(
            f"Starting backtest simulation for {command.symbol} at interval {command.interval.value}"
        )

        klines = self._fetch_historical_data(command)
        if not klines:
            return

        self._run_simulation_loop(klines, command)

    def _fetch_historical_data(
        self, command: RunBacktestCommand
    ) -> list[MarketData] | None:
        """
        @brief Fetches historical klines for the simulation.
        """
        klines = self.repo.get_klines(
            symbol=command.symbol,
            interval=command.interval,
            start_time=command.start_time if hasattr(command, "start_time") else None,
            end_time=command.end_time if hasattr(command, "end_time") else None,
            limit=command.limit,
        )

        if not klines:
            self.logger.warning(
                f"No historical data found for {command.symbol}. Please run sync first."
            )
            return None

        self.logger.info(
            f"Loaded {len(klines)} historical candles. Starting simulation loop..."
        )
        return klines

    def _run_simulation_loop(
        self, klines: list[MarketData], command: RunBacktestCommand
    ) -> None:
        """
        @brief Runs the backtest simulation loop, emitting events and throttling.
        """
        self.state.is_running = True

        for i, kline in enumerate(klines):
            if not self.state.is_running:
                self.logger.info("Backtest simulation stopped by user.")
                break

            # Create a mock market tick event for each candle
            event = MarketTickEvent(market_data=kline)

            # Emit the event
            self.event_publisher.publish(event)

            # Throttle the simulation
            if command.replay_speed_ms > 0:
                time.sleep(command.replay_speed_ms / 1000.0)

            if i % 100 == 0 and i > 0:
                self.logger.info(f"Simulated {i}/{len(klines)} candles...")

        self.state.is_running = False
        self.logger.info("Backtest simulation completed/stopped.")
