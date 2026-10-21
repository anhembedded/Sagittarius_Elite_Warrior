"""`BUG-254` - sends a paced order, and sends it again when trading finds it too soon.

The pacer spaces the bot's turns; trading stamps an order when it judges it, a moment after the
turn that differs from order to order (a sleep that overshoots, the handler's lock held by a
neighbour, a terms read), and refuses one stamped less than the spacing after the previous stamp
(`owner_budget_spacing`). The two clocks cannot be made to agree: the stamp is taken after the
turn, so the pacer can only forecast it. Trading's verdict is the one that counts, and a verdict
of "too soon" is not a verdict on the order: the order waits for its next turn, which is at least
a spacing after the last, and goes again. Only when the turns keep missing (`PACING_RETRIES` in a
row) is the bot paused like any other pause it is asked for, and resumes by itself.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.order_outcome import (
    OrderOutcome,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)

logger = logging.getLogger("App.Bots.OrderPacer")

#: Turns a paced order takes again after trading found it too soon. A stamp lags its turn by
#: milliseconds, so one more turn (a spacing later) clears it; three is a pacer that is wrong,
#: not a stamp that is late.
PACING_RETRIES = 3
#: The pause asked of a bot whose turns kept missing, when trading named none.
DEFAULT_PACING_PAUSE = timedelta(seconds=1)


def send_paced(
    pacer: IOrderPacer, send: Callable[[], OrderOutcome], bot_tag: str
) -> OrderOutcome:
    """The outcome of `send` once it has taken a turn on `pacer`; a `PACED` answer takes another
    turn and sends again, up to `PACING_RETRIES` times, and then becomes `RATE_LIMITED`."""
    for attempt in range(PACING_RETRIES + 1):
        pacer.wait_turn()
        outcome = send()
        if outcome.kind is not OrderOutcomeKind.PACED:
            return outcome
        if attempt < PACING_RETRIES:
            logger.debug(
                "Bot %s: trading found the order sooner than the budget's spacing after the "
                "previous one, short by %s; it takes another turn (%d of %d) [order-pacing]",
                bot_tag,
                outcome.retry_after,
                attempt + 1,
                PACING_RETRIES,
            )
    return OrderOutcome(
        OrderOutcomeKind.RATE_LIMITED,
        detail=(
            f"the app's own order budget refused the order's spacing {PACING_RETRIES + 1} turns "
            "in a row"
        ),
        retry_after=outcome.retry_after or DEFAULT_PACING_PAUSE,
    )
