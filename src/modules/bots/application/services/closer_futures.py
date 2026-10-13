"""`EPIC-039H` — the position venue's close: a reduce-only market order, confirmed flat (decision O8).

@details What is closed is the position **the exchange reports**, not the bot's own count of it:
a symbol is leased to its bot for the run and a start refuses a position that already stands
(`EPIC-039D`), so the exchange's position is the bot's, and when it is not (a forced close, an ADL,
a trade by hand) it is exactly the exposure that must not be left bare. The orders are reduce-only
and cut under the per-order cap (`send_exit_slices`); the exchange refuses one that would grow or
flip the position (`-2022`), so a close sent twice cannot open the opposite side.

The close is confirmed by reading the position again, and by nothing else: a remainder below the
market step cannot be sent (a market order is a whole number of market steps) and is left, said in
the log; anything more waits for the next run of the stop, which derives what is left, as Spot's
does.

A halt closes (`closes_on_halt`), because a leveraged position is never left bare; `EPIC-039L`
makes that conditional on an exchange-side stop standing.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_exit_slices import (
    send_exit_slices,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stopping_wait import (
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
        """`None` when the position is flat (or a remainder below one market step);
        otherwise how the stop ended."""
        context = self._context
        held = context.gateway.position()
        if held is None:
            return self._wait("the exchange's position could not be read")
        step = context.terms.market_step
        if abs(held) < step:
            self._log_flat(held)
            return None
        side = OrderSide.SELL if held > 0 else OrderSide.BUY
        slices = base_slices(abs(held), price, context.cap, step)
        progress = send_exit_slices(
            context,
            slices,
            lambda piece: context.gateway.market_reduce_only(side, piece, price),
        )
        if progress is not None:
            return progress
        return self._confirm_flat(step)

    def _confirm_flat(self, step: Decimal) -> StopProgress | None:
        left = self._context.gateway.position()
        if left is None:
            return self._wait("the position could not be read after the close")
        if abs(left) >= step:
            return self._wait(f"a position of {left} is still open after the close")
        self._log_flat(left)
        return None

    def _log_flat(self, left: Decimal) -> None:
        logger.info(
            "Bot %s: the position is closed (%s left, below one market step) "
            "[position-closed]",
            self._context.state.bot_id,
            left,
        )

    def _wait(self, detail: str) -> StopProgress:
        wait_in_stopping(self._context, detail)
        return StopProgress.WAITING_ON_EXCHANGE
