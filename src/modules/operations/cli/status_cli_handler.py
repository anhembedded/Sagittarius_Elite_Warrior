"""`status [--json] [--watch [--interval n]]` (`EPIC-038C`).

Dispatches `GetHostStatusQuery` through `ICommandDispatcher`, the port the Bots
tab uses for its reads (decision D2), builds one `Report` and prints it through
the registered renderer. `--watch` is D1's replacement for a terminal UI: the
same report, again, until Ctrl-C.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_printer import (
    IReportPrinter,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.queries.get_host_status import (
    GetHostStatusQuery,
    HostStatus,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.status_report import (
    status_outcome,
    status_report,
)
from sagittarius_engine import App


def run_status(
    args: argparse.Namespace,
    dispatcher: ICommandDispatcher,
    printer: IReportPrinter,
    wait: Callable[[float], None] = time.sleep,
) -> CliOutcome | None:
    """Once, with the exit code the findings deserve; or, with `--watch`, until
    interrupted, then 0. `wait` is injected so a test needs no sleep."""
    if args.watch:
        return _watch(args, dispatcher, printer, wait)
    status = _status_of(dispatcher)
    refused = printer.print_report(status_report(status), args)
    return refused if refused is not None else status_outcome(status)


def _watch(
    args: argparse.Namespace,
    dispatcher: ICommandDispatcher,
    printer: IReportPrinter,
    wait: Callable[[float], None],
) -> CliOutcome | None:
    if args.interval < 1:
        return CliOutcome(
            ExitCode.USAGE, "--interval is a whole number of seconds, 1 or more"
        )
    try:
        while True:
            refused = printer.print_report(status_report(_status_of(dispatcher)), args)
            if refused is not None:
                return refused
            sys.stdout.write("\n")
            wait(args.interval)
    except KeyboardInterrupt:
        return None


def _status_of(dispatcher: ICommandDispatcher) -> HostStatus:
    return cast(
        HostStatus, dispatcher.dispatch(GetHostStatusQuery, GetHostStatusQuery())
    )


class StatusCliHandler(ICliCommandHandler):
    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> CliOutcome | None:
        return run_status(
            args,
            app.container.resolve(ICommandDispatcher),
            app.container.resolve(IReportPrinter),
        )
