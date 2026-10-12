"""`main.py preflight [--venue V] [--skip IDS] [--json]` (`EPIC-038F`).

Runs every declared pre-flight check, prints the report in the format asked for
and exits with the code the findings deserve (`preflight_report.py`). It sends
only read-only requests and never an order.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    IPreflightCheckTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_formats import (
    IReportFormats,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_report import (
    preflight_outcome,
    preflight_report,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_runner import (
    PreflightRunner,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.report_output import emit_report

if TYPE_CHECKING:
    from sagittarius_engine import App


def parse_skip(raw: str | None) -> frozenset[str]:
    return frozenset(part.strip() for part in (raw or "").split(",") if part.strip())


class PreflightCliHandler(ICliCommandHandler):
    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> CliOutcome | None:
        container = app.container
        runner = PreflightRunner(
            container.resolve(IPreflightCheckTable).descriptors(), container
        )
        skip = parse_skip(getattr(args, "skip", None))
        unknown = sorted(skip - set(runner.check_ids()))
        if unknown:
            return CliOutcome(
                ExitCode.USAGE,
                f"unknown check id(s) in --skip: {', '.join(unknown)}; "
                f"choose from: {', '.join(runner.check_ids())}",
            )
        results = runner.run(PreflightScope(getattr(args, "venue", None), skip))
        refused = emit_report(
            preflight_report(results), args, container.resolve(IReportFormats)
        )
        return refused if refused is not None else preflight_outcome(results)
