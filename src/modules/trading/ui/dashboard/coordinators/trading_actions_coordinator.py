"""`BOT-144` — Enable/Disable trading toggle, Emergency Stop, manual order
submission and per-order cancel, pulled out of `DashboardPresenter`.

@details Shape-matches this same screen's other Coordinators
(`SymbolOptionsCoordinator`/`LiveOrderBookCoordinator`/
`StrategyArmingCoordinator`/`IndicatorCoordinator`): a plain class, narrow
constructor-injected callables rather than the whole Presenter, no FSM state
and no action-id bookkeeping of its own (`async-ui-action-rule.md` §2) — the
three `ActionOwnershipTracker` instances are constructed and owned by
`DashboardPresenter`, handed in here exactly like `StrategyArmingCoordinator`
already receives `tracker=self._arm_tracker`.

Only the synchronous `request_*` orchestration (validate → track → submit to
`IThreadManager`) and the `run_*` background workers live here. The four
`_on_x_completed` handlers stay on `DashboardPresenter` — not for a Qt
threading reason (`Tasks/backlog/BOT-144_...md` §3.2 corrects an earlier,
disproven claim to that effect), but because each one calls
`tracker.finish_action(...)`/`is_current_pending(...)` and then touches
several more Presenter-owned collaborators
(`_view_model`/`_order_book`/`_append_log`/`_refresh_session_stats`) whose
combination is specific to *this* screen's completion handling, not a
reusable action shape — `async-ui-action-rule.md` §2's "one owner" rule
reads more naturally as the Presenter keeping the bookkeeping's read side too,
not just its construction.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
    manual_order_intent_for,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
        IAccountSnapshot,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
        IOrderSubmission,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
        ITradingSession,
    )
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


class TradingActionsCoordinator:
    """Enable/Disable trading, Emergency Stop, manual order submission and
    per-order cancel — the four action families `DashboardPresenter` already
    orchestrates its other Coordinators' worth of background work through,
    applied here for the first time."""

    def __init__(
        self,
        thread_manager: IThreadManager,
        trading_session: ITradingSession,
        order_submission: IOrderSubmission,
        account: IAccountSnapshot,
        toggle_tracker: ActionOwnershipTracker[str, None, None],
        emergency_stop_tracker: ActionOwnershipTracker[str, None, None],
        manual_order_tracker: ActionOwnershipTracker[str, None, None],
        toggle_action_kind: str,
        emergency_stop_action_kind: str,
        manual_order_action_kind: str,
        set_trading_state: Callable[[bool, bool], None],
        set_manual_order_state: Callable[[bool, str], None],
        append_log: Callable[[str], None],
        get_active_symbol: Callable[[], str],
        get_last_price: Callable[[str], Decimal | None],
        emit_enable_completed: Callable[[tuple], None],
        emit_disable_completed: Callable[[tuple], None],
        emit_emergency_stop_completed: Callable[[tuple], None],
        emit_manual_order_completed: Callable[[tuple], None],
        emit_cancel_order_completed: Callable[[tuple], None],
    ) -> None:
        self._thread_manager = thread_manager
        self._trading_session = trading_session
        self._order_submission = order_submission
        self._account = account
        self._toggle_tracker = toggle_tracker
        self._emergency_stop_tracker = emergency_stop_tracker
        self._manual_order_tracker = manual_order_tracker
        self._toggle_action_kind = toggle_action_kind
        self._emergency_stop_action_kind = emergency_stop_action_kind
        self._manual_order_action_kind = manual_order_action_kind
        self._set_trading_state = set_trading_state
        self._set_manual_order_state = set_manual_order_state
        self._append_log = append_log
        self._get_active_symbol = get_active_symbol
        self._get_last_price = get_last_price
        self._emit_enable_completed = emit_enable_completed
        self._emit_disable_completed = emit_disable_completed
        self._emit_emergency_stop_completed = emit_emergency_stop_completed
        self._emit_manual_order_completed = emit_manual_order_completed
        self._emit_cancel_order_completed = emit_cancel_order_completed

    # ------------------------------------------------------------------ #
    # Enable/Disable trading toggle
    # ------------------------------------------------------------------ #

    def request_toggle(self) -> None:
        # `BUG-089` (Trading's own precedent) — the toggle button is already
        # disabled by `busy=True` while Emergency Stop runs, but this is the
        # real guard: a click that slips through anyway must not begin a
        # new toggle action and, via the shared session state, race the
        # Emergency Stop already in flight.
        if self._emergency_stop_tracker.active_outcome is ActionOutcome.PENDING:
            self._append_log(
                "Emergency stop in progress — please wait for it to finish "
                "before enabling/disabling trading."
            )
            return
        action = self._toggle_tracker.begin_action(self._toggle_action_kind, None, None)
        currently_enabled = self._trading_session.snapshot().enabled
        self._set_trading_state(currently_enabled, True)
        if currently_enabled:
            self._thread_manager.submit(self.run_disable, action.action_id)
        else:
            self._thread_manager.submit(self.run_enable, action.action_id)

    def run_enable(self, action_id: int) -> None:
        try:
            result = self._trading_session.enable()
            self._emit_enable_completed((action_id, result, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._emit_enable_completed((action_id, None, str(exc)))

    def run_disable(self, action_id: int) -> None:
        try:
            self._trading_session.disable()
            self._emit_disable_completed((action_id, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self._emit_disable_completed((action_id, str(exc)))

    # ------------------------------------------------------------------ #
    # Emergency Stop
    # ------------------------------------------------------------------ #

    def request_emergency_stop(self) -> None:
        # Deliberately not `@safe_ui_action` on the Presenter's own Slot that
        # calls this — Emergency Stop's whole point is that a failure must be
        # seen, never silently dropped mid-flow (ONBOARDING.md §8, bẫy 8).
        try:
            # `BUG-089` debounce (Trading's own precedent) — the Emergency
            # Stop button is deliberately never disabled (it must always be
            # clickable), so a second click while one is still in flight is
            # only caught here: without this, it would submit a second,
            # independent `ITradingSession.emergency_stop()` against the
            # live exchange, racing the first one's own cancel/close calls.
            if self._emergency_stop_tracker.active_outcome is ActionOutcome.PENDING:
                self._append_log(
                    "Emergency stop in progress — the request has already been sent, please wait."
                )
                return
            action = self._emergency_stop_tracker.begin_action(
                self._emergency_stop_action_kind, None, None
            )
            # Disables the toggle button for the duration — Enable/Disable
            # must not race Emergency Stop's own `disable()`/`place_order()`
            # calls.
            self._set_trading_state(self._trading_session.snapshot().enabled, True)
            self._append_log("Emergency stop in progress...")
            self._thread_manager.submit(self.run_emergency_stop, action.action_id)
        except Exception as exc:  # noqa: BLE001 - deliberately not @safe_ui_action, see this coordinator's own docstring
            self._set_trading_state(self._trading_session.snapshot().enabled, False)
            self._append_log(f"Error during emergency stop: {exc}")

    def run_emergency_stop(self, action_id: int) -> None:
        try:
            result = self._trading_session.emergency_stop()
            self._emit_emergency_stop_completed((action_id, result, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self._emit_emergency_stop_completed((action_id, None, str(exc)))

    # ------------------------------------------------------------------ #
    # Manual trading card (`EPIC-024B`)
    # ------------------------------------------------------------------ #

    def request_manual_order(
        self, direction_text: str, quantity: float, order_type_text: str, price: float
    ) -> None:
        if self._manual_order_tracker.active_outcome is ActionOutcome.PENDING:
            self._append_log("Already processing a manual order — please wait.")
            return
        try:
            direction = ManualOrderDirection(direction_text)
            order_type = OrderType[order_type_text]
        except (ValueError, KeyError):
            self._append_log(
                f"Invalid manual order parameters: {direction_text}/{order_type_text}"
            )
            return
        quantity_decimal = Decimal(str(quantity))
        if quantity_decimal <= 0:
            self._append_log("Manual order quantity must be greater than 0.")
            return

        symbol = self._get_active_symbol()
        reference_price: Decimal | None
        if order_type is OrderType.LIMIT:
            reference_price = Decimal(str(price))
            if reference_price <= 0:
                self._append_log("Limit order price must be greater than 0.")
                return
        else:
            reference_price = self._get_last_price(symbol)
            if reference_price is None:
                self._append_log(
                    "No market price available for this symbol yet — wait for "
                    "live data and try again."
                )
                return

        action = self._manual_order_tracker.begin_action(
            self._manual_order_action_kind, None, None
        )
        self._set_manual_order_state(True, "Sending order...")
        self._thread_manager.submit(
            self.run_manual_order,
            action.action_id,
            symbol,
            direction,
            quantity_decimal,
            order_type,
            reference_price,
        )

    def run_manual_order(
        self,
        action_id: int,
        symbol: str,
        direction: ManualOrderDirection,
        quantity: Decimal,
        order_type: OrderType,
        reference_price: Decimal,
    ) -> None:
        try:
            # `PRO-003` §4.1.2's hard block on the strategy's armed symbol is
            # **not** here any more (`EPIC-025` PR 2.1f) — see this method's
            # pre-extraction history in `dashboard_presenter.py`'s own git
            # log for the full reasoning; the rule now lives on the order
            # path itself (`ExecuteOrderSafetyGate.SYMBOL_LEASED`), so every
            # caller inherits it.
            #
            # `EPIC-024B` §2 — read the REAL current position fresh, every
            # attempt; never guessed, never remembered from a prior click
            # (see `manual_order_intent_for()`'s own docstring).
            positions = self._account.open_positions()
            current_position = next((p for p in positions if p.symbol == symbol), None)
            intent = manual_order_intent_for(direction, current_position)
            result = self._order_submission.submit(
                OrderRequest(
                    symbol=symbol,
                    side=intent.side,
                    order_type=order_type,
                    quantity=quantity,
                    reference_price=reference_price,
                    reduce_only=intent.reduce_only,
                ),
                live=True,
            )
            self._emit_manual_order_completed((action_id, result, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._emit_manual_order_completed((action_id, None, str(exc)))

    # ------------------------------------------------------------------ #
    # Per-order cancel (`EPIC-024B` §0) — no tracker: unlike the manual
    # order card (one card, one pending attempt at a time), cancelling
    # order A and cancelling a different order B on another row are
    # genuinely independent actions.
    # ------------------------------------------------------------------ #

    def request_cancel_order(self, symbol: str, client_order_id: str) -> None:
        self._append_log(f"Cancelling order {client_order_id} ({symbol})...")
        self._thread_manager.submit(self.run_cancel_order, symbol, client_order_id)

    def run_cancel_order(self, symbol: str, client_order_id: str) -> None:
        try:
            result = self._order_submission.cancel(symbol, client_order_id)
            self._emit_cancel_order_completed((symbol, client_order_id, result, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self._emit_cancel_order_completed((symbol, client_order_id, None, str(exc)))
