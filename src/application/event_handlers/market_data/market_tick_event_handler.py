import logging

from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)
from sagittarius_engine import App


class MarketTickEventHandler:
    """
    @brief Application Event Handler for MarketTickEvent.
    @details Listens to MarketTickEvent emitted by the Domain/Infrastructure and processes the market tick directly.
    """

    def __init__(self, app: App) -> None:
        self.app = app
        self.logger = logging.getLogger("App.TradingStrategy")

    def handle(self, event: MarketTickEvent) -> None:
        """
        @brief Handles the MarketTickEvent.
        """
        md = event.market_data
        self.logger.info(f"Processing tick for {md.symbol} at {md.close_price}")

        # Here we will later invoke domain logic for strategy processing
