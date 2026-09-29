import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.submit_order.command import (
    SubmitOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)

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

    `EPIC-028B` — validates against `command.venue`'s own client. A venue
    that cannot submit orders (`DISABLED`) raises `VenueNotEnabledError`
    before anything is built: this used to be an unbound `ITradingClient`
    at dispatch time, the same "fail loudly, never hand back a client
    nobody enabled" outcome, now named and per venue.
    """

    def __init__(
        self, preview_handler: PreviewOrderQueryHandler, contexts: IVenueContexts
    ) -> None:
        self._preview_handler = preview_handler
        self._contexts = contexts

    def execute(self, command: SubmitOrderCommand) -> Order:
        logger.debug(
            "Handling SubmitOrderCommand for %s on %s",
            command.order_request.symbol,
            command.venue.value,
        )
        if not command.venue.supports_order_submission:
            raise VenueNotEnabledError(command.venue, self._contexts.enabled())
        trading_client = self._contexts.get(command.venue).client_factory.create(
            OrderSubmissionMode.VALIDATE_ONLY
        )
        preview = self._preview_handler.execute(command.order_request)
        return trading_client.place_order(preview.order)
