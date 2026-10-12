"""`EPIC-021D` — headless `main.py exchange-status`. The first CLI command
that touches the real exchange, read-only."""

import argparse

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import CliOutcome
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_formats import (
    IReportFormats,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_report import (
    exchange_status_outcome,
    exchange_status_report,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.report_output import emit_report
from sagittarius_engine import App


def execute_exchange_status(app: App, args: argparse.Namespace) -> CliOutcome | None:
    """`EPIC-025` PR 1.3b — resolves `trading`'s published port instead of
    building its query. Same handler underneath, same output; what changes is
    that this file no longer imports another context's `application/` package
    to name a type it only wanted to dispatch.

    `EPIC-038B` — the status becomes a `Report` printed in the format the
    operator asked for (`--json`, `--format`); the exit code is the failure's,
    unless the format itself was unusable (nothing was printed, a usage error).
    """
    status = app.container.resolve(IAccountSnapshot).check_connection()
    refused = emit_report(
        exchange_status_report(status), args, app.container.resolve(IReportFormats)
    )
    return refused if refused is not None else exchange_status_outcome(status)
