"""What the `run` host does once at start (`EPIC-038D`).

Each step is an `IHostStep` the entry point hands the host in order; the host runs
them and logs their names. They are the part of "start" that is about *this app's*
bots and money rather than about being a host:

  · `WarnWhenNoAlertChannel` - with no alert channel configured on this host (no
    Discord webhook stored, `EPIC-036G`), a halt at 3 a.m. is silent, and the log
    should say so at the top;
  · `ReportRecoveringBots` - decision O2: a restart leaves RUNNING and PAUSED bots
    RECOVERING and the host does **not** resume them; one WARNING each says whose
    move it is;
  · `ResumeHaltedBots` - `--resume-halted`: a person's Resume and Confirm for every HALTED
    or AWAITING_RECOVERY bot, answered in advance on the command line (`EPIC-042E`);
  · `StartPlannedBots` - `--start-planned`: start what the plan wants running and
    is at rest, through the same Start the screen dispatches; a mainnet bot whose venue the
    operator did not type is skipped with a WARNING and an alert, and the rest start
    (`EPIC-045F`);
  · `ResumeRecoveringBots` - `--resume-recovering`: each RECOVERING bot's own Resume, the one
    the GUI sends, which opens its venue's order session and reconciles it with the exchange.

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
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.planned_bot_not_started_event import (
    PlannedBotNotStartedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ResumeHaltedForHostCommand,
    ResumeHaltedResult,
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
                "a person resumes it (decision O2) - `main.py bot resume %s` from a second "
                "shell on this host (a mainnet venue also needs --confirm-venue <that venue>), "
                "the Bots tab, or stop the host and start it again with --resume-recovering. "
                "Without that flag the host never resumes a bot by itself",
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
                    "[resume-recovering] %s: resumed %s; each reconciles with the exchange",
                    venue.venue,
                    ", ".join(venue.bot_ids),
                )
            else:
                logger.warning(
                    "[resume-recovering] %s: %s",
                    venue.venue,
                    venue.note,
                )


class ResumeHaltedBots(IHostStep):
    """`--resume-halted` (`EPIC-042E`): one line per bot says whether it was resumed and why not."""

    name = "resume-halted"
    trades = True

    def __init__(
        self, dispatcher: ICommandDispatcher, confirmed_venue: str | None
    ) -> None:
        self._dispatcher = dispatcher
        self._confirmed_venue = confirmed_venue

    def run(self) -> None:
        result = cast(
            ResumeHaltedResult,
            self._dispatcher.dispatch(
                ResumeHaltedForHostCommand,
                ResumeHaltedForHostCommand(self._confirmed_venue),
            ),
        )
        if not result.bots:
            logger.info("[resume-halted] no bot is HALTED or AWAITING_RECOVERY")
        for bot in result.bots:
            if bot.resumed:
                logger.info(
                    "[resume-halted] bot %s (%s, was %s): resume confirmed and queued; "
                    "its worker lays the ladder unless the price moved past the tolerance",
                    bot.bot_id,
                    bot.venue,
                    bot.was,
                )
            else:
                logger.warning(
                    "[resume-halted] bot %s (%s) stays %s: %s",
                    bot.bot_id,
                    bot.venue,
                    bot.was,
                    bot.note,
                )


class StartPlannedBots(IHostStep):
    name = "start-planned"
    trades = True

    def __init__(
        self,
        plan: IBotPlan,
        dispatcher: ICommandDispatcher,
        confirmed_venue: str | None,
        events: IEventPublisher,
    ) -> None:
        self._plan = plan
        self._dispatcher = dispatcher
        self._confirmed_venue = confirmed_venue
        self._events = events

    def run(self) -> None:
        if not self._plan.exists():
            logger.warning(
                "[start-planned] no bot plan exists, so nothing was started "
                "(`bot apply` writes one: EPIC-038I)"
            )
            return
        bots = {bot.bot_id: bot for bot in read_bot_status(self._dispatcher).bots}
        wanted = self._plan.wants_running()
        if not wanted:
            logger.info(
                "[start-planned] the plan wants no bot running, so nothing was started"
            )
        for bot_id in sorted(wanted):
            bot = bots.get(bot_id)
            if bot is None:
                logger.warning(
                    "[start-planned] the plan wants bot %s running; no such bot", bot_id
                )
            elif bot.is_at_rest and self._unconfirmed_mainnet(bot):
                self._skip(bot)
            elif bot.is_at_rest:
                self._start(bot_id)
            else:
                logger.info(
                    "[start-planned] bot %s is %s; not started", bot_id, bot.state
                )

    def _unconfirmed_mainnet(self, bot: BotStatusEntry) -> bool:
        """Decision O8: real money starts only for the venue the operator typed."""
        return TradingVenue(bot.venue).is_mainnet and bot.venue != self._confirmed_venue

    def _skip(self, bot: BotStatusEntry) -> None:
        """`EPIC-045F` (ADR 045 D7): leave this bot, tell a person, and go on with the rest of the
        plan. The old refusal exited 2 before boot, which systemd does not restart, and left every
        other bot unattended."""
        reason = (
            f"--start-planned did not start bot {bot.bot_id} on {bot.venue}: that real-money "
            "venue was not confirmed on this run"
            + (
                f" (this run confirms {self._confirmed_venue})"
                if self._confirmed_venue
                else " (no --confirm-venue was given)"
            )
            + "."
        )
        logger.warning(
            "[start-planned] bot %s on %s was not started: its venue was not confirmed; "
            "`bot start %s --confirm-venue %s` starts it",
            bot.bot_id,
            bot.venue,
            bot.bot_id,
            bot.venue,
        )
        self._events.publish(PlannedBotNotStartedEvent(bot.bot_id, bot.venue, reason))

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


def mainnet_resume_refusal(
    bots: tuple[BotStatusEntry, ...], confirmed_venue: str | None
) -> str | None:
    """Why the whole `--resume-recovering` must be refused, or `None` (decision O8).

    Resuming a RECOVERING bot on a mainnet venue reconciles real orders and lets the bot
    trade again, so it is judged like a start: an unconfirmed mainnet venue refuses the
    run with exit 2 and names the flag. It is judged **before the app boots**, when a bot
    left RUNNING or PAUSED on disk is not yet RECOVERING - the boot makes it so - so the
    test is the report's `recovers_on_restart`, the lifecycle table's own answer, not
    the state name. It is not skipped with a warning - a host that
    serves while it quietly left a bot unresumed is the surprise O8 exists to prevent.
    """
    return _unconfirmed_mainnet_refusal(
        "--resume-recovering would resume",
        [
            bot
            for bot in bots
            if bot.recovers_on_restart
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
