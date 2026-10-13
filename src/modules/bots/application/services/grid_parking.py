"""`EPIC-029E` / `EPIC-039H` — what a halt does to what the bot has on the exchange (decision O8).

@details A bot that stops placing takes its ladder off the exchange, so nothing keeps trading
while nobody places the counters (`GridTaskGuard`). That is all a Spot halt does: the base the bot
bought stays held, and the user decides (the owner's halt of 2026-10-09).

A position venue goes one step further, because a leveraged position is never left bare: after the
ladder is off, the bot **stops with the close** its venue's closer carries out (`IExposureCloser`) —
the same reduce-only close, the same STOPPING states, the same retries and rate-limit wait as the
user's Stop, a stop loss or a take profit, so one tested close serves all four. The halt's reason
stays the reason of the stop, and the detail says the position was closed, so the user reads why
the bot ended flat. `EPIC-039L` lets a standing exchange-side stop replace the close.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_housekeeping import (
    GridHousekeeping,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stopper import (
    GridStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_closer import (
    IExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: What the halt's detail says once the position is being closed.
POSITION_CLOSED_NOTE = (
    "any position is closed at market, as a leveraged position is never left bare"
)


class GridParking:
    """Takes a halted bot's ladder off and, on a position venue, closes its position."""

    def __init__(
        self, context: GridRunContext, closer: IExposureCloser, stopper: GridStopper
    ) -> None:
        self._context = context
        self._closer = closer
        self._stopper = stopper
        self._housekeeping = GridHousekeeping(context)

    def park(self) -> str | None:
        """@return What may still rest, in words, when a cancel did not go through; `None`
        when the ladder is off (and the position, where the venue closes one, is being closed)."""
        report = self._housekeeping.cancel_tagged()
        if report.failed is not None:
            return (
                f"{report.client_order_id} and any after it may still rest: "
                f"{report.failed.detail}"
            )
        if self._closer.closes_on_halt():
            self._close_position()
        return None

    def _close_position(self) -> None:
        state = self._context.state
        runtime = state.runtime
        reason = runtime.reason or GridReason.ORDER_FAILED
        detail = f"{runtime.reason_detail}; {POSITION_CLOSED_NOTE}"
        logger.warning(
            "Bot %s: halted (%s); closing the position [halt-closes-position]",
            state.bot_id,
            reason.value,
        )
        self._stopper.run(ExposureHandling.CLOSE_AT_MARKET, reason, detail)
