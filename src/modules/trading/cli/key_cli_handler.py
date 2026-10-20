"""`key check` at the command line (`BOT-200`): which venue is this key for?

Reads the key and the secret from standard input (`key_stdin.py`), asks each
environment about them through `CheckKeyQuery`, prints the venues or the reason, and
writes nothing: it takes no lock and no data root, so it runs beside a running host.
On a server the keys are written by the root-run script `deploy/linux/sew-key`, which
pipes the key here before it keeps anything; the app never writes a systemd credential.

Exit status: 0 the key is for the venues it names; 2 the input cannot be a key; 5 the
operator must replace the key (it can withdraw, it may not trade, the exchange refuses
it); 6 an environment did not answer, so the key could not be judged.
"""

from __future__ import annotations

import argparse
import logging
import sys

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
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.check_key import (
    CheckKeyQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.cli.key_check_report import (
    key_check_outcome,
    key_check_report,
)
from Sagittarius_Elite_Warrior.src.modules.trading.cli.key_stdin import read_key_from
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_check import KeyCheck
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from sagittarius_engine import App

logger = logging.getLogger("App.KeyCheck")


class KeyCliHandler(ICliCommandHandler):
    """`key check`."""

    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> CliOutcome | None:
        if getattr(args, "action", None) != "check":
            return CliOutcome(ExitCode.USAGE, "key needs one of: check")
        container = app.container
        return run_key_check(
            read_key_from(sys.stdin),
            container.resolve(ICommandDispatcher),  # type: ignore[type-abstract]
            container.resolve(IReportPrinter),  # type: ignore[type-abstract]
            args,
        )


def run_key_check(
    credentials: ExchangeCredentials,
    dispatcher: ICommandDispatcher,
    printer: IReportPrinter,
    args: argparse.Namespace,
) -> CliOutcome | None:
    check = dispatcher.dispatch(CheckKeyQuery, CheckKeyQuery(credentials))
    if not isinstance(check, KeyCheck):
        raise TypeError("CheckKeyQuery was not answered with a KeyCheck")
    # The decision, never the key: the venues and why, as the report states them.
    logger.info(
        "the key is for [%s], refusal %s [key-check]",
        ", ".join(venue.value for venue in check.venues),
        check.refusal.value if check.refusal else "none",
    )
    printed = printer.print_report(key_check_report(check), args)
    return printed if printed is not None else key_check_outcome(check)
