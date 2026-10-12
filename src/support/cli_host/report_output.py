"""Print a command's `Report` in the format the operator asked for.

Capability: Print a report command's result as text, JSON or any registered format
    Also: --json, --format, output format, machine-readable output, renderer, report command, key=value, CSV
    Use: emit_report, select_format, wants_machine_output
    User: src/presentation/cli/exchange_status_cmd.py
    Status: stable

`EPIC-038B`. Every report command ends with `emit_report(report, args,
formats)`; it never names a format. `--json` is the short form of `--format
json`, and `--format` takes any name registered in `IReportFormats`, which is
why a new renderer needs no edit to a command or to the parser: the parser
accepts a free word and this module checks it against the registry at run time.
"""

from __future__ import annotations

import argparse
import sys

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_formats import (
    IReportFormats,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import Report
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import (
    JSON_FORMAT,
    TEXT_FORMAT,
)


class ReportFormatError(ValueError):
    """The operator named a format that does not exist, or two that disagree."""


def select_format(args: argparse.Namespace, formats: IReportFormats) -> str:
    """The format name the arguments ask for; `text` when they ask for none.

    @raise ReportFormatError `--json` contradicts `--format`, or the name is
        not registered (the message lists the ones that are).
    """
    explicit = getattr(args, "format", None)
    wants_json = bool(getattr(args, "json", False))
    if wants_json and explicit not in (None, JSON_FORMAT):
        raise ReportFormatError(
            f"--json means --format json, which contradicts --format {explicit}"
        )
    name = JSON_FORMAT if wants_json else (explicit or TEXT_FORMAT)
    if formats.get(name) is None:
        raise ReportFormatError(
            f"unknown format {name!r}; choose one of: {', '.join(formats.names())}"
        )
    return name


def wants_machine_output(args: argparse.Namespace) -> bool:
    """True when the operator asked for anything but the text report.

    Machine output owns stdout: the entry point keeps the application's console
    log (which the Engine writes to stdout) off for the run, or `... --json |
    jq` would read log lines as the start of the document. The format name is
    not validated here (`select_format` does that once the app is built).
    """
    explicit = getattr(args, "format", None)
    return bool(getattr(args, "json", False)) or explicit not in (None, TEXT_FORMAT)


def emit_report(
    report: Report, args: argparse.Namespace, formats: IReportFormats
) -> CliOutcome | None:
    """Print `report`; a usage outcome (nothing printed) if the format is unusable.

    The caller keeps the command's own outcome: print first, then return the
    exit code the *findings* deserve (a failed connection still prints its
    report and then exits 6), unless this returns a usage outcome, which takes
    precedence because nothing was shown.
    """
    try:
        name = select_format(args, formats)
    except ReportFormatError as exc:
        return CliOutcome(ExitCode.USAGE, str(exc))
    renderer = formats.get(name)
    if renderer is None:  # unreachable after select_format; keeps the type honest
        return CliOutcome(ExitCode.USAGE, f"unknown format {name!r}")
    sys.stdout.write(renderer.render(report) + "\n")
    return None
