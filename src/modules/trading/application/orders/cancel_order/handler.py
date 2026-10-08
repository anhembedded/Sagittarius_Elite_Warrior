"""`EPIC-024B` §0 — `CancelOrderCommandHandler`: the first place in this
app that cancels exactly ONE order, not the whole account
(`EmergencyStopCommand`'s job). Gated behind the same three safety checks
`ExecuteOrderCommandHandler` uses — cancelling is real, signed exchange
activity, not a read.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order.command import (
    CancelOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.connection_gate import (
    connection_block,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)

logger = logging.getLogger("App.CommandHandler")


class CancelOrderCommandHandler(ICommandHandler[CancelOrderCommand, CancelOrderResult]):
    """@details `EPIC-028B` — cancels on `command.venue` only, through that
    venue's own session state, connection and client."""

    def __init__(self, scopes: VenueTradingScopes) -> None:
        self._scopes = scopes

    def execute(self, command: CancelOrderCommand) -> CancelOrderResult:
        logger.debug(
            "Handling CancelOrderCommand for %s %s on %s",
            command.symbol,
            command.client_order_id,
            command.venue.value,
        )
        if not command.venue.supports_order_submission:
            return CancelOrderResult(
                ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED, None
            )
        scope = self._scopes.get(command.venue)
        gate = self._first_blocked_safety_gate(scope)
        if gate is not None:
            return CancelOrderResult(gate, None)

        # `OrderSubmissionMode` only gates `place_order()` — irrelevant to
        # a cancel, same reasoning `EnsureSessionReadyCommandHandler` already
        # gives for its own read-only calls through this same adapter.
        trading_client = scope.ports.client_factory.create(
            OrderSubmissionMode.VALIDATE_ONLY
        )
        cancelled_order = trading_client.cancel_order(
            command.symbol, command.client_order_id
        )
        logger.info(
            "Order cancelled on %s: %s %s",
            command.venue.value,
            command.symbol,
            command.client_order_id,
        )
        return CancelOrderResult(None, cancelled_order)

    @staticmethod
    def _first_blocked_safety_gate(
        scope: VenueTradingScope,
    ) -> ExecuteOrderSafetyGate | None:
        if not scope.session_state.enabled:
            return ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
        return connection_block(scope.ports.account_reader.check_connection())
