import logging

from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)


class MarketTickEventHandler:
    """
    @brief Application Event Handler for MarketTickEvent.
    @details Listens to MarketTickEvent emitted by the Domain/Infrastructure and processes the market tick directly.

    @par No engine dependency (`EPIC-008F`)
    This class used to take `sagittarius_engine.App` in its constructor and
    store it as `self.app` — the whole engine runtime held by an
    Application-layer object, the heaviest of the layering violations that
    epic set out to remove. It was also **never read**: the attribute was
    assigned and nothing ever used it, so dropping the parameter changes no
    behaviour. Anything this handler genuinely needs later must arrive as a
    port (`application/ports/`), not as the runtime it could pull anything out
    of.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("App.TradingStrategy")

    def handle(self, event: MarketTickEvent) -> None:
        """
        @brief Handles the MarketTickEvent.
        """
        md = event.market_data
        self.logger.info(f"Processing tick for {md.symbol} at {md.close_price}")

        # Here we will later invoke domain logic for strategy processing
