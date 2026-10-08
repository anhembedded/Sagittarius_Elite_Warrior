"""`EPIC-035A` — what a running Grid does with the price it hears and with its silence.

Split out of `GridExecutor` (the 400-line ceiling, `architecture-rule.md` §5.4):
the actor routes a tick and an age check here, and both run on the bot's worker.

  · **A tick** remembers the price with its moment (`EPIC-035J`), resets the
    bot's price age, and at or beyond the stop loss or the take profit runs Stop
    with *sell base* forced, recording why (ADR D11). It is watched while the bot may still hold a position it must
    exit: HALTED and ERROR, and since `EPIC-035A` STARTING and RECOVERING too;
    not STOPPING, whose Stop may keep the base.
  · **An age check** (`GridPriceAge`) halts a bot that holds orders and heard no
    tick for too long, with `PRICE_FEED_STALE`; in a state a quiet feed does not
    halt it only arms the wait again.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stopper import (
    GridStopper,
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
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

_S = BotLifecycleState

_WATCHES_EXITS: frozenset[BotLifecycleState] = frozenset(
    {_S.STARTING, _S.RUNNING, _S.PAUSED, _S.RECOVERING, _S.HALTED, _S.ERROR}
)


class GridPriceReaction:
    """Remembers the last price and reacts to a tick and to a quiet feed."""

    def __init__(self, context: GridRunContext, stopper: GridStopper) -> None:
        self._context = context
        self._stopper = stopper

    def on_tick(self, price: Decimal) -> None:
        self._context.reference_price.note_tick(price)
        self._context.price_age.note_tick()
        if self._context.state.state not in _WATCHES_EXITS:
            return
        params = self._context.params
        reason = crossed_exit(price, params.stop_loss_price, params.take_profit_price)
        if reason is not None:
            self._stopper.run(BaseHandling.SELL_AT_MARKET, reason, f"price {price}")

    def check_age(self) -> None:
        state = self._context.state
        age = self._context.price_age
        if state.state not in PRICE_STALENESS_HALTS:
            age.arm()
        elif (detail := age.stale_detail()) is not None:
            age.arm()
            halt_with(state, GridReason.PRICE_FEED_STALE, detail)
