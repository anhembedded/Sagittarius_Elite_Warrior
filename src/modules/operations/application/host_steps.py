"""What the `run` host does once at start (`EPIC-038D`).

Each step is an `IHostStep` the entry point hands the host in order; the host runs
them and logs their names. They are the part of "start" that is about *this app's*
bots and money rather than about being a host:

  · `WarnWhenNoAlertChannel` - before `EPIC-036B` routes bot events to a person,
    a halt at 3 a.m. is silent, and the log should say so at the top;
  · `ReportRecoveringBots` - decision O2: a restart leaves RUNNING and PAUSED bots
    RECOVERING and the host does **not** resume them; one WARNING each says whose
    move it is;
  · `StartPlannedBots` - `--start-planned`: start what the plan wants running and
    is at rest, through the same Start the screen dispatches;
  · `ResumeRecoveringBots` - `--resume-recovering`: open the order session the GUI
    opens, which reconciles each RECOVERING bot with the exchange.

Every request to the bots is a contract command (`host_bot_requests`) answered by
the screen's own command, so the host adds no way to start, stop or resume a bot.

@par Extension cases
  · another start-up duty - one `IHostStep` and one entry in the list the entry
    point builds; `RunHost` does not change.
"""

from __future__ import annotations

import logging
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
    ResumeRecoveringForHostCommand,
    ResumeRecoveringResult,
    StartBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_plan import IBotPlan
