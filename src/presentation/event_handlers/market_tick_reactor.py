from sagittarius_engine import App

from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.application.use_cases.process_market_tick import (
    ProcessMarketTickCommand,
)


class MarketTickReactor:
    """
    @brief Event Reactor in the Presentation Layer (Interface Adapters).
    @details Listens to MarketTickEvent from the Domain/Infrastructure and translates it into an Application Command.
    """

    def __init__(self, app: App) -> None:
        self.app = app

    def handle(self, event: MarketTickEvent) -> None:
        """
        @brief Transforms the event into a DTO and dispatches to the Application layer.
        """
        cmd = ProcessMarketTickCommand(market_data=event.market_data)
        self.app.dispatch(ProcessMarketTickCommand, cmd)
