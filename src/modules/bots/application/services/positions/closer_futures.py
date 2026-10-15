"""`EPIC-039H` — the position venue's close: a reduce-only market order, confirmed (decision O8).

@details What is closed is **the bot's own position**: the quantity it built from its own fills
(the registration's derived position), reduce-only, and no more (the owner's answer of
2026-10-13). A position the owner opened by hand on the same symbol, or what a forced close or an
ADL left of the bot's, is not the bot's to close: it stays open and is reported in words (a warning
tagged `[foreign-position]` and a note on the stop's reason), as the divergence or foreign position
it is. The orders are reduce-only and cut under the per-order cap (`send_exit_slices`); the
exchange refuses one that would grow or flip the position (`-2022`), so a close sent twice cannot
open the opposite side.

The close is confirmed by reading the position again, and by nothing else: the position must have
shrunk by what was sold. A remainder below the market step cannot be sent (a market order is a
whole number of market steps) and is left, said in the log; anything more waits for the next run of
the stop, which derives what is left, as Spot's does.

A halt closes (`closes_on_halt`), because a leveraged position is never left bare; `EPIC-039L`
makes that conditional on an exchange-side stop standing.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_exit_slices import (
    send_exit_slices,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stopping_wait import (
    wait_in_stopping,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_closer import (
    IExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.stop_progress import (
    StopProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.market_slices import (
    base_slices,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class PositionExposureCloser(IExposureCloser):
    """Closes the position on the bot's symbol with reduce-only market orders."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def closes_on_halt(self) -> bool:
        return True

    def close(
        self, registration: OwnerBudgetRegistrationResult, price: Decimal
    ) -> StopProgress | None:
        """`None` when the bot's own position is closed (or is a remainder below one market
        step); otherwise how the stop ended."""
        context = self._context
        held = context.gateway.position()
        if held is None:
            return self._wait("the exchange's position could not be read")
        derived = registration.position
        if derived is None and registration.foreign_position is None:
            return self._wait("the bot's own position could not be derived")
        # A refusal as a foreign position means the bot's own fills add up to flat (trading
        # refuses only then): nothing of the exchange's position is the bot's to close, which is
        # a NEUTRAL bot's ordinary state between cycles (`EPIC-039I`).
        step = context.terms.market_step
        own = _own_quantity(derived.quantity if derived else Decimal(0), held)
        foreign = abs(held) - own
        if own < step:
            self._report_foreign(foreign, step)
            self._log_flat(own)
            return None
        side = OrderSide.SELL if held > 0 else OrderSide.BUY
        slices = base_slices(own, price, context.cap, step)
        progress = send_exit_slices(
            context,
            slices,
            lambda piece: context.gateway.market_reduce_only(side, piece, price),
        )
        if progress is not None:
            return progress
        return self._confirm(foreign, step)

    def _confirm(self, foreign: Decimal, step: Decimal) -> StopProgress | None:
        left = self._context.gateway.position()
        if left is None:
            return self._wait("the position could not be read after the close")
        if abs(left) >= foreign + step:
            return self._wait(f"a position of {left} is still open after the close")
        self._report_foreign(foreign, step)
        self._log_flat(abs(left) - foreign)
        return None

    def _report_foreign(self, foreign: Decimal, step: Decimal) -> None:
        """Says, in words, what stays open because it is not the bot's."""
        if foreign < step:
            return
        state = self._context.state
        words = (
            f"{foreign} of the position on {state.bot.definition.symbol} is not this bot's "
            "(opened by hand, or left by a forced close) and was left open"
        )
        logger.warning("Bot %s: %s [foreign-position]", state.bot_id, words)
        runtime = state.runtime
        if runtime.reason is not None and words not in runtime.reason_detail:
            state.update(
                runtime.with_reason(runtime.reason, f"{runtime.reason_detail}; {words}")
            )

    def _log_flat(self, left: Decimal) -> None:
        logger.info(
            "Bot %s: the bot's own position is closed (%s left, below one market step) "
            "[position-closed]",
            self._context.state.bot_id,
            left,
        )

    def _wait(self, detail: str) -> StopProgress:
        wait_in_stopping(self._context, detail)
        return StopProgress.WAITING_ON_EXCHANGE


def _own_quantity(derived: Decimal, held: Decimal) -> Decimal:
    """How much of the exchange's position `held` the bot's derived `derived` may close: what they
    share on the same side, never more than either. A bot long by its fills over a short the owner
    opened has nothing to close."""
    if derived == 0 or (derived > 0) != (held > 0):
        return Decimal(0)
    return min(abs(derived), abs(held))
