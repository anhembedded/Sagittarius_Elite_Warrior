"""Stop policy A (decision O1): close the workers, leave the orders where they are (`EPIC-038D`, `EPIC-038M`).

This is what closing the GUI does and what a crash does regardless, so it is the
one stop path that is tested in anger. For a Spot bot it asks the exchange for nothing and
changes no bot: it writes down, at INFO, which bots it leaves and how many orders
each has resting. The orders keep working on the exchange; what stops is the
watch. Between this stop and the next start nothing looks at a stop loss or a
take profit, under either policy (known gap, recorded for `EPIC-036`), and the next
boot reads each such bot back as RECOVERING from its file.

@par A position venue's bot (`EPIC-038M`, decision O12)
A Futures bot is leveraged: left with no stop on the exchange it can be liquidated while no copy of
the app watches it. So for each active bot the policy asks `GetBotStopCoverageQuery`, read fresh from
the exchange:
  · a position that a stop on the exchange covers (or no position and no ladder) is left as it is -
    its position, its resting orders and its stop stay, and the bot comes back RECOVERING;
  · a position whose stop is missing, does not cover it, or could not be read (an unread stop is not
    a covering stop) is closed before exit through the Stop the Bots tab's "Close the position at
    market" dispatches (`HostBotStopper`: cancel the ladder, close at market, reduce-only), and named
    at WARNING and in the ledger.

@par One deadline
The whole policy runs under `--stop-timeout`. Reading takes a share of it (`READ_SHARE`) so that
what must be closed has the rest. A bot not read by then is closed unread, and the log says that the
deadline made closing the safe side. A close that does not finish by the timeout stays in the ledger
with the state it was last seen in, and the host names it.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    BotStopCoverage,
    GetBotStopCoverageQuery,
    StopCoverage,
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

NAME = "leave-orders"

#: The share of `--stop-timeout` the policy spends reading whether stops cover positions; the rest
#: is for the closes it then asks for. Half: a read is a pair of REST calls per bot, a close is
#: a cancel, a market order and a confirming read.
READ_SHARE = 0.5


class LeaveOrdersResting(IShutdownPolicy):
    name = NAME

    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        stop_timeout_s: float,
        clock: Callable[[], float] = time.monotonic,
        poll_s: float = DEFAULT_POLL_SECONDS,
    ) -> None:
        self._dispatcher = dispatcher
        self._timeout_s = stop_timeout_s
        self._clock = clock
        self._stopper = HostBotStopper(
            dispatcher, NAME, ExposureHandling.CLOSE_AT_MARKET, poll_s
        )

    def apply(self, ledger: StopLedger, give_up: threading.Event) -> None:
        active = active_bots(read_bot_status(self._dispatcher))
        if not active:
            logger.info(
                "[stop-policy] %s: no bot is active; nothing is left behind", NAME
            )
            return
        read_until = self._clock() + self._timeout_s * READ_SHARE
        left: list[BotStatusEntry] = []
        waiting: list[str] = []
        for bot in active:
            decision = self._decide(bot, read_until, give_up)
            if decision.action is _Action.LEAVE:
                left.append(bot)
                logger.info(
                    "[stop-policy] %s: leaves %s%s",
                    NAME,
                    _describe(bot),
                    decision.words,
                )
            elif decision.action is _Action.CLOSE:
                logger.warning(
                    "[stop-policy] %s: closing %s (%s) before exit: %s",
                    NAME,
                    bot.bot_id,
                    bot.state,
                    decision.words,
                )
                if self._stopper.begin(
                    bot, ledger, f"closing before exit: {decision.words}"
                ):
                    waiting.append(bot.bot_id)
            elif decision.action is _Action.AWAIT:
                if self._stopper.begin(bot, ledger):
                    waiting.append(bot.bot_id)
            else:
                ledger.begin(bot.bot_id, bot.state, bot.resting_orders, decision.words)
        self._say_what_is_left(left, len(active) - len(left))
        self._stopper.wait(waiting, ledger, give_up)

    def _decide(
        self, bot: BotStatusEntry, read_until: float, give_up: threading.Event
    ) -> _Decision:
        if bot.state == "STOPPING":
            return _Decision(_Action.AWAIT)
        if give_up.is_set():
            return _Decision(_Action.SKIP, "not looked at: the host stopped waiting")
        reading = self._read(bot, read_until)
        if reading.coverage.leaves_standing:
            return _Decision(_Action.LEAVE, _why_left(reading))
        return _Decision(_Action.CLOSE, reading.words)

    def _read(self, bot: BotStatusEntry, read_until: float) -> BotStopCoverage:
        """The coverage of `bot`'s position; unread - which is not covered - when the budget is spent
        or the read fails."""
        if self._clock() >= read_until:
            return BotStopCoverage(
                bot.bot_id,
                StopCoverage.UNREAD,
                f"the stop deadline left no time to read its stop (a read budget of "
                f"{self._timeout_s * READ_SHARE:.0f} s of {self._timeout_s:.0f} s); closing "
                "is the safe side",
            )
        try:
            answer = self._dispatcher.dispatch(
                GetBotStopCoverageQuery, GetBotStopCoverageQuery(bot.bot_id)
            )
        except Exception as failure:  # converted at this seam: an unread stop is `UNREAD`, never covered
            logger.exception(
                "[stop-policy] %s: the stop of %s could not be read", NAME, bot.bot_id
            )
            return BotStopCoverage(
                bot.bot_id,
                StopCoverage.UNREAD,
                f"whether its protective stop stands could not be read ({type(failure).__name__})",
            )
        if not isinstance(answer, BotStopCoverage):
            return BotStopCoverage(
                bot.bot_id,
                StopCoverage.UNREAD,
                "whether its protective stop stands was not answered",
            )
        return answer

    def _say_what_is_left(self, left: list[BotStatusEntry], closed: int) -> None:
        known = [b.resting_orders for b in left if b.resting_orders is not None]
        logger.info(
            "[stop-policy] %s: %d active bot(s) left, %d orders resting on the exchange "
            "(%d bot(s) with the count unknown), %d closed before exit; nothing watches "
            "their stop loss or take profit until the next start",
            NAME,
            len(left),
            sum(known),
            len(left) - len(known),
            closed,
        )


class _Action(Enum):
    #: Nothing of what the bot holds can run away unwatched: it stays as it is.
    LEAVE = "leave"
    #: It is closed through the Bots tab's Stop with close.
    CLOSE = "close"
    #: It is already stopping: it is waited for, not asked again.
    AWAIT = "await"
    #: The host stopped waiting before the bot was looked at.
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class _Decision:
    action: _Action
    words: str = ""


def _describe(bot: BotStatusEntry) -> str:
    orders = "unknown" if bot.resting_orders is None else str(bot.resting_orders)
    if bot.resting_orders is None:
        return f"{bot.bot_id} ({bot.state}) orders resting: {orders}"
    return f"{bot.bot_id} ({bot.state}) {orders} orders resting"


def _why_left(reading: BotStopCoverage) -> str:
    if reading.coverage is StopCoverage.COVERED:
        return f"; its stop covers its position ({reading.words})"
    if reading.coverage is StopCoverage.NOTHING_EXPOSED:
        return f"; it holds no position and rests no ladder ({reading.words})"
    return ""
