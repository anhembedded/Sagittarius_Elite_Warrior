from sagittarius_engine import App

from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.application.use_cases.process_market_tick import (
    ProcessMarketTickCommand,
)


class MarketTickEventHandler:
    """
    @brief Application Event Handler for MarketTickEvent.
    @details Listens to MarketTickEvent emitted by the Domain/Infrastructure and dispatches ProcessMarketTickCommand.
    """

    def __init__(self, app: App) -> None:
        self.app = app

    def handle(self, event: MarketTickEvent) -> None:
        """
        @brief Handles the MarketTickEvent by dispatching a ProcessMarketTickCommand.
        """
        cmd = ProcessMarketTickCommand(market_data=event.market_data)
        self.app.dispatch(ProcessMarketTickCommand, cmd)
