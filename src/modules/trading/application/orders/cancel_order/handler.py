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
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.CommandHandler")


class CancelOrderCommandHandler(ICommandHandler[CancelOrderCommand, CancelOrderResult]):
    def __init__(
        self,
        trading_venue: TradingVenue,
        session_state: TradingSessionState,
        account_reader: ITradingAccountReader,
        trading_client_factory: ITradingClientFactory,
    ) -> None:
        self._trading_venue = trading_venue
        self._session_state = session_state
        self._account_reader = account_reader
        self._trading_client_factory = trading_client_factory

    def execute(self, command: CancelOrderCommand) -> CancelOrderResult:
        logger.debug(
            "Handling CancelOrderCommand for %s %s",
            command.symbol,
            command.client_order_id,
        )
        gate = self._first_blocked_safety_gate()
        if gate is not None:
            return CancelOrderResult(gate, None)

        # `OrderSubmissionMode` only gates `place_order()` — irrelevant to
        # a cancel, same reasoning `EnableTradingCommandHandler` already
        # gives for its own read-only calls through this same adapter.
        trading_client = self._trading_client_factory.create(
            OrderSubmissionMode.VALIDATE_ONLY
        )
        cancelled_order = trading_client.cancel_order(
            command.symbol, command.client_order_id
        )
        logger.info("Order cancelled: %s %s", command.symbol, command.client_order_id)
        return CancelOrderResult(None, cancelled_order)

    def _first_blocked_safety_gate(self) -> ExecuteOrderSafetyGate | None:
        if self._trading_venue is not TradingVenue.FUTURES_TESTNET:
            return ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
        if not self._session_state.enabled:
            return ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
        status = self._account_reader.check_connection()
        if not status.reachable or status.failure is not None:
            return ExecuteOrderSafetyGate.CONNECTION_NOT_READY
        return None
