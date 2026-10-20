"""Stop policy B (decision O1, `--on-stop stop-bots`): stop each active bot first (`EPIC-038D`).

For planned maintenance and for "I am leaving the machine". For each bot that is
not at rest it asks for the Stop the screen dispatches (cancel the bot's tagged
orders, confirm none are open, STOPPED), then waits, reading the same status the
operator reads, until every bot it asked has reached STOPPED - or until the host
stops waiting (`give_up`: the timeout, or a second signal). It changes neither the
Stop use case nor any bot's lifecycle; a bot the host did not wait for stays in
the ledger with the state it was last seen in, and the host names it.

A Stop the lifecycle refuses (the table has no such row for the bot's state) is a
WARNING and the bot is left; a bot already STOPPING is waited for, not asked again
(`HostBotStopper`, shared with `LeaveOrdersResting`'s close of an uncovered position).
"""

from __future__ import annotations

import logging
import threading

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.host_bot_stopper import (
    DEFAULT_POLL_SECONDS,
    HostBotStopper,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.bots_status_read import (
    active_bots,
    read_bot_status,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_policy import (
    IShutdownPolicy,
    StopLedger,
)

logger = logging.getLogger("App.Operations.StopPolicy")

NAME = "stop-bots"


class StopBotsFirst(IShutdownPolicy):
    name = NAME

    def __init__(
        self, dispatcher: ICommandDispatcher, poll_s: float = DEFAULT_POLL_SECONDS
    ) -> None:
        self._dispatcher = dispatcher
        self._stopper = HostBotStopper(dispatcher, NAME, ExposureHandling.KEEP, poll_s)

    def apply(self, ledger: StopLedger, give_up: threading.Event) -> None:
        active = active_bots(read_bot_status(self._dispatcher))
        logger.info(
            "[stop-policy] %s: stopping %d bot(s) before the workers close",
            NAME,
            len(active),
        )
        waiting = [bot.bot_id for bot in active if self._stopper.begin(bot, ledger)]
        self._stopper.wait(waiting, ledger, give_up)
