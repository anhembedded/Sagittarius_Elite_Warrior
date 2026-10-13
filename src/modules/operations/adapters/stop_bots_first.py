"""Stop policy B (decision O1, `--on-stop stop-bots`): stop each active bot first (`EPIC-038D`).

For planned maintenance and for "I am leaving the machine". For each bot that is
not at rest it asks for the Stop the screen dispatches (cancel the bot's tagged
orders, confirm none are open, STOPPED), then waits, reading the same status the
operator reads, until every bot it asked has reached STOPPED - or until the host
stops waiting (`give_up`: the timeout, or a second signal). It changes neither the
Stop use case nor any bot's lifecycle; a bot the host did not wait for stays in
the ledger with the state it was last seen in, and the host names it.

A Stop the lifecycle refuses (the table has no such row for the bot's state) is a
WARNING and the bot is left; a bot already STOPPING is waited for, not asked again.
"""

from __future__ import annotations

import logging
import threading
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StopBotForHostCommand,
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

NAME = "stop-bots"
_STOPPING = "STOPPING"
_STOPPED = "STOPPED"
#: How long between two reads of the bots while waiting for their stops.
DEFAULT_POLL_SECONDS = 0.5


class StopBotsFirst(IShutdownPolicy):
    name = NAME

    def __init__(
        self, dispatcher: ICommandDispatcher, poll_s: float = DEFAULT_POLL_SECONDS
    ) -> None:
        self._dispatcher = dispatcher
        self._poll_s = poll_s

    def apply(self, ledger: StopLedger, give_up: threading.Event) -> None:
        active = active_bots(read_bot_status(self._dispatcher))
        logger.info(
            "[stop-policy] %s: stopping %d bot(s) before the workers close",
            NAME,
            len(active),
        )
        waiting = [bot.bot_id for bot in active if self._begin(bot, ledger)]
        while waiting and not give_up.is_set():
            waiting = self._after_a_read(waiting, ledger)
            if waiting:
                give_up.wait(self._poll_s)

    def _begin(self, bot: BotStatusEntry, ledger: StopLedger) -> bool:
        """Ask for the stop; True when the bot is now stopping and worth waiting for."""
        ledger.begin(bot.bot_id, bot.state, bot.resting_orders)
        if bot.state == _STOPPING:
            logger.info("[stop-policy] %s: %s is already stopping", NAME, bot.bot_id)
            return True
        result = cast(
            BotCommandResult,
            self._dispatcher.dispatch(
                StopBotForHostCommand, StopBotForHostCommand(bot.bot_id)
            ),
        )
        if result.accepted:
            logger.info("[stop-policy] %s: stop requested for %s", NAME, bot.bot_id)
            return True
        note = f"the stop was refused: {result.message}"
        ledger.update(bot.bot_id, bot.state, note)
        logger.warning(
            "[stop-policy] %s: %s (%s) was left: %s", NAME, bot.bot_id, bot.state, note
        )
        return False

    def _after_a_read(self, waiting: list[str], ledger: StopLedger) -> list[str]:
        """The bots still not STOPPED after one more read of their states."""
        states = {b.bot_id: b.state for b in read_bot_status(self._dispatcher).bots}
        still: list[str] = []
        for bot_id in waiting:
            state = states.get(bot_id)
            if state == _STOPPED:
                logger.info("[stop-policy] %s: %s stopped", NAME, bot_id)
                ledger.finish(bot_id)
            else:
                ledger.update(bot_id, state or "unknown")
                still.append(bot_id)
        return still
