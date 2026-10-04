"""`EPIC-029E` — bringing a restored Grid back in line with the exchange (ADR §3.3, D12).

A bot that was RUNNING or PAUSED when the app closed loads as RECOVERING and
places nothing. When the user enables trading on its venue, this runs, in the
ADR's order:

  1. **Claim the lease** under the bot's owner id (leases live in memory).
  2. **Register the budget**: trading derives the inventory from exchange
     evidence (D6). Refused (trading off again) → the bot stays RECOVERING.
  3. **Read the open orders carrying the bot's tag.**
  4. **Apply fills first.** A saved order missing from the exchange is looked
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

History's order row carries no fee, so a missed fill takes its fees from the
order's trades, less what the bot already counted: Spot takes a buy's fee from
the base it bought, and the counter SELL may ask for no more than arrived. The
derivation in step 6 (which nets base-asset fees too) is the check that the
bot's inventory is still the exchange's.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
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
    LevelFill,
    adopted,
    drop_order,
    on_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
    LevelOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
)

logger = logging.getLogger("App.Bots.GridExecutor")


@dataclass(frozen=True, slots=True)
class ReconcileMismatch:
    """A step found the exchange and the ladder disagree, and why."""

    reason: GridReason
    detail: str


class GridReconciler:
    """Reconciles a RECOVERING Grid; ends in its prior state or HALTED."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._housekeeping = GridHousekeeping(context)

    def run(self) -> None:
        state = self._context.state
        symbol = state.bot.definition.symbol
        if not self._context.session.claim_symbol(symbol, bot_owner_id(state.bot_id)):
            self._mismatch(GridReason.LEASE_HELD, f"{symbol} is held by another owner")
            return
        registration = self._housekeeping.register()
        if not registration.registered or registration.inventory is None:
            state.update(
                state.runtime.with_reason(
                    GridReason.SWITCH_OFF,
                    f"waiting: the budget was refused: {refusal_text(registration)}",
                )
            )
            return
        open_orders = self._context.gateway.tagged_open_orders()
        runtime = self._apply_missed_fills(state.runtime, open_orders)
        outcome = self._adopt(runtime, open_orders)
        if isinstance(outcome, ReconcileMismatch):
            self._mismatch(outcome.reason, outcome.detail)
            return
        mismatch = self._check_inventory(outcome, registration.inventory.quantity)
        if mismatch is not None:
            self._mismatch(mismatch.reason, mismatch.detail)
            return
        state.update(outcome)
        state.transition(BotLifecycleEvent.RECONCILE_OK)

    def _apply_missed_fills(
        self, runtime: GridRuntime, open_orders: tuple[Order, ...]
    ) -> GridRuntime:
        gateway = self._context.gateway
        open_ids = {order.client_order_id for order in open_orders}
        since = self._context.state.bot.lifecycle.run_started_at
        for saved in runtime.open_orders:
            if saved.client_order_id in open_ids or since is None:
                continue
            record = gateway.order_record(saved.client_order_id, since)
            missed = (
                (record.executed_quantity - saved.executed) if record else Decimal(0)
            )
            if missed > 0 and record is not None:
                fill = self._missed_fill(saved, record, missed, since)
                runtime = on_fill(
                    runtime, fill, self._context.terms.step_size, hold=True
                ).runtime
            runtime = drop_order(runtime, saved.client_order_id)
            logger.info(
                "Bot %s: reconcile %s missing from the exchange, %s executed since",
                self._context.state.bot_id,
                saved.client_order_id,
                missed,
            )
        return runtime

    def _missed_fill(
        self, saved: LevelOrder, record: OrderRecord, missed: Decimal, since: datetime
    ) -> LevelFill:
        trades = self._context.gateway.order_trades(record.exchange_order_id, since)
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
