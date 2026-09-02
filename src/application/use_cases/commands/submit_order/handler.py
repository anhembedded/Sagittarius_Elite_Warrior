import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.commands.submit_order.command import (
    SubmitOrderCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order

logger = logging.getLogger("App.CommandHandler")


class SubmitOrderCommandHandler(ICommandHandler[SubmitOrderCommand, Order]):
    """
    @brief Handler for `SubmitOrderCommand` (`EPIC-021F`).

    @details Reuses `PreviewOrderQueryHandler` directly (not through the
    dispatcher — this is one handler using another as a plain
    collaborator, not a CQRS call) so normalization can never drift
    between `order-preview` and `order-dry-run`/`order-submit`. Whatever
    `ITradingClient.place_order()` raises (`OrderRejectedByExchangeError`,
    `InvalidOrderForSubmissionError`, a network exception) is left to
    propagate — this handler has nothing useful to add to those.
    """

    def __init__(
        self, preview_handler: PreviewOrderQueryHandler, trading_client: ITradingClient
    ) -> None:
        self._preview_handler = preview_handler
        self._trading_client = trading_client

    def execute(self, command: SubmitOrderCommand) -> Order:
        logger.debug("Handling SubmitOrderCommand for %s", command.order_request.symbol)
        preview = self._preview_handler.execute(command.order_request)
        return self._trading_client.place_order(preview.order)
