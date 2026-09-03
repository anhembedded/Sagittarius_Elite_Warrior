"""`EPIC-021K` §2.2 — `EmergencyStopCommandHandler`: the second file this
app allows to construct `FuturesTradingClient` with
`OrderSubmissionMode.LIVE` (see `ExecuteOrderCommandHandler`'s own
docstring for the first, and
`tests/unit/infrastructure/binance/test_order_submission_mode_live_is_restricted.py`
for the guard listing both by name).

@details Does **not** go through `ExecuteOrderCommand`/`DisableTradingCommand`
for its own steps, on purpose:

- `ExecuteOrderCommandHandler._first_blocked_safety_gate()` refuses
  whenever `not session_state.enabled` — and step 1 here disables trading
  *before* step 3 needs to place closing orders, so routing step 3 through
  `ExecuteOrderCommand` would make it refuse every single time, the exact
  opposite of what an emergency close needs.
- Reusing `DisableTradingCommandHandler`'s logic inline (rather than
  dispatching that command) matches this app's existing pattern of
  handlers taking shared services as direct constructor dependencies
  (`ExecuteOrderCommandHandler` does the same for `TradingSessionState`),
  not calling one handler from another through the dispatcher.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.emergency_stop.result import (
    EmergencyStopResult,
    EmergencyStopStepResult,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_trading_client import (
    FuturesTradingClient,
)

logger = logging.getLogger("App.CommandHandler")


class EmergencyStopCommandHandler(
    ICommandHandler[EmergencyStopCommand, EmergencyStopResult]
):
    """
    @brief Handler for `EmergencyStopCommand` — three steps, always
    attempted in this exact order (`EPIC-021K` §2.2):

    1. Disable trading — blocks new orders *first*; reversing this order
       would mean an order could still slip in while orders are being
       cancelled and positions closed.
    2. Cancel every open order, whole-account (`ITradingClient.
       get_open_orders()` takes no symbol; `cancel_all_orders()` is
       per-symbol, so this groups by symbol first).
    3. Close every open position with a `MARKET` `reduce_only` order in
       the opposite direction.

    Never gated on `TradingVenue`/connection readiness — same reasoning
    `DisableTradingCommandHandler` documents for step 1: an emergency stop
    must always be attempted. A step's own API calls failing (network,
    exchange rejection, insufficient margin) is reported through that
    step's own `EmergencyStopStepResult`, not raised — one step failing
    must never prevent the next one from being attempted.
    """

    def __init__(
        self,
        session_state: TradingSessionState,
        user_data_stream: IUserDataStream,
        session_factory: ExchangeSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        metadata_provider: IMarketMetadataProvider,
    ) -> None:
        self._session_state = session_state
        self._user_data_stream = user_data_stream
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._metadata_provider = metadata_provider

    def execute(self, command: EmergencyStopCommand) -> EmergencyStopResult:
        logger.warning("Handling EmergencyStopCommand")

        trading_disabled = self._disable_trading()

        trading_client = FuturesTradingClient(
            self._session_factory,
            self._credentials_provider,
            self._metadata_provider,
            OrderSubmissionMode.LIVE,
        )
        orders_cancelled = self._cancel_all_orders(trading_client)
        positions_closed = self._close_all_positions(trading_client)
        final_positions, final_open_orders, final_state_confirmed = (
            self._read_final_state(trading_client)
        )

        result = EmergencyStopResult(
            trading_disabled,
            orders_cancelled,
            positions_closed,
            final_positions,
            final_open_orders,
            final_state_confirmed,
        )
        if result.fully_succeeded:
            logger.warning(
                "Emergency stop completed: trading disabled, all orders "
                "cancelled, all positions closed."
            )
        else:
            logger.error("Emergency stop completed with failures: %s", result)
        return result

    def _disable_trading(self) -> EmergencyStopStepResult:
        try:
            self._session_state.disable()
            self._user_data_stream.stop()
            return EmergencyStopStepResult(True, "Giao dịch đã tắt.")
        except Exception as exc:  # noqa: BLE001 - report every failure, never let one abort the remaining steps
            return EmergencyStopStepResult(False, f"Lỗi khi tắt giao dịch: {exc}")

    def _cancel_all_orders(
        self, trading_client: ITradingClient
    ) -> EmergencyStopStepResult:
        try:
            open_orders = trading_client.get_open_orders()
        except Exception as exc:  # noqa: BLE001
            return EmergencyStopStepResult(False, f"Lỗi khi đọc lệnh chờ: {exc}")
        if not open_orders:
            return EmergencyStopStepResult(True, "Không có lệnh chờ nào.")

        symbols = sorted({order.symbol for order in open_orders})
        cancelled_count = 0
        for symbol in symbols:
            try:
                cancelled_count += len(trading_client.cancel_all_orders(symbol))
            except Exception as exc:  # noqa: BLE001
                remaining = len(open_orders) - cancelled_count
                return EmergencyStopStepResult(
                    False,
                    f"Đã huỷ {cancelled_count}/{len(open_orders)} lệnh chờ — "
                    f"lỗi ở {symbol}: {exc}. Còn {remaining} lệnh chưa huỷ.",
                )
        return EmergencyStopStepResult(True, f"Đã huỷ {cancelled_count} lệnh chờ.")

    def _close_all_positions(
        self, trading_client: ITradingClient
    ) -> EmergencyStopStepResult:
        try:
            positions = trading_client.get_positions()
        except Exception as exc:  # noqa: BLE001
            return EmergencyStopStepResult(False, f"Lỗi khi đọc vị thế: {exc}")
        if not positions:
            return EmergencyStopStepResult(True, "Không có vị thế nào đang mở.")

        closed_count = 0
        for position in positions:
            closing_side = (
                OrderSide.SELL if position.side is PositionSide.LONG else OrderSide.BUY
            )
            closing_order = Order(
                client_order_id=generate_client_order_id(),
                symbol=position.symbol,
                side=closing_side,
                order_type=OrderType.MARKET,
                quantity=abs(position.position_amt),
                reduce_only=True,
            )
            try:
                trading_client.place_order(closing_order)
                closed_count += 1
            except Exception as exc:  # noqa: BLE001
                remaining = len(positions) - closed_count
                return EmergencyStopStepResult(
                    False,
                    f"Đã đóng {closed_count}/{len(positions)} vị thế — lỗi ở "
                    f"{position.symbol}: {exc}. Còn {remaining} vị thế chưa đóng.",
                )
        return EmergencyStopStepResult(True, f"Đã đóng {closed_count} vị thế.")

    def _read_final_state(
        self, trading_client: ITradingClient
    ) -> tuple[tuple[LivePosition, ...], tuple[Order, ...], bool]:
        """@brief `BUG-093` — a best-effort read of the account's true
        state after the three steps above, regardless of their own
        outcome: `TradingPresenter` seeded its Positions/Open Orders
        tables before this command ran and has no other way to learn what
        actually happened — the user-data stream this screen otherwise
        relies on was already stopped in step 1.
        @return `(positions, open_orders, confirmed)` — `confirmed` is
        `False` only when this read itself failed; a caller must then
        treat the account's true state as unknown, never as "confirmed
        empty" from the accompanying empty tuples.
        """
        try:
            return (
                tuple(trading_client.get_positions()),
                tuple(trading_client.get_open_orders()),
                True,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort, report via the bool
            logger.error("Could not confirm final account state: %s", exc)
            return (), (), False
