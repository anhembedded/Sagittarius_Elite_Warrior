"""Stop policy A (decision O1): close the workers, leave the orders where they are (`EPIC-038D`).

This is what closing the GUI does and what a crash does regardless, so it is the
one stop path that is tested in anger. It asks the exchange for nothing and
changes no bot: it writes down, at INFO, which bots it leaves and how many orders
each has resting. The orders keep working on the exchange; what stops is the
watch. Between this stop and the next start nothing looks at a stop loss or a
take profit, under either policy (known gap, recorded for `EPIC-036`), and the next
boot reads each such bot back as RECOVERING from its file.
"""

from __future__ import annotations

import logging
import threading

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.bots_status_read import (
    active_bots,
    read_bot_status,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_policy import (
    IShutdownPolicy,
    StopLedger,
)

logger = logging.getLogger("App.Operations.StopPolicy")

NAME = "leave-orders"


class LeaveOrdersResting(IShutdownPolicy):
    name = NAME

    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def apply(self, ledger: StopLedger, give_up: threading.Event) -> None:
        active = active_bots(read_bot_status(self._dispatcher))
        if not active:
            logger.info(
                "[stop-policy] %s: no bot is active; nothing is left behind", NAME
            )
            return
        for bot in active:
            logger.info("[stop-policy] %s: leaves %s", NAME, _describe(bot))
        known = [b.resting_orders for b in active if b.resting_orders is not None]
        logger.info(
            "[stop-policy] %s: %d active bot(s) left, %d orders resting on the exchange "
            "(%d bot(s) with the count unknown); nothing watches their stop loss or take "
            "profit until the next start",
            NAME,
            len(active),
            sum(known),
            len(active) - len(known),
        )


def _describe(bot: BotStatusEntry) -> str:
    orders = "unknown" if bot.resting_orders is None else str(bot.resting_orders)
    if bot.resting_orders is None:
        return f"{bot.bot_id} ({bot.state}) orders resting: {orders}"
    return f"{bot.bot_id} ({bot.state}) {orders} orders resting"
