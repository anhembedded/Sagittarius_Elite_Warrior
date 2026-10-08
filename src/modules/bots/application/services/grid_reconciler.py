"""`EPIC-029E` — bringing a restored Grid back in line with the exchange (ADR §3.3, D12).

A bot that was RUNNING or PAUSED when the app closed loads as RECOVERING and
places nothing. When the user enables trading on its venue, this runs, in the
ADR's order:

  1. **Claim the lease** under the bot's owner id (leases live in memory).
  2. **Register the budget**: trading derives the inventory from exchange
     evidence (D6). Refused (trading off again) → the bot stays RECOVERING.
  3. **Read the open orders carrying the bot's tag.**
  4. **Apply fills first.** (History that does not answer is a wait, not a
     fault: the bot stays RECOVERING naming it, and the next enable retries.)
     A saved order missing from the exchange is looked
     up in order history; what it executed beyond what the bot counted is
     applied as a fill (its counter order held), then the level empties if
     the order is over.
  5. **Then adopt.** A tagged order the saved ladder did not know — sent but
     never saved, because the app died between the submit and the write — is
     adopted at the level of its price, so that level is never placed twice.
     Two orders at one level, or one at no level, halts.
  6. **Check the inventory**: the saved inventory equals the derived one to
     within one step (`INVENTORY_MISMATCH`), and the account holds **at
     least** the derived inventory (`HOLDING_BELOW_INVENTORY`) — never an
     equality with the holding, which includes the user's own coins.
  7. **Persist, then transition**: `reconcile_ok` back to RUNNING or PAUSED,
     or `reconcile_mismatch` to HALTED, naming why.

`EPIC-035B` — the same steps 2–6 are `compare_with_exchange`, which
`GridStreamGap` runs for a **RUNNING or PAUSED** bot after a user-data-stream
gap: no lease claim and no transition, because the bot never left its state.

A fill applied from history is remembered by its trade ids (`AppliedFills`,
`EPIC-035P`), so the stream delivering it late does not count it twice.

History's order row carries no fee, so a missed fill takes its fees from the
order's trades, less what the bot already counted: Spot takes a buy's fee from
the base it bought, and the counter SELL may ask for no more than arrived. The
derivation in step 6 (which nets base-asset fees too) is the check that the
bot's inventory is still the exchange's.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    bot_owner_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_housekeeping import (
    GridHousekeeping,
    refusal_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    Halt,
    LadderRules,
    LevelEnd,
    LevelFill,
    adopted,
    on_end,
    on_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
    LevelOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

logger = logging.getLogger("App.Bots.GridExecutor")


@dataclass(frozen=True, slots=True)
class ReconcileMismatch:
    """A step found the exchange and the ladder disagree, and why."""

    reason: GridReason
    detail: str


@dataclass(frozen=True, slots=True)
class ReconcileWait:
    """The exchange did not answer a read: nothing was changed. What a
    RECOVERING bot shows while it waits for the next try."""

    reason: GridReason
    detail: str


class GridReconciler:
    """Reconciles a RECOVERING Grid (ends in its prior state or HALTED), or a
    running one after a stream gap (`EPIC-035B`)."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._housekeeping = GridHousekeeping(context)

    def run(self) -> None:
        state = self._context.state
        symbol = state.bot.definition.symbol
        if not self._context.session.claim_symbol(symbol, bot_owner_id(state.bot_id)):
            self._mismatch(GridReason.LEASE_HELD, f"{symbol} is held by another owner")
            return
        outcome = self.compare_with_exchange()
        if isinstance(outcome, ReconcileWait):
            state.update(state.runtime.with_reason(outcome.reason, outcome.detail))
        elif isinstance(outcome, ReconcileMismatch):
            self._mismatch(outcome.reason, outcome.detail)
        else:
            if outcome.reason is GridReason.RECOVERY_READ:
                # The boot report was a read; this reconcile is the answer.
                outcome = replace(outcome, reason=None, reason_detail="")
            state.update(outcome)
            state.transition(BotLifecycleEvent.RECONCILE_OK)

    def compare_with_exchange(self) -> GridRuntime | ReconcileMismatch | ReconcileWait:
        """Steps 2–6 of the module docstring: the saved ladder brought level
        with the exchange, or why not. A query: nothing of the bot's record is
        changed (the budget is registered again, as trading derives it from
        exchange evidence); the caller applies the answer. `run` does for a
        RECOVERING bot, `GridStreamGap` for a running one (`EPIC-035B`)."""
        state = self._context.state
        # Open orders **before** the registration reads history fresh: an order
        # that fills in between is still listed open here and waits for the
        # next run, whereas read after it, the order would be gone from the
        # open orders while the history just read still shows it unexecuted,
        # and `_apply_missed_fills` would drop it with no fill and no counter
        # order (the review of PR 431, finding 3).
        open_orders = self._context.gateway.tagged_open_orders()
        registration = self._housekeeping.register()
        if not registration.registered or registration.inventory is None:
            return ReconcileWait(
                GridReason.SWITCH_OFF,
                f"waiting: the budget was refused: {refusal_text(registration)}",
            )
        try:
            applied = self._apply_missed_fills(state.runtime, open_orders)
        except AccountHistoryUnavailableError as error:
            logger.info("Bot %s: reconcile waits — history: %s", state.bot_id, error)
            return ReconcileWait(
                GridReason.HISTORY_UNAVAILABLE,
                f"waiting: order history did not answer ({error}); "
                "enable trading again to retry",
            )
        if isinstance(applied, ReconcileMismatch):
            return applied
        outcome = self._adopt(applied, open_orders)
        if isinstance(outcome, ReconcileMismatch):
            return outcome
        mismatch = self._check_inventory(outcome, registration.inventory.quantity)
        return outcome if mismatch is None else mismatch

    def _apply_missed_fills(
        self, runtime: GridRuntime, open_orders: tuple[Order, ...]
    ) -> GridRuntime | ReconcileMismatch:
        since = self._context.state.bot.lifecycle.run_started_at
        if since is None:
            return runtime
        open_ids = {order.client_order_id for order in open_orders}
        saved_ids = frozenset(order.client_order_id for order in runtime.open_orders)
        records = self._context.gateway.order_records(saved_ids, since)
        for saved in runtime.open_orders:
            record = records.get(saved.client_order_id)
            applied = self._catch_up(runtime, saved, record, since)
            if isinstance(applied, ReconcileMismatch):
                return applied
            runtime = applied
            if saved.client_order_id not in open_ids:
                ended = self._end_missing(runtime, saved)
                if isinstance(ended, ReconcileMismatch):
                    return ended
                runtime = ended
        return runtime

    def _catch_up(
        self,
        runtime: GridRuntime,
        saved: LevelOrder,
        record: OrderRecord | None,
        since: datetime,
    ) -> GridRuntime | ReconcileMismatch:
        """What the order executed beyond what the bot counted, applied as a
        fill, whether the order is gone from the exchange or still resting
        (`BUG-188`: a partial fill of an open order missed in a gap)."""
        missed = (record.executed_quantity - saved.executed) if record else Decimal(0)
        if missed <= 0 or record is None:
            return runtime
        trades = self._context.gateway.order_trades(record.exchange_order_id, since)
        fill = self._missed_fill(saved, record, missed, trades)
        reaction = on_fill(runtime, fill, self._context.terms.step_size, hold=True)
        halt = next((a for a in reaction.actions if isinstance(a, Halt)), None)
        if halt is not None:
            return ReconcileMismatch(halt.reason, halt.detail)
        # The replay uses the stream's key (`EPIC-035P`): a trade this applied
        # from history is not counted again when the stream delivers it late.
        for trade in trades:
            self._context.applied_fills.record(saved.client_order_id, trade.trade_id)
        logger.info(
            "Bot %s: reconcile %s executed %s since",
            self._context.state.bot_id,
            saved.client_order_id,
            missed,
        )
        return reaction.runtime

    def _end_missing(
        self, runtime: GridRuntime, saved: LevelOrder
    ) -> GridRuntime | ReconcileMismatch:
        """An order missing from the exchange that is not whole ended without
        filling: the level is laid again once, as the stream's end event does
        (`BUG-187`); a fully filled one was settled by `_catch_up`."""
        if runtime.level_of(saved.client_order_id) is None:
            return runtime
        terms = self._context.terms
        reaction = on_end(
            runtime,
            LevelEnd(saved.client_order_id, self._context.state.now()),
            LadderRules(terms.step_size, terms.min_notional),
            hold=True,
        )
        halt = next((a for a in reaction.actions if isinstance(a, Halt)), None)
        if halt is not None:
            return ReconcileMismatch(halt.reason, halt.detail)
        logger.info(
            "Bot %s: reconcile %s missing from the exchange, ended without filling",
            self._context.state.bot_id,
            saved.client_order_id,
        )
        return reaction.runtime

    def _missed_fill(
        self,
        saved: LevelOrder,
        record: OrderRecord,
        missed: Decimal,
        trades: tuple[TradeRecord, ...],
    ) -> LevelFill:
        base = self._context.base_asset
        base_fee = sum((t.fee for t in trades if t.fee_asset == base), Decimal(0))
        quote_fee = sum(
            (t.fee for t in trades if t.fee_asset == BUDGET_QUOTE_ASSET), Decimal(0)
        )
        return LevelFill(
            saved.client_order_id,
            record.average_price or saved.price,
            missed,
            base_fee=base_fee - saved.base_fee,
            quote_fee=quote_fee - saved.quote_fee,
        )

    def _adopt(
        self, runtime: GridRuntime, open_orders: tuple[Order, ...]
    ) -> GridRuntime | ReconcileMismatch:
        known = {order.client_order_id for order in runtime.open_orders}
        for order in open_orders:
            if order.client_order_id in known:
                continue
            level = runtime.level_at(order.price) if order.price is not None else None
            if level is None:
                return ReconcileMismatch(
                    GridReason.UNKNOWN_TAGGED_ORDER,
                    f"{order.client_order_id} at {order.price} is at no level of the ladder",
                )
            if level.state is not LevelState.EMPTY:
                return ReconcileMismatch(
                    GridReason.DUPLICATE_LEVEL_ORDER,
                    f"L{level.index} holds two orders carrying the tag",
                )
            runtime = adopted(runtime, level.index, _level_order(order))
            logger.info(
                "Bot %s: adopted %s at L%d",
                self._context.state.bot_id,
                order.client_order_id,
                level.index,
            )
        return runtime

    def _check_inventory(
        self, runtime: GridRuntime, derived: Decimal
    ) -> ReconcileMismatch | None:
        step = self._context.terms.step_size
        if abs(runtime.inventory - derived) > step:
            return ReconcileMismatch(
                GridReason.INVENTORY_MISMATCH,
                f"saved {runtime.inventory} against {derived} derived from the exchange",
            )
        base = self._context.base_asset
        holding = self._context.gateway.holding(base)
        if holding is None or holding < derived:
            return ReconcileMismatch(
                GridReason.HOLDING_BELOW_INVENTORY,
                f"the account holds {holding} {base}, below the {derived} the bot bought",
            )
        return None

    def _mismatch(self, reason: GridReason, detail: str) -> None:
        self._context.state.transition(
            BotLifecycleEvent.RECONCILE_MISMATCH, reason, detail
        )


def _level_order(order: Order) -> LevelOrder:
    if order.price is None:
        raise ValueError(f"{order.client_order_id} has no price to rest at")
    return LevelOrder(order.client_order_id, order.side, order.price, order.quantity)