from Sagittarius_Elite_Warrior.src.modules.operations.application.bots_status_read import (
    read_bot_status,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_alert_channels import (
    IAlertChannels,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_step import (
    IHostStep,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Operations.Host")

_RECOVERING = "RECOVERING"


class WarnWhenNoAlertChannel(IHostStep):
    name = "alerts"

    def __init__(self, alerts: IAlertChannels) -> None:
        self._alerts = alerts

    def run(self) -> None:
        if self._alerts.carries_bot_events():
            logger.info("[alerts] an alert channel carries bot events")
            return
        logger.warning(
            "[alerts] no alert channel is configured for bot events; "
            "nothing will tell you if a bot halts"
        )


class ReportRecoveringBots(IHostStep):
    name = "recovering"

    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def run(self) -> None:
        recovering = [
            bot
            for bot in read_bot_status(self._dispatcher).bots
            if bot.state == _RECOVERING
        ]
        if not recovering:
            logger.info("[recovering] no bot is RECOVERING")
            return
        for bot in recovering:
            logger.warning(
                "[recovering] bot %s (%s) is RECOVERING after the restart and stays so: "
                "a person resumes it (decision O2) - the Bots tab, or stop the host and "
                "start it again with --resume-recovering (a mainnet venue also needs "
                "--confirm-venue <that venue>); `bot resume %s` needs a host that can be "
                "controlled (EPIC-038J). Without that flag the host never resumes a bot "
                "by itself",
                bot.bot_id,
                bot.name,
                bot.bot_id,
            )


class ResumeRecoveringBots(IHostStep):
    name = "resume-recovering"
    trades = True

    def __init__(
        self, dispatcher: ICommandDispatcher, confirmed_venue: str | None
    ) -> None:
        self._dispatcher = dispatcher
        self._confirmed_venue = confirmed_venue

    def run(self) -> None:
        result = cast(
            ResumeRecoveringResult,
            self._dispatcher.dispatch(
                ResumeRecoveringForHostCommand,
                ResumeRecoveringForHostCommand(self._confirmed_venue),
            ),
        )
        if not result.venues:
            logger.info("[resume-recovering] no venue holds a RECOVERING bot")
        for venue in result.venues:
            if venue.opened:
                logger.info(
                    "[resume-recovering] %s: the order session is open; reconciling %s "
                    "with the exchange",
                    venue.venue,
                    ", ".join(venue.bot_ids),
                )
            else:
                logger.warning(
                    "[resume-recovering] %s: %s; %s stay RECOVERING",
                    venue.venue,
                    venue.note,
                    ", ".join(venue.bot_ids),
                )


class StartPlannedBots(IHostStep):
    name = "start-planned"
    trades = True

    def __init__(
        self,
        plan: IBotPlan,
        dispatcher: ICommandDispatcher,
        confirmed_venue: str | None,
    ) -> None:
        self._plan = plan
        self._dispatcher = dispatcher
        self._confirmed_venue = confirmed_venue

    def run(self) -> None:
        if not self._plan.exists():
            logger.warning(
                "[start-planned] no bot plan exists, so nothing was started "
                "(`bot apply` writes one: EPIC-038I)"
            )
            return
        bots = {bot.bot_id: bot for bot in read_bot_status(self._dispatcher).bots}
        for bot_id in sorted(self._plan.wants_running()):
            bot = bots.get(bot_id)
            if bot is None:
                logger.warning(
                    "[start-planned] the plan wants bot %s running; no such bot", bot_id
                )
            elif bot.is_at_rest:
                self._start(bot_id)
            else:
                logger.info(
                    "[start-planned] bot %s is %s; not started", bot_id, bot.state
                )

    def _start(self, bot_id: str) -> None:
        result = cast(
            BotCommandResult,
            self._dispatcher.dispatch(
                StartBotForHostCommand,
                StartBotForHostCommand(bot_id, self._confirmed_venue),
            ),
        )
        if result.accepted:
            logger.info("[start-planned] bot %s: start requested", bot_id)
            return
        refusal = result.refusal.value if result.refusal is not None else "REFUSED"
        logger.warning(
            "[start-planned] bot %s was not started: %s (%s)",
            bot_id,
            refusal,
            result.message,
        )


def mainnet_start_refusal(
    bots: tuple[BotStatusEntry, ...], plan: IBotPlan, confirmed_venue: str | None
) -> str | None:
    """Why the whole `--start-planned` must be refused, or `None` (decision O8).

    A planned bot at rest on a mainnet venue is started with real money; the operator
    must have typed that venue. Judged for every planned bot before any is started, so
    one unconfirmed mainnet bot leaves all the others unstarted too: a half-started
    plan is the worse surprise.
    """
    if not plan.exists():
        return None
    wanted = plan.wants_running()
    return _unconfirmed_mainnet_refusal(
        "--start-planned would start",
        [
            bot
            for bot in bots
            if bot.bot_id in wanted
            and bot.is_at_rest
            and TradingVenue(bot.venue).is_mainnet
            and bot.venue != confirmed_venue
        ],
        "the plan holds",
    )


def mainnet_resume_refusal(
    bots: tuple[BotStatusEntry, ...], confirmed_venue: str | None
) -> str | None:
    """Why the whole `--resume-recovering` must be refused, or `None` (decision O8).

    Resuming a RECOVERING bot on a mainnet venue reconciles real orders and lets the bot
    trade again, so it is judged like a start: an unconfirmed mainnet venue refuses the
    run with exit 2 and names the flag. It is not skipped with a warning - a host that
    serves while it quietly left a bot unresumed is the surprise O8 exists to prevent.
    """
    return _unconfirmed_mainnet_refusal(
        "--resume-recovering would resume",
        [
            bot
            for bot in bots
            if bot.state == _RECOVERING
            and TradingVenue(bot.venue).is_mainnet
            and bot.venue != confirmed_venue
        ],
        "the host holds",
    )


def _unconfirmed_mainnet_refusal(
    what: str, unconfirmed: list[BotStatusEntry], holds: str
) -> str | None:
    if not unconfirmed:
        return None
    named = "; ".join(f"{bot.bot_id} on {bot.venue}" for bot in unconfirmed)
    venues = sorted({bot.venue for bot in unconfirmed})
    needed = f"--confirm-venue {venues[0]}"
    if len(venues) > 1:
        needed += (
            f" ({holds} real-money bots on {len(venues)} venues and one run "
            "confirms one: one mainnet venue per run)"
        )
    return (
        f"{what} real-money bots ({named}); nothing was started. "
        f"Type the venue to confirm it: {needed}"
    )
