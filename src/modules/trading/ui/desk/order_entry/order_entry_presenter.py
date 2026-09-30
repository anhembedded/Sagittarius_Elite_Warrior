"""`EPIC-028H` — drives one order panel: reads the symbol's terms and the
account, and places an order through the one submission path.

@details An order goes preview → confirm → submit:
1. **Preview** (worker): `IOrderSubmission.preview()` rounds the typed amount
   and price to the symbol's filters and checks the minimum notional, with
   no order sent.
2. **Confirm** (UI thread): the dialog shows the rounded order
   (`order_confirmation.py`); Cancel ends the attempt.
3. **Submit** (worker): the real position (and, on Spot, the real holding)
   is read fresh and turned into a side and `reduce_only` by
   `manual_order_intent_for()`, the same rule the Dev Board's card uses, then
   `IOrderSubmission.submit(live=True)` runs every safety gate and limit.

Every port here is the desk's own venue's (`VenueTradingPorts`), so the
Spot desk's panel cannot reach Futures. Each background read carries an
action id from an `ActionOwnershipTracker`; an answer for a superseded load
or order is logged and dropped (`async-ui-action-rule.md` §1).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from decimal import Decimal

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
    manual_order_intent_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_confirmation import (
    ConfirmOrder,
    build_confirmation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    OrderEntryContext,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Trading.OrderEntry")

_LOAD = "load"
_ORDER = "order"

_ORDER_SIDE = {EntrySide.BUY: OrderSide.BUY, EntrySide.SELL: OrderSide.SELL}
_DIRECTION = {
    EntrySide.BUY: ManualOrderDirection.LONG,
    EntrySide.SELL: ManualOrderDirection.SHORT,
}


class OrderEntryPresenter(QObject):
    """@brief One order panel's reads and its preview → confirm → submit."""

    _loaded = Signal(object)
    _previewed = Signal(object)
    _submitted = Signal(object)

    def __init__(
        self,
        view_model: OrderEntryViewModel,
        ports: VenueTradingPorts,
        thread_manager: IThreadManager,
        confirm: ConfirmOrder,
    ) -> None:
        super().__init__(view_model)
        if ports.venue is not view_model.profile.venue:
            raise ValueError(
                f"the {view_model.profile.title} panel was given "
                f"{ports.venue.value}'s ports"
            )
        self._vm = view_model
        self._ports = ports
        self._threads = thread_manager
        self._confirm = confirm
        self._loads: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._orders: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._loaded.connect(self._on_loaded)
        self._previewed.connect(self._on_previewed)
        self._submitted.connect(self._on_submitted)
        view_model.submitRequested.connect(self._on_submit_requested)

    # -- the host ------------------------------------------------------ #

    def show_symbol(self, symbol: str) -> None:
        """Switches the panel to `symbol` and reads its terms."""
        self._vm.begin_symbol(symbol)
        self.refresh()

    def refresh(self) -> None:
        """Re-reads the terms and balances, after a fill for instance."""
        symbol = self._vm.order_symbol
        if not symbol:
            return
        action = self._loads.begin_action(_LOAD, symbol, None)
        self._threads.submit(self._run_load, action.action_id, symbol)

    def update_last_price(self, price: Decimal | None) -> None:
        self._vm.set_last_price(price)

    # -- load ---------------------------------------------------------- #

    def _run_load(self, action_id: int, symbol: str) -> None:
        try:
            terms = self._ports.order_entry_terms.terms_for(symbol)
            status = self._ports.account_snapshot.check_connection()
            context = self._context_for(symbol, terms, status)
            self._loaded.emit((action_id, context, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._loaded.emit((action_id, None, str(exc)))

    def _context_for(
        self, symbol: str, terms: OrderEntryTerms, status: ExchangeConnectionStatus
    ) -> OrderEntryContext:
        quote = self._vm.profile.quote_asset
        base = symbol.removesuffix(quote)
        summary = status.summary if status.reachable else None
        holdings = status.holdings if status.reachable else None
        free_base: Decimal | None = None
        if holdings is not None:
            held = next((h for h in holdings if h.asset == base), None)
            free_base = held.free if held is not None else Decimal(0)
        return OrderEntryContext(
            symbol=symbol,
            base_asset=base,
            quote_asset=quote,
            terms=terms,
            available_quote=summary.available_balance if summary else None,
            free_base=free_base,
        )

    def _on_loaded(self, payload: tuple) -> None:
        action_id, context, error = payload
        if not self._loads.is_current_pending(action_id, _LOAD):
            self._loads.log_stale_callback("_on_loaded", action_id, _LOAD)
            return
        if context is None:
            self._loads.finish_action(action_id, ActionOutcome.FAILED)
            logger.warning(
                "Order panel could not read %s: %s", self._vm.order_symbol, error
            )
            self._vm.show_error(f"Could not read {self._vm.order_symbol}: {error}")
            return
        self._loads.finish_action(action_id, ActionOutcome.SUCCEEDED)
        self._vm.set_context(context)

    # -- preview → confirm → submit ------------------------------------ #

    def _on_submit_requested(self, side_value: str) -> None:
        if self._orders.active_outcome is ActionOutcome.PENDING:
            self._vm.show_result("An order is already being placed.", is_error=True)
            return
        side = EntrySide(side_value)
        figures = self._vm.figures(side)
        if figures is None or figures.problem is not None or figures.price is None:
            reason = figures.problem if figures is not None else "Still loading."
            self._vm.show_result(reason or "Enter a price.", is_error=True)
            return
        request = OrderRequest(
            symbol=self._vm.order_symbol,
            side=_ORDER_SIDE[side],
            order_type=self._vm.order_type,
            quantity=self._vm.entry(side).quantity or Decimal(0),
            reference_price=figures.price,
        )
        action = self._orders.begin_action(_ORDER, side.value, None)
        self._vm.set_busy(True, "Checking the order...")
        self._threads.submit(self._run_preview, action.action_id, side, request)

    def _run_preview(
        self, action_id: int, side: EntrySide, request: OrderRequest
    ) -> None:
        try:
            preview = self._ports.order_submission.preview(request)
            self._previewed.emit((action_id, side, request, preview, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self._previewed.emit((action_id, side, request, None, str(exc)))

    def _on_previewed(self, payload: tuple) -> None:
        action_id, side, request, preview, error = payload
        if not self._orders.is_current_pending(action_id, _ORDER):
            self._orders.log_stale_callback("_on_previewed", action_id, _ORDER)
            return
        refusal = self._preview_refusal(preview, error)
        if refusal is not None:
            self._orders.finish_action(action_id, ActionOutcome.FAILED)
            self._vm.show_result(refusal, is_error=True)
            return
        price = preview.order.price or request.reference_price
        context = self._vm.context
        fee_rate = context.terms.commission.taker if context else Decimal(0)
        confirmation = build_confirmation(
            preview,
            side_label=self._vm.profile.side_label(side),
            venue_label=self._ports.venue.value.replace("_", " ").title(),
            base_asset=context.base_asset if context else "",
            quote_asset=self._vm.profile.quote_asset,
            price=price,
            fee_rate=fee_rate,
        )
        if not self._confirm(confirmation):
            self._orders.finish_action(action_id, ActionOutcome.CANCELLED)
            self._vm.show_result("Order not sent.", is_error=False)
            return
        self._vm.set_busy(True, "Sending order...")
        rounded = replace(
            request, quantity=preview.order.quantity, reference_price=price
        )
        self._threads.submit(self._run_submit, action_id, side, rounded)

    @staticmethod
    def _preview_refusal(preview: OrderPreview | None, error: str | None) -> str | None:
        if preview is None:
            return f"The order could not be checked: {error}"
        if preview.order.quantity <= 0:
            return f"The amount is below one lot of {preview.step_size}."
        if preview.notional_check is NotionalCheck.INSUFFICIENT:
            return (
                "The order is worth less than the symbol's minimum of "
                f"{preview.min_notional}."
            )
        return None

    def _run_submit(
        self, action_id: int, side: EntrySide, request: OrderRequest
    ) -> None:
        """@param request The previewed order, already rounded; its side is
        replaced by the intent read here, fresh."""
        try:
            symbol = request.symbol
            market = self._vm.profile.market_type
            account = self._ports.account_snapshot
            position = next(
                (p for p in account.open_positions() if p.symbol == symbol), None
            )
            holding = None
            if market is MarketType.SPOT:
                base = symbol.removesuffix(self._vm.profile.quote_asset)
                holdings = account.check_connection().holdings or ()
                holding = next((h for h in holdings if h.asset == base), None)
            intent = manual_order_intent_for(
                _DIRECTION[side], position, market, holding
            )
            result = self._ports.order_submission.submit(
                replace(request, side=intent.side, reduce_only=intent.reduce_only),
                live=True,
            )
            self._submitted.emit((action_id, side, result, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self._submitted.emit((action_id, side, None, str(exc)))

    def _on_submitted(self, payload: tuple) -> None:
        action_id, side, result, error = payload
        if not self._orders.is_current_pending(action_id, _ORDER):
            self._orders.log_stale_callback("_on_submitted", action_id, _ORDER)
            return
        message, placed = self._result_text(result, error)
        self._orders.finish_action(
            action_id, ActionOutcome.SUCCEEDED if placed else ActionOutcome.FAILED
        )
        logger.info("Order panel %s order: %s", side.value, message)
        self._vm.show_result(message, is_error=not placed)
        if placed:
            self._vm.clear_amount(side)
            self.refresh()

    @staticmethod
    def _result_text(
        result: ExecuteOrderResult | None, error: str | None
    ) -> tuple[str, bool]:
        if result is None:
            return f"The order failed: {error}", False
        if result.blocked:
            return format_execute_order_block_reason(result.blocked_by), False
        order = result.submitted_order
        if order is None:
            return "The order was not sent.", False
        return f"Order placed ({order.client_order_id}).", True
