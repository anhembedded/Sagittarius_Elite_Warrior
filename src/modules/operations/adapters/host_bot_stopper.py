"""Ask for the Stop the Bots tab dispatches and wait for it, as the host's policies do (`EPIC-038D`, `EPIC-038M`).

@details Both policies that stop a bot (`StopBotsFirst`, and `LeaveOrdersResting` for a position
venue's bot whose stop does not cover it) send `StopBotForHostCommand`, which is the screen's own
`StopBotCommand`, and then wait - reading the same status the operator reads - until every bot they
asked has reached STOPPED, or until the host stops waiting (`give_up`). The only difference between
them is what the Stop does with what the bot holds, so the dispatch and the wait live here once.

A Stop the lifecycle refuses (the table has no such row for the bot's state) is a WARNING and the bot is
left; a bot already STOPPING is waited for, not asked again. A bot the host did not wait for stays in
the ledger with the state it was last seen in.
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.bots_status_read import (
    read_bot_status,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_policy import (
    StopLedger,
)

logger = logging.getLogger("App.Operations.StopPolicy")

_STOPPING = "STOPPING"
_STOPPED = "STOPPED"
#: How long between two reads of the bots while waiting for their stops.
DEFAULT_POLL_SECONDS = 0.5


class HostBotStopper:
    """Stops bots for one policy, with `exposure` as what the Stop does with what a bot holds."""

    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        policy_name: str,
        exposure: ExposureHandling,
        poll_s: float = DEFAULT_POLL_SECONDS,
    ) -> None:
        self._dispatcher = dispatcher
        self._policy = policy_name
        self._exposure = exposure
        self._poll_s = poll_s

    def begin(self, bot: BotStatusEntry, ledger: StopLedger, note: str = "") -> bool:
        """Ask for the stop; True when the bot is now stopping and worth waiting for."""
        ledger.begin(bot.bot_id, bot.state, bot.resting_orders, note)
        if bot.state == _STOPPING:
            logger.info(
                "[stop-policy] %s: %s is already stopping", self._policy, bot.bot_id
            )
            return True
        result = cast(
            BotCommandResult,
            self._dispatcher.dispatch(
                StopBotForHostCommand, StopBotForHostCommand(bot.bot_id, self._exposure)
            ),
        )
        if result.accepted:
            logger.info(
                "[stop-policy] %s: stop requested for %s", self._policy, bot.bot_id
            )
            return True
        refusal = f"the stop was refused: {result.message}"
        ledger.update(bot.bot_id, bot.state, refusal)
        logger.warning(
            "[stop-policy] %s: %s (%s) was left: %s",
            self._policy,
            bot.bot_id,
            bot.state,
            refusal,
        )
        return False

    def wait(
        self, waiting: list[str], ledger: StopLedger, give_up: threading.Event
    ) -> None:
        """Read the bots until each in `waiting` is STOPPED, or `give_up` is set."""
        while waiting and not give_up.is_set():
            waiting = self._after_a_read(waiting, ledger)
            if waiting:
                give_up.wait(self._poll_s)

    def _after_a_read(self, waiting: list[str], ledger: StopLedger) -> list[str]:
        """The bots still not STOPPED after one more read of their states."""
        states = {b.bot_id: b.state for b in read_bot_status(self._dispatcher).bots}
        still: list[str] = []
        for bot_id in waiting:
            state = states.get(bot_id)
            if state == _STOPPED:
                logger.info("[stop-policy] %s: %s stopped", self._policy, bot_id)
                ledger.finish(bot_id)
            else:
                ledger.update(bot_id, state or "unknown")
                still.append(bot_id)
        return still
