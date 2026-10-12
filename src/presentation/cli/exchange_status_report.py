"""The `exchange-status` result: one `Report`, and the exit code its findings deserve (`EPIC-038B`).

The report is built from the status once; `--json` and the text view both come
from it, so they cannot disagree. The outcome is separate from the report: a
failed connection still prints its report (a monitor wants the JSON of the
failure) and *then* exits non-zero.

Failure kind -> exit code (DESIGN §7). `NOT_CONFIGURED` is code 5 because the
operator has not given the application a key; the two kinds where the key
exists but the application refuses it (`WITHDRAWAL_ENABLED`) or the account
cannot trade here (`HEDGE_MODE_UNSUPPORTED`) are code 5 too — a configuration
the operator must change. Everything the exchange itself answered or failed to
answer (`-2015`, `-1021`, `-1022`, network, maintenance) is code 6, which a
supervisor retries after a delay.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import Report
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    exchange_status_layout,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_payload import (
    SCHEMA_VERSION,
    exchange_status_payload,
)

COMMAND = "exchange-status"

#: Complete on purpose: `test_every_failure_kind_has_an_exit_code` fails for a
#: kind added to `ConnectionFailureKind` without a decision here.
EXIT_CODE_FOR_FAILURE: dict[ConnectionFailureKind, ExitCode] = {
    ConnectionFailureKind.NOT_CONFIGURED: ExitCode.CONFIGURATION,
    ConnectionFailureKind.WITHDRAWAL_ENABLED: ExitCode.CONFIGURATION,
    ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: ExitCode.CONFIGURATION,
    ConnectionFailureKind.BAD_SIGNATURE: ExitCode.EXCHANGE,
    ConnectionFailureKind.CLOCK_SKEW: ExitCode.EXCHANGE,
    ConnectionFailureKind.KEY_REJECTED: ExitCode.EXCHANGE,
    ConnectionFailureKind.NETWORK: ExitCode.EXCHANGE,
    ConnectionFailureKind.MAINTENANCE: ExitCode.EXCHANGE,
}


def exchange_status_report(status: ExchangeConnectionStatus) -> Report:
    return Report(
        command=COMMAND,
        version=SCHEMA_VERSION,
        payload=exchange_status_payload(status),
        layout=exchange_status_layout(status),
    )


def exchange_status_outcome(status: ExchangeConnectionStatus) -> CliOutcome | None:
    """`None` for a healthy connection, otherwise the failure's exit code."""
    if status.failure is None:
        return None
    return CliOutcome(EXIT_CODE_FOR_FAILURE[status.failure])
