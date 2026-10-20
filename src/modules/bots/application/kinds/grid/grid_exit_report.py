"""`BOT-190` — tells the rest of the app that an exit has closed the run's position.

The close sells in several slices and each is booked by its own fill, after the bot is already
STOPPED, so the result of an exit is final only when the slice that leaves no more than dust is
booked. This is the one place that asks the question, right after an exit slice was booked. It only
reads the books and publishes: it orders, cancels, sizes and confirms nothing, and `GridStopSequence`
neither calls it nor waits for it.

An exit is told once, however many trades its last slice fills in (the count of exit slices sent
when it was told). A restart in the middle of an exit forgets the slices it sent (`OffLadderOrders`
lives in memory), so that exit is not told.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_exit_closed_event import (
    BotExitClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.exit_dust import (
    is_exit_dust,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_pnl import pnl_summary
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridExitReport:
    """Publishes one `BotExitClosedEvent` per exit, once its last slice is booked."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._told_after = 0

    def after_exit_fill(self) -> None:
        """Call right after an exit slice's fill was booked, on the worker."""
        context = self._context
        sent = context.off_ladder.exits_sent
        if sent <= self._told_after:
            return
        state = context.state
        runtime = state.runtime
        terms = context.terms
        floor = (
            terms.min_notional
            if context.limits.exposure_kind is ExposureKind.INVENTORY
            else None
        )
        if not is_exit_dust(
            runtime.inventory, runtime.mark_price, terms.market_step, floor
        ):
            return
        self._told_after = sent
        pnl = pnl_summary(runtime, None)
        started = state.bot.lifecycle.run_started_at
        run_id = f"{state.bot_id}@{started.isoformat() if started else 'unknown'}"
        reason = runtime.reason.value if runtime.reason is not None else ""
        context.events.publish(
            BotExitClosedEvent(
                bot_id=state.bot_id,
                run_id=run_id,
                reason=reason,
                total_pnl=pnl.total,
                grid_profit=pnl.grid_profit,
                completed_cycles=runtime.completed_cycles,
                unpriced_fees=pnl.unpriced_fees,
                quote_asset=BUDGET_QUOTE_ASSET,
            )
        )
        logger.info(
            "Bot %s: the exit of %s closed the position, %s left; result %s [exit-closed]",
            state.bot_id,
            reason or "no reason",
            runtime.inventory,
            pnl.total,
        )
