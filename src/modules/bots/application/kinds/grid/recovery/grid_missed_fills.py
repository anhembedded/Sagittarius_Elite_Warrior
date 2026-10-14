"""`EPIC-029E` — the fills a reconcile applies from the exchange's history (split
from `grid_reconciler.py`, which sat at the 400-line ceiling; a pure move).

What a saved order executed beyond what the bot counted is applied as a fill
(its counter order held), and an order missing from the exchange that is not whole
ends without filling, so its level is laid again once. `GridReconciler` calls
`apply` for every saved order and `catch_up` for an order it adopts.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.reconcile_outcome import (
    ReconcileMismatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    Halt,
    LadderRules,
    LevelEnd,
    LevelFill,
    on_end,
    on_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridMissedFills:
    """Applies the fills of a reconcile, on the bot's worker."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def apply(
        self,
        runtime: GridRuntime,
        open_orders: tuple[Order, ...],
        records: dict[str, OrderRecord],
    ) -> GridRuntime | ReconcileMismatch:
        since = self._context.state.bot.lifecycle.run_started_at
        if since is None:
            return runtime
        open_ids = {order.client_order_id for order in open_orders}
        for saved in runtime.open_orders:
            record = records.get(saved.client_order_id)
            applied = self.catch_up(runtime, saved, record, since)
            if isinstance(applied, ReconcileMismatch):
                return applied
            runtime = applied
            if saved.client_order_id not in open_ids:
                ended = self._end_missing(runtime, saved)
                if isinstance(ended, ReconcileMismatch):
                    return ended
                runtime = ended
        return runtime

    def catch_up(
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
