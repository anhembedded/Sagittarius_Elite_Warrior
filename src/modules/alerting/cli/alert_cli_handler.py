"""`alert test` at the command line (`EPIC-036G`): the headless host's Send test.

Sends one test message to every configured channel and reports each answer.
Read-only (it writes no outbox and takes no lock), so it runs beside a running
host. On the VPS a channel's secret exists only inside the service's unit
(`LoadCredential=`), so the runbook runs it with the unit's credential
(`Docs/OPERATIONS/headless_runbook.md`).

Exit status: 0 when every channel took the message; 5 (`CONFIGURATION`, the
operator must act) when no channel is configured or a channel refused it; 1 when
a channel did not answer or asked to wait.
"""

from __future__ import annotations

import argparse

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_printer import (
    IReportPrinter,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    JsonValue,
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_message import (
    ChannelTestOutcome,
    SendTestMessage,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from sagittarius_engine import App

COMMAND = "alert"
REPORT_VERSION = 1

NO_CHANNEL = (
    "No alert channel is configured on this host. Store a Discord webhook under "
    "the secret 'alerting_discord_webhook' (on a server: the systemd credential "
    "the unit names, see the runbook), then run this again."
)

_CHANNEL_WIDTH = 10


class AlertCliHandler(ICliCommandHandler):
    """`alert test`."""

    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> CliOutcome | None:
        if getattr(args, "action", None) != "test":
            return CliOutcome(ExitCode.USAGE, "alert needs one of: test")
        container = app.container
        outcomes = SendTestMessage(
            container.resolve(IAlertChannelCatalog),  # type: ignore[type-abstract]
            container.resolve(IAlertClock),  # type: ignore[type-abstract]
        ).run()
        if not outcomes:
            return CliOutcome(ExitCode.CONFIGURATION, NO_CHANNEL)
        printed = container.resolve(IReportPrinter).print_report(  # type: ignore[type-abstract]
            send_test_report(outcomes), args
        )
        return printed if printed is not None else outcome_of(outcomes)


def send_test_report(outcomes: tuple[ChannelTestOutcome, ...]) -> Report:
    channels: list[JsonValue] = [
        {
            "channel": outcome.channel_id,
            "sent": outcome.result.ok,
            "reason": outcome.result.reason,
        }
        for outcome in outcomes
    ]
    rows = tuple(
        ReportRow(
            (
                ReportCell(outcome.channel_id, _CHANNEL_WIDTH),
                ReportCell(
                    "sent"
                    if outcome.result.ok
                    else f"not sent: {outcome.result.reason}"
                ),
            )
        )
        for outcome in outcomes
    )
    return Report(
        command=COMMAND,
        version=REPORT_VERSION,
        payload={"channels": channels},
        layout=(ReportSection("Test message", rows),),
    )


def outcome_of(outcomes: tuple[ChannelTestOutcome, ...]) -> CliOutcome | None:
    """`None` (success) when every channel took the message."""
    failed = [outcome.result for outcome in outcomes if not outcome.result.ok]
    if not failed:
        return None
    if any(result.permanent for result in failed):
        return CliOutcome(ExitCode.CONFIGURATION)
    return CliOutcome(ExitCode.ERROR)
