"""`EPIC-026L` — a trip stops every bot through the Bots tab's own Stop; it closes nothing itself.

For each bot that is not at rest it dispatches `StopBotCommand`, the command the screen's Stop
and the host's `bot stop` dispatch, so the lifecycle table, the executor's cancel-and-confirm and
its retries are the ones a person gets. This class places no order and has no close path of its
own.

@par What the stop keeps
A venue whose position cannot be kept (`keep_on_stop_closed_reason`: a Futures position has no
stop on the exchange) is stopped with the position closed at market, the one form the Stop
accepts there; any other venue is stopped keeping what the bot holds, as the host's shutdown stop
does. A Spot bot's base therefore stays in the account and its loss can still move: the alert says
so. Selling it is the owner's decision, made after the trip.

@par Not opening the order session
Like the host's shutdown stop, an automated Stop never opens a closed order session
(`StopBotForOperatorCommand` does, for a person). A stop that waits for a session stays STOPPING
and is repeated by the next sample, which skips a bot already STOPPING.
"""

from __future__ import annotations

import logging
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    keep_on_stop_closed_reason,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Bots.LossCap")

_STOPPING = "STOPPING"


class LossCapStopper:
    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher
        #: The refusal last told per bot, so a bot the Stop cannot take is said once, not every sample.
        self._told: dict[str, str] = {}

    def stop_all(self, active: tuple[BotStatusEntry, ...]) -> int:
        """Ask every active bot that is not already stopping to stop; how many are stopping now."""
        stopping = 0
        for bot in active:
            if bot.state == _STOPPING or self._stop(bot):
                stopping += 1
        return stopping

    def _stop(self, bot: BotStatusEntry) -> bool:
        try:
            result = cast(
                BotCommandResult,
                self._dispatcher.dispatch(
                    StopBotCommand, StopBotCommand(bot.bot_id, _exposure_of(bot))
                ),
            )
        # Converted at the seam: one bot whose Stop raised must not leave the bots after it running
        # on the money path; it is told at ERROR, counted as not stopping, and asked again.
        except Exception as exc:  # noqa: BLE001 - see above
            logger.error(
                "[loss-cap] the Stop of %s (%s) raised %s; the next sample asks again",
                bot.bot_id,
                bot.state,
                type(exc).__name__,
            )
            return False
        if result.accepted:
            self._told.pop(bot.bot_id, None)
            logger.info(
                "[loss-cap] stop requested for %s (%s on %s)",
                bot.bot_id,
                bot.state,
                bot.venue,
            )
            return True
        if self._told.get(bot.bot_id) != result.message:
            self._told[bot.bot_id] = result.message
            logger.warning(
                "[loss-cap] %s (%s) was not stopped: %s",
                bot.bot_id,
                bot.state,
                result.message,
            )
        return False


def _exposure_of(bot: BotStatusEntry) -> ExposureHandling:
    profile = venue_profile_of(TradingVenue(bot.venue))
    if profile is not None and keep_on_stop_closed_reason(profile) is not None:
        return ExposureHandling.CLOSE_AT_MARKET
    return ExposureHandling.KEEP
