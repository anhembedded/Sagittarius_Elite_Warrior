"""The `exchange-status` result: one `Report`, and the exit code its findings deserve (`EPIC-038B`).

The report is built from the status once; `--json` and the text view both come
from it, so they cannot disagree. The outcome is separate from the report: a
failed connection still prints its report (a monitor wants the JSON of the
failure) and *then* exits non-zero.

Failure kind -> exit code is `connection_failure_exit_code.py` (`EPIC-038` D9),
shared with `preflight`: what the operator must change exits 5 (no key, `-2015`,
`-1022`, a key that can withdraw, Hedge Mode), what a restart can outlast exits 6
(network, maintenance, `-1021`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import Report
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connection_failure_exit_code import (
    EXIT_CODE_FOR_FAILURE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
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
