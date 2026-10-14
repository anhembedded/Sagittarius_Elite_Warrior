"""`EPIC-029E` / `EPIC-039H` — sending a close in slices, whatever the venue's order.

@details Every close — a Spot base sale, a position's reduce-only market order — is cut under the
per-order cap and sent one slice at a time (ADR D21). What a slice's outcome means is the same on
every venue, so it is judged here once: the order session closed waits for trading; a rejected key
ends the stop; a rate limit waits (nothing was sent, the next run derives what is left); any other
failure halts the bot naming the remainder, `possibly unsold` when the request raised, since it
may have executed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_order_failure import (
    fail_with,
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stopping_wait import (
    wait_in_stopping,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    OrderOutcome,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.stop_progress import (
    StopProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

logger = logging.getLogger("App.Bots.GridExecutor")


def send_exit_slices(
    context: GridRunContext,
    slices: tuple[Decimal, ...],
    send: Callable[[Decimal], OrderOutcome],
) -> StopProgress | None:
    """Send each of `slices` through `send`; `None` when all were sent, otherwise how the
    stop ended (the bot already carries the reason)."""
    remaining = sum(slices, Decimal(0))
    for index, piece in enumerate(slices, start=1):
        outcome = send(piece)
        context.off_ladder.add(outcome.client_order_id)
        logger.info(
            "Bot %s: exit slice %d of %s -> %s %s",
            context.state.bot_id,
            index,
            piece,
            outcome.kind.value,
            outcome.client_order_id or outcome.detail,
        )
        if outcome.kind is OrderOutcomeKind.SWITCH_OFF:
            wait_in_stopping(context, f"exit slice {index} refused: trading is off")
            return StopProgress.WAITING_FOR_TRADING
        if outcome.kind is OrderOutcomeKind.KEY_REJECTED:
            fail_with(context.state, outcome, f"exit slice {index}")
            return StopProgress.ENDED
        if outcome.kind is OrderOutcomeKind.RATE_LIMITED:
            # Nothing was sent: the next run derives what is left and sells it.
            wait_in_stopping(context, f"exit slice {index} not sent: {outcome.detail}")
            return StopProgress.WAITING_ON_EXCHANGE
        if not outcome.done:
            # A slice that raised may still have executed: say so rather
            # than count it unsold; the next stop or resume derives again.
            unsold = (
                "possibly unsold (the request may have executed)"
                if outcome.kind is OrderOutcomeKind.FAULT
                else "unsold"
            )
            halt_with(
                context.state,
                GridReason.EXIT_SLICE_FAILED,
                f"{remaining} {unsold} after slice {index}: {outcome.detail}",
            )
            return StopProgress.ENDED
        remaining -= piece
    return None
