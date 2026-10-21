"""The rows of the Bots tab / host parity guard (`EPIC-045D`): the data, kept apart from the checks.

Split from `test_the_bots_tab_and_the_host_stay_in_step.py` when that file reached the 400-line
ceiling. Each row says how a thing the Bots tab does is reached on the running host, or why it is not
(an `OPEN GAP` is something to close with a verb: slice `EPIC-045G`).
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import HostControlAction
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)


@dataclass(frozen=True, slots=True)
class HostVerb:
    """The tab command is reached on the host by `bot <verb>`, which sends this action."""

    verb: str
    action: HostControlAction


@dataclass(frozen=True, slots=True)
class Excluded:
    """The tab command has no single host verb, and why (or `OPEN GAP` when it should have one)."""

    reason: str


@dataclass(frozen=True, slots=True)
class ReadOnly:
    """A menu command that changes no stored bot (a view, a read, a form helper), and why."""

    reason: str


#: Every bot command defined under `use_cases/` that the tab can dispatch, by class name.
PARITY: dict[str, HostVerb | Excluded] = {
    "CreateBotCommand": HostVerb("add", HostControlAction.ADD),
    "EditBotCommand": HostVerb("edit", HostControlAction.EDIT),
    "StartBotCommand": HostVerb("start", HostControlAction.START),
    "PauseBotCommand": HostVerb("pause", HostControlAction.PAUSE),
    "ResumeBotCommand": HostVerb("resume", HostControlAction.RESUME),
    "StopBotCommand": HostVerb("stop", HostControlAction.STOP),
    "DeleteBotCommand": HostVerb("delete", HostControlAction.DELETE),
    "ConfirmBotResumeCommand": Excluded(
        "OPEN GAP. Confirming a HALTED bot's resume proposal is a person's act on the tab (decision "
        "D13), and `bot resume` refuses a HALTED bot. The host's only answer is `run --resume-halted`, "
        "a flag of `run`: it acts when a host starts, so a bot that halts on a running host is "
        "confirmed only by restarting the host, which is the cost the owner's rule is about."
    ),
    "ChangeBotVenueCommand": Excluded(
        "OPEN GAP. The tab moves a DRAFT that never ran to another venue. A plan names a bot by "
        "name and venue, so on the host the nearest thing is `bot delete <id>` then `bot add` with "
        "the entry on the new venue, which makes a new bot id and is not the same act."
    ),
}

#: Menu commands that dispatch no bot command of `PARITY`, by command id.
MENU: dict[str, HostVerb | Excluded | ReadOnly] = {
    "bots.bots.export_plan": ReadOnly(
        "It reads bots and writes a file, changing none; the host's equivalent is the read-only "
        "`bot export`, which works on the read-only copy beside a running host."
    ),
    "bots.bots.arm_strategy": Excluded(
        "OPEN GAP. It arms a strategy on a venue through the trading module's armed-strategy "
        "controls (`IVenueStrategyControls`), not a bot: there is no bot id and no host verb, and "
        "the one-round headless command is `trade-once`, which arms nothing."
    ),
    "bots.bots.disarm_strategy": Excluded(
        "OPEN GAP. The counterpart of Arm strategy; same controls, same missing verb."
    ),
    "bots.bots.refresh_fills": ReadOnly("Reads the selected bot's fills again."),
    "bots.bots.fit_levels": ReadOnly("Fits the chart to the ladder; a view."),
    "bots.bots.retry_connection": ReadOnly("Reads the venue account again."),
    "bots.bots.refresh_exchange": ReadOnly("Asks the exchange its facts again."),
    "bots.bots.fix_next": ReadOnly(
        "Performs the first readiness fix: read the account, ask the exchange, bring a field "
        "forward or select the active bot. It changes no stored bot."
    ),
    "bots.bots.chart.live_stream": ReadOnly("Switches the chart's stream; a view."),
    "bots.bots.live_tab": ReadOnly("Shows the live chart tab; a view."),
    "bots.bots.backtest_tab": ReadOnly("Shows the backtest tab; a view."),
    "bots.bots.chart.more_timeframes": ReadOnly("Chart timeframe chooser; a view."),
    "bots.bots.chart.zoom_in": ReadOnly("Chart zoom; a view."),
    "bots.bots.chart.zoom_out": ReadOnly("Chart zoom; a view."),
    "bots.bots.chart.zoom_in_vertically": ReadOnly("Chart zoom; a view."),
    "bots.bots.chart.zoom_out_vertically": ReadOnly("Chart zoom; a view."),
    "bots.bots.chart.box_zoom": ReadOnly("Chart zoom; a view."),
    "bots.bots.chart.reset_zoom": ReadOnly("Chart zoom; a view."),
    "bots.bots.chart.follow_latest": ReadOnly("Chart follow mode; a view."),
}

#: The tab's lifecycle buttons and the bot command each one dispatches (`bot_commands.command_for`).
BUTTON_COMMAND: dict[BotAction, str] = {
    BotAction.START: "StartBotCommand",
    BotAction.PAUSE: "PauseBotCommand",
    BotAction.RESUME: "ResumeBotCommand",
    BotAction.CONFIRM_RESUME: "ConfirmBotResumeCommand",
    BotAction.STOP: "StopBotCommand",
    BotAction.SAVE: "EditBotCommand",
    BotAction.DELETE: "DeleteBotCommand",
}
