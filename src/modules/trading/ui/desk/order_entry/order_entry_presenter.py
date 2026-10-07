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
   `manual_order_intent_for()`, the same rule the Dev Board's card used, then
   `IOrderSubmission.submit(live=True)` runs every safety gate and limit.

Every port here is the desk's own venue's (`VenueTradingPorts`), so the
Spot desk's panel cannot reach Futures. Each background read carries an
action id from an `ActionOwnershipTracker`; an answer for a superseded load
or order is logged and dropped (`async-ui-action-rule.md` §1).

`EPIC-028I`: on a desk with leverage the load also reads the Futures
context (`read_futures_context`) and shows its leverage and margin mode on
the chips, which `FuturesSettingsChanger` sends; the request carries the
chosen time in force and reduce-only; an entry placed with TP/SL on is
announced on `entryPlaced` with its levels, for the desk's
`ProtectiveOrderFollower` to protect once the fill is reported.

`EPIC-028O`: the load also reads the app's per-order notional limit, which
caps every maximum; the request carries a stop-limit's stop and last price
and a quote-sized buy's total; the BBO button's book read is
`BestPriceFiller`'s, dropped when the symbol changes under it.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from decimal import Decimal

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    INotifier,
    failure_detail,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.protective_levels import (
    ProtectiveLevels,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
    manual_order_intent_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.best_price_filler import (
    BestPriceFiller,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.futures_context_reader import (
    read_futures_context,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.futures_settings_changer import (
    FuturesSettingsChanger,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_confirmation import (
    ConfirmOrder,
    build_confirmation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_failures import (
    OrderEntryFailures,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_requests import (
    order_entry_context_for,
    order_request_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_outcome_text import (
    preview_refusal,
    result_text,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_failure import (
    submit_failure_of,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Trading.OrderEntry")

_LOAD = "load"
_ORDER = "order"

_DIRECTION = {
    EntrySide.BUY: ManualOrderDirection.LONG,
    EntrySide.SELL: ManualOrderDirection.SHORT,
}


class OrderEntryPresenter(QObject):
    """@brief One order panel's reads and its preview → confirm → submit."""

    #: `(Order, ProtectiveLevels)`: an entry placed with TP/SL on, to be
    #: protected once it fills (`EPIC-028I`).
    entryPlaced = Signal(object)
    #: `Order`: every order the venue accepted, as it answered (`EPIC-028K`).
    orderAccepted = Signal(object)

    _loaded = Signal(object)
    _previewed = Signal(object)
    _submitted = Signal(object)

    def __init__(
        self,
        view_model: OrderEntryViewModel,
        ports: VenueTradingPorts,
        thread_manager: IThreadManager,
        confirm: ConfirmOrder,
        notifier: INotifier,
    ) -> None:
        super().__init__(view_model)
        if ports.venue is not view_model.profile.venue:
            raise ValueError(
                f"the {view_model.profile.title} panel was given "
                f"{ports.venue.value}'s ports"
            )
        self._vm = view_model
        self._writes = view_model.presenter_side()
        self._ports = ports
        self._threads = thread_manager
        self._confirm = confirm
        self._loads: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._orders: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._failures = OrderEntryFailures(notifier, ports.venue, self._writes)
        self._best_price = BestPriceFiller(
            view_model,
            ports.order_entry_terms,
            thread_manager,
            notifier,
            ports.venue,
        )
        self._protection: ProtectiveLevels | None = None
        if view_model.profile.futures_controls:
            FuturesSettingsChanger(
                view_model,
                ports.futures_settings,
                thread_manager,
                self.refresh,
                notifier,
                ports.venue,
            )
        self._loaded.connect(self._on_loaded)
        self._previewed.connect(self._on_previewed)
        self._submitted.connect(self._on_submitted)
        view_model.submitRequested.connect(self._on_submit_requested)

    # -- the host ------------------------------------------------------ #

    def show_symbol(self, symbol: str) -> None:
        """Switches the panel to `symbol` and reads its terms."""
        self._best_price.drop_pending()
        self._writes.begin_symbol(symbol)
        self.refresh()

    def refresh(self) -> None:
        """Re-reads the terms and balances, after a fill for instance."""
        symbol = self._vm.order_symbol
        if not symbol:
            return
        action = self._loads.begin_action(_LOAD, symbol, None)
        self._threads.submit(self._run_load, action.action_id, symbol)

    def update_last_price(self, price: Decimal | None) -> None:
        self._writes.set_last_price(price)

    # -- load ---------------------------------------------------------- #

    def _run_load(self, action_id: int, symbol: str) -> None:
        try:
            terms = self._ports.order_entry_terms.terms_for(symbol)
            status = self._ports.account_snapshot.check_connection()
            limit = self._ports.order_entry_terms.order_notional_limit()
            context = order_entry_context_for(
                self._vm.profile, symbol, terms, status, limit
            )
            futures = (
                read_futures_context(
                    self._ports.order_entry_terms,
                    self._ports.account_snapshot,
                    symbol,
                    status,
                )
                if self._vm.profile.futures_controls
                else None
            )
            self._loaded.emit((action_id, replace(context, futures=futures), None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._loaded.emit((action_id, None, failure_detail(exc)))

    def _on_loaded(self, payload: tuple) -> None:
        action_id, context, detail = payload
        if not self._loads.is_current_pending(action_id, _LOAD):
            self._loads.log_stale_callback("_on_loaded", action_id, _LOAD)
            return
        if context is None:
            self._loads.finish_action(action_id, ActionOutcome.FAILED)
            logger.warning(
                "Order panel could not read %s: %s", self._vm.order_symbol, detail
            )
            self._failures.terms_unread(self._vm.order_symbol, detail, self.refresh)
            return
        self._loads.finish_action(action_id, ActionOutcome.SUCCEEDED)
        self._failures.terms_read()
        self._writes.set_context(context)
        self._vm.options.show_setting(
            context.futures.setting if context.futures else None
        )

    # -- preview → confirm → submit ------------------------------------ #

    def _on_submit_requested(self, side_value: str) -> None:
        if self._orders.active_outcome is ActionOutcome.PENDING:
            self._writes.show_result("An order is already being placed.", is_error=True)
            return
        side = EntrySide(side_value)
        figures = self._vm.figures(side)
        if figures is None or figures.problem is not None or figures.price is None:
            reason = figures.problem if figures is not None else "Still loading."
            self._writes.show_result(reason or "Enter a price.", is_error=True)
            return
        request = order_request_for(self._vm, side, figures, figures.price)
        self._protection = (
            None if request.reduce_only else self._vm.options.protection(side)
        )
        action = self._orders.begin_action(_ORDER, side.value, None)
        self._writes.set_busy(True, "Checking the order...")
        self._threads.submit(self._run_preview, action.action_id, side, request)

    def _run_preview(
        self, action_id: int, side: EntrySide, request: OrderRequest
    ) -> None:
        try:
            preview = self._ports.order_submission.preview(request)
            self._previewed.emit((action_id, side, request, preview, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self._previewed.emit((action_id, side, request, None, failure_detail(exc)))

    def _on_previewed(self, payload: tuple) -> None:
        action_id, side, request, preview, detail = payload
        if not self._orders.is_current_pending(action_id, _ORDER):
            self._orders.log_stale_callback("_on_previewed", action_id, _ORDER)
            return
        if preview is None:
            self._orders.finish_action(action_id, ActionOutcome.FAILED)
            logger.warning("Order panel could not check the order: %s", detail)
            self._failures.preview_failed(detail)
            return
        context = self._vm.context
        limit = context.notional_limit if context else None
        refusal = preview_refusal(preview, limit)
        if refusal is not None:
            self._orders.finish_action(action_id, ActionOutcome.FAILED)
            self._writes.show_result(refusal, is_error=True)
            return
        price = preview.order.price or request.reference_price
        fee_rate = context.terms.commission.taker if context else Decimal(0)
        confirmation = build_confirmation(
            preview,
            side_label=self._vm.profile.side_label(side),
            venue_label=self._ports.venue.display_name,
            base_asset=context.base_asset if context else "",
            quote_asset=self._vm.profile.quote_asset,
            price=price,
            fee_rate=fee_rate,
        )
        if not self._confirm(confirmation):
            self._orders.finish_action(action_id, ActionOutcome.CANCELLED)
            self._writes.show_result("Order not sent.", is_error=False)
            return
        self._writes.set_busy(True, "Sending order...")
        rounded = replace(
            request, quantity=preview.order.quantity, reference_price=price
        )
        self._threads.submit(self._run_submit, action_id, side, rounded)

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
            # The box only ever narrows: an order the position makes reducing
            # stays so, and a ticked box makes any order reduce-only.
            reduce_only = intent.reduce_only or request.reduce_only
            result = self._ports.order_submission.submit(
                replace(request, side=intent.side, reduce_only=reduce_only),
                live=True,
            )
            self._submitted.emit((action_id, side, result, None, reduce_only))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            failure = submit_failure_of(exc)
            self._submitted.emit((action_id, side, None, failure, False))

    def _on_submitted(self, payload: tuple) -> None:
        action_id, side, result, failure, reduced = payload
        if not self._orders.is_current_pending(action_id, _ORDER):
            self._orders.log_stale_callback("_on_submitted", action_id, _ORDER)
            return
        if result is None:
            self._orders.finish_action(action_id, ActionOutcome.FAILED)
            logger.warning(
                "Order panel %s order failed (%s): %s",
                side.value,
                failure.kind.value,
                failure.detail,
            )
            self._failures.submit_failed(failure)
            return
        message, placed = result_text(result)
        self._orders.finish_action(
            action_id, ActionOutcome.SUCCEEDED if placed else ActionOutcome.FAILED
        )
        logger.info("Order panel %s order: %s", side.value, message)
        self._writes.show_result(message, is_error=not placed)
        if not placed:
            self._failures.order_refused(message)
        if placed:
            if result is not None and result.submitted_order is not None:
                self.orderAccepted.emit(result.submitted_order)
            self._announce_protection(result, reduced)
            self._writes.clear_amount(side)
            self.refresh()

    def _announce_protection(
        self, result: ExecuteOrderResult | None, reduced: bool
    ) -> None:
        """@param reduced Whether the order sent was reduce-only: it closes
        a position, so there is no new one to protect."""
        levels, self._protection = self._protection, None
        order = result.submitted_order if result else None
        if levels is None or order is None or reduced:
            return
        self.entryPlaced.emit((order, levels))
        self._writes.show_result(
            f"Order placed ({order.client_order_id}); TP/SL follow once it fills.",
            is_error=False,
        )
