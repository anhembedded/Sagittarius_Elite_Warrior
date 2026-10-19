"""`EPIC-029E` — the fills a reconcile applies from the exchange's history (split
from `grid_reconciler.py`, which sat at the 400-line ceiling; a pure move).

What a saved order executed beyond what the bot counted is applied as a fill
(its counter order held), and an order missing from the exchange that is not whole
ends without filling, so its level is laid again once. `GridReconciler` calls
`apply` for every saved order and `catch_up` for an order it adopts.

`BUG-214`: `apply` applies the missed fills in the order the exchange filled them,
read off the trade history, not in level order: a fill's counter is computed from
the ladder as the fills before it left it, so a rung that filled second is applied
second whatever its level (a lower rung applied first would send its counter to the
level an unapplied higher rung still holds, a `DUPLICATE_LEVEL_ORDER` halt).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.reconcile_outcome import (
    ReconcileMismatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_filled_order import (
    FilledOrder,
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


@dataclass(frozen=True)
class MissedFill:
    """What one saved order executed beyond what the bot counted, with its trades."""

    saved: LevelOrder
    record: OrderRecord
    missed: Decimal
    trades: tuple[TradeRecord, ...]

    @property
    def happened_at(self) -> tuple[datetime, int] | None:
        """When the exchange finished this fill: its newest trade's time, the
        trade id breaking a tie (ids rise in the order trades happen). `None`
        when history lists no trade for it."""
        if not self.trades:
            return None
        newest = max(self.trades, key=lambda trade: (trade.time, trade.trade_id))
        return newest.time, newest.trade_id


def event_order(found: MissedFill) -> tuple[bool, datetime, int]:
    """Sort key: fills the history dates, oldest first; the undated last, in the
    level order they were given (a stable sort keeps it)."""
    happened_at = found.happened_at
    if happened_at is None:
        return (True, datetime.max.replace(tzinfo=UTC), 0)
    return (False, *happened_at)


class GridMissedFills:
    """Applies the fills of a reconcile, on the bot's worker."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        #: The orders this reconcile filled from history, until the caller keeps its runtime.
        self._filled: list[FilledOrder] = []

    def apply(
        self,
        runtime: GridRuntime,
        open_orders: tuple[Order, ...],
        records: dict[str, OrderRecord],
    ) -> GridRuntime | ReconcileMismatch:
        self._filled = []
        since = self._context.state.bot.lifecycle.run_started_at
        if since is None:
            return runtime
        open_ids = {order.client_order_id for order in open_orders}
        saved_orders = runtime.open_orders
        pending = [
            found
            for saved in saved_orders
            if (found := self._missed(saved, records.get(saved.client_order_id), since))
            is not None
        ]
        for found in sorted(pending, key=event_order):
            applied = self._apply_missed(runtime, found)
            if isinstance(applied, ReconcileMismatch):
                return applied
            runtime = applied
        for saved in saved_orders:
            if saved.client_order_id not in open_ids:
                ended = self._end_missing(runtime, saved)
                if isinstance(ended, ReconcileMismatch):
                    return ended
                runtime = ended
        return runtime

    def take_filled(self) -> tuple[FilledOrder, ...]:
        """The orders the last `apply` filled, handed over once. Called only when the reconcile's
        runtime is kept: a runtime that is thrown away re-applies its fills at the next reconcile,
        so they are announced then and not now (`BOT-189`)."""
        taken = tuple(self._filled)
        self._filled = []
        return taken

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
        found = self._missed(saved, record, since)
        if found is None:
            return runtime
        return self._apply_missed(runtime, found)

    def _missed(
        self, saved: LevelOrder, record: OrderRecord | None, since: datetime
    ) -> MissedFill | None:
        missed = (record.executed_quantity - saved.executed) if record else Decimal(0)
        if missed <= 0 or record is None:
            return None
        trades = self._context.gateway.order_trades(record.exchange_order_id, since)
        return MissedFill(saved, record, missed, trades)

    def _apply_missed(
        self, runtime: GridRuntime, found: MissedFill
    ) -> GridRuntime | ReconcileMismatch:
        saved, missed, trades = found.saved, found.missed, found.trades
        fill = self._missed_fill(saved, found.record, missed, trades)
        reaction = on_fill(runtime, fill, self._context.terms.step_size, hold=True)
        halt = next((a for a in reaction.actions if isinstance(a, Halt)), None)
        if halt is not None:
            return ReconcileMismatch(halt.reason, halt.detail)
        self._filled.extend(reaction.filled)
        # The replay uses the stream's key (`EPIC-035P`): a trade this applied
        # from history is not counted again when the stream delivers it late.
        for trade in trades:
            self._context.applied_fills.record(saved.client_order_id, trade.trade_id)
        # `BUG-209`: the stream lost this fill and history gave it back - degraded
        # but recovered, so a WARNING, one per order (a reconcile, not a tick).
        logger.warning(
            "Bot %s: reconcile %s executed %s since, which the stream never "
            "delivered; applied from history [missed-fill]",
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
        logger.warning(
            "Bot %s: reconcile %s missing from the exchange, ended without filling; "
            "the stream never delivered its end [missed-end]",
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
