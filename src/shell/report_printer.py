"""`IReportPrinter` over the CLI host's `emit_report` (`EPIC-038C`)."""

from __future__ import annotations

import argparse

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import CliOutcome
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_formats import (
    IReportFormats,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_printer import (
    IReportPrinter,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import Report
from Sagittarius_Elite_Warrior.src.support.cli_host.report_output import emit_report


class ReportPrinter(IReportPrinter):
    def __init__(self, formats: IReportFormats) -> None:
        self._formats = formats

    def print_report(
        self, report: Report, args: argparse.Namespace
    ) -> CliOutcome | None:
        return emit_report(report, args, self._formats)
