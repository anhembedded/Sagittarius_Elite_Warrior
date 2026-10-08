"""`EPIC-035A` — what a running Grid does with the price it hears and with its silence.

Split out of `GridExecutor` (the 400-line ceiling, `architecture-rule.md` §5.4):
the actor routes a tick and an age check here, and both run on the bot's worker.

  · **A tick** remembers the price with its moment (`EPIC-035J`), resets the
    bot's price age, and when the tick's *range* reached the stop loss or the take
    profit runs Stop with *sell base* forced, recording why (ADR D11). The range
    is the low and high the bot observed while watching (`GridTickExtremes`,
    `BUG-191`): a wick between two pushes counts, one from before the bot listened
    does not. It is watched while the bot may still hold a position it must
    exit: HALTED and ERROR, and since `EPIC-035A` STARTING and RECOVERING too
    (a start or a recovery may hold the base, and `GridTickExtremes` already
    keeps the pre-start wick out); not STOPPING, whose Stop may keep the base.
  · **An age check** (`GridPriceAge`) halts a bot that holds orders and heard no
    tick for too long, with `PRICE_FEED_STALE`; in a state a quiet feed does not
    halt it only arms the wait again.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stopper import (
    GridStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_tick_extremes import (
    GridTickExtremes,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    PRICE_STALENESS_HALTS,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    crossed_exit,
    crossed_exit_in_range,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

logger = logging.getLogger("App.Bots.GridExecutor")

_S = BotLifecycleState

_WATCHES_EXITS: frozenset[BotLifecycleState] = frozenset(
    {_S.STARTING, _S.RUNNING, _S.PAUSED, _S.RECOVERING, _S.HALTED, _S.ERROR}
)


class GridPriceReaction:
    """Remembers the last price and reacts to a tick and to a quiet feed."""

    def __init__(self, context: GridRunContext, stopper: GridStopper) -> None:
        self._context = context
        self._stopper = stopper
        self._extremes = GridTickExtremes()

    def on_tick(self, tick: PriceTick) -> None:
        self._context.reference_price.note_tick(tick.last)
        self._context.price_age.note_tick()
        if self._context.state.state not in _WATCHES_EXITS:
            self._extremes.reset()
            return
        low, high = self._extremes.observed(tick)
        params = self._context.params
        stop, take = params.stop_loss_price, params.take_profit_price
        reason = crossed_exit_in_range(low, high, stop, take)
        if reason is None:
            return
        detail = f"price {tick.last}"
        if crossed_exit(tick.last, stop, take) is not reason:
            # Once: the Stop this starts leaves every state that watches exits.
            extreme, threshold = (
                (low, stop) if reason is GridReason.STOP_LOSS else (high, take)
            )
            detail = f"price {tick.last}, traded to {extreme}"
            logger.info(
                "Bot %s: %s fires on a wick, not on the close: close %s, %s %s, "
                "threshold %s [exit-on-extreme]",
                self._context.state.bot_id,
                reason.value,
                tick.last,
                "low" if reason is GridReason.STOP_LOSS else "high",
                extreme,
                threshold,
            )
        self._stopper.run(BaseHandling.SELL_AT_MARKET, reason, detail)

    def check_age(self) -> None:
        state = self._context.state
        age = self._context.price_age
        if state.state not in PRICE_STALENESS_HALTS:
            age.arm()
        elif (detail := age.stale_detail()) is not None:
            age.arm()
            halt_with(state, GridReason.PRICE_FEED_STALE, detail)
