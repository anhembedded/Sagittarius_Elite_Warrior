"""`EPIC-035F` — a bot that holds orders asks, between orders, whether its key still works.

A revoked API key gave no sign until the next order failed its connection check;
the bot's orders kept resting on an exchange that would no longer take a cancel.
Every beat of the price watch (`IBotFacts.on_price_age_check`, a task on the
bot's own queue) the bot asks, once per `KEY_PROBE_EVERY_SECONDS`, whether the
exchange still accepts its key (`BotOrderGateway.key_rejected`: the venue's
connection check, one account read). A rejection halts the bot with
`KEY_REJECTED` (see `grid_order_failure.key_rejected_detail`) and, being that
reason, `GridTaskGuard` does not try to park a ladder it cannot cancel.

Only a *rejected key* is acted on. An exchange that cannot be reached, a clock
that skews or any other failed check says nothing about the key and changes
nothing: the probe asks again at the next interval. A read that raises is logged
and asked again the same way.

Asked only in the states that hold orders or are laying them, the same set a
quiet price feed halts (`PRICE_STALENESS_HALTS`): a bot already HALTED, ERROR or
STOPPING has stopped placing, and a STOPPED or DRAFT bot holds nothing.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    halt_with,
    key_rejected_detail,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    PRICE_STALENESS_HALTS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: How often a bot with orders asks the exchange whether its API key is still
#: accepted: one account read a minute, so a revocation is found within about
#: a minute of the price watch's next beat, not at the next fill.
KEY_PROBE_EVERY_SECONDS: float = 60.0


class GridKeyProbe:
    """Asks the exchange, on an interval, whether it still accepts the bot's key."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._next_at = context.monotonic.seconds() + KEY_PROBE_EVERY_SECONDS

    def check(self) -> None:
        """One beat: probe when the interval has passed and the bot holds orders."""
        state = self._context.state
        now = self._context.monotonic.seconds()
        if state.state not in PRICE_STALENESS_HALTS:
            self._next_at = now + KEY_PROBE_EVERY_SECONDS
            return
        if now < self._next_at:
            return
        self._next_at = now + KEY_PROBE_EVERY_SECONDS
        try:
            rejected = self._context.gateway.key_rejected()
        # Converted at the seam: a probe that raised (the venue did not answer)
        # says nothing about the key; it is logged and asked again.
        except Exception:
            logger.exception("Bot %s: the key probe failed; asking again", state.bot_id)
            return
        if rejected:
            logger.error(
                "Bot %s: the exchange rejects the API key; halting [key-rejected]",
                state.bot_id,
            )
            halt_with(
                state,
                GridReason.KEY_REJECTED,
                key_rejected_detail("the key probe", ""),
            )
