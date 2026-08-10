import logging

from Binace_Bot.src.application.ports.i_cqrs import ICommandHandler
from Binace_Bot.src.application.use_cases.backtest.run_backtest.handler import (
    BacktestState,
)

from .command import StopBacktestCommand


class StopBacktestCommandHandler(ICommandHandler[StopBacktestCommand, None]):
    """
    @brief Handler for StopBacktestCommand. Stops the currently running backtest simulation.
    """

    def __init__(self, state: BacktestState) -> None:
        self.state = state
        self.logger = logging.getLogger("App.StopBacktest")

    def execute(self, command: StopBacktestCommand) -> None:
        """
        @brief Signals the backtest loop to stop.
        """
        if not self.state.is_running:
            self.logger.warning("No backtest is currently running.")
            return

        self.logger.info("Signaling backtest simulation to stop...")
        self.state.is_running = False
