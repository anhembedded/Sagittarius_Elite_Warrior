"""`EPIC-021G` — `ExecuteOrderCommandHandler`: the one place in this app
allowed to construct `FuturesTradingClient` with `OrderSubmissionMode.LIVE`.
Guarded by `tests/unit/infrastructure/binance/
test_order_submission_mode_live_is_restricted.py`, which allowlists this
exact file — nowhere else."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.domain.policies.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.domain.trading.policies.trading_limit_policy import (
    TradingLimitContext,
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_trading_client import (
    FuturesTradingClient,
)

logger = logging.getLogger("App.CommandHandler")


class ExecuteOrderCommandHandler(
    ICommandHandler[ExecuteOrderCommand, ExecuteOrderResult]
):
    def __init__(
        self,
        trading_venue: TradingVenue,
        session_state: TradingSessionState,
        account_reader: ITradingAccountReader,
        preview_handler: PreviewOrderQueryHandler,
        limits_policy: TradingLimitPolicy,
        session_factory: ExchangeSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        metadata_provider: IMarketMetadataProvider,
    ) -> None:
        self._trading_venue = trading_venue
        self._session_state = session_state
        self._account_reader = account_reader
        self._preview_handler = preview_handler
        self._limits_policy = limits_policy
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._metadata_provider = metadata_provider

    def execute(self, command: ExecuteOrderCommand) -> ExecuteOrderResult:
        logger.debug(
            "Handling ExecuteOrderCommand for %s (live=%s)",
            command.order_request.symbol,
            command.live,
        )

        gate = self._first_blocked_safety_gate()
        if gate is not None:
            return ExecuteOrderResult(gate, None, (), None)

        preview = self._preview_handler.execute(command.order_request)

        # `BUG-090` — refuse before the four session limits, and well
        # before any network call, rather than letting an order this
        # app's own normalization already knows is too small round-trip
        # to the exchange for a `-4164` rejection.
        if preview.notional_check is NotionalCheck.INSUFFICIENT:
            return ExecuteOrderResult(
                ExecuteOrderNotionalRejection.MIN_NOTIONAL, preview, (), None
            )

        symbol = command.order_request.symbol
        now = datetime.now(UTC)
        context = TradingLimitContext(
            orders_sent_this_session=self._session_state.orders_sent_this_session,
            order_notional=preview.estimated_notional,
            open_position_count_for_symbol=self._session_state.open_position_count(
                symbol
            ),
            time_since_last_order_for_symbol=self._session_state.time_since_last_order(
                symbol, now
            ),
        )
        checks = self._limits_policy.evaluate(context)
        violation = next((c.violation for c in checks if not c.passed), None)
        if violation is not None:
            return ExecuteOrderResult(violation, preview, checks, None, context)

        if not command.live:
            return ExecuteOrderResult(None, preview, checks, None, context)

        trading_client = FuturesTradingClient(
            self._session_factory,
            self._credentials_provider,
            self._metadata_provider,
            OrderSubmissionMode.LIVE,
        )
        submitted_order = trading_client.place_order(preview.order)
        self._session_state.record_order_sent(symbol, now)
        logger.info(
            "Live order submitted: %s %s", symbol, submitted_order.client_order_id
        )
        return ExecuteOrderResult(None, preview, checks, submitted_order, context)

    def _first_blocked_safety_gate(self) -> ExecuteOrderSafetyGate | None:
        if self._trading_venue is not TradingVenue.FUTURES_TESTNET:
            return ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
        if not self._session_state.enabled:
            return ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
        status = self._account_reader.check_connection()
        if not status.reachable or status.failure is not None:
            return ExecuteOrderSafetyGate.CONNECTION_NOT_READY
        return None
