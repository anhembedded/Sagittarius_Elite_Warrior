import logging
from Binace_Bot.src.application.ports.cqrs import ICommandHandler
from .command import ProcessMarketTickCommand

class ProcessMarketTickCommandHandler(ICommandHandler[ProcessMarketTickCommand, None]):
    """
    @brief Handler for ProcessMarketTickCommand.
    @details Acts as the entry point for the trading strategy in the future.
    """
    def __init__(self) -> None:
        self.logger = logging.getLogger("App.TradingStrategy")

    def execute(self, command: ProcessMarketTickCommand) -> None:
        """
        @brief Process the market tick.
        """
        md = command.market_data
        self.logger.info(f"Processing tick for {md.symbol} at {md.close_price}")
