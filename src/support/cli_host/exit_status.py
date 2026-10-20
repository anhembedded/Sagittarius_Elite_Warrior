"""Run a command and turn whatever happens into one process exit status.

Capability: Turn a command's result into the process exit status, one table for every command
    Also: exit code, sys.exit, CliOutcome, return code, failed command exits zero, non-zero exit, script can tell failure
    Use: exit_status_of, run_command
    User: src/main.py
    Status: stable

`EPIC-038B`. `main()` used to end by falling off the bottom, so every command
exited 0 whatever it printed. `exit_status_of` is the one mapping
(`None` or a success outcome is 0; any other outcome is its code) and
`run_command` is the one place an exception becomes status 1, with the
traceback in the log: an unexpected failure is not a user's mistake, and the
supervisor that restarts a process on status 1 must find the cause in the log
without a reproduction.
"""

from __future__ import annotations

import logging
import sys
import traceback
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.error_message_style import (
    styled_error_message,
)

logger = logging.getLogger("App.CliHost")


def exit_status_of(outcome: CliOutcome | None) -> int:
    """`None` means success: the handlers written before the contract returned it."""
    return int(ExitCode.SUCCESS if outcome is None else outcome.code)


def run_command(command: Callable[[], CliOutcome | None]) -> int:
    """The exit status of `command`.

    A returned outcome with a message has it written to the error stream. An
    exception is logged with its traceback, written to the error stream too, and
    becomes `ExitCode.ERROR`;
    `SystemExit` (argparse's, a validator's) passes through untouched, because
    it already carries the status it means.
    """
    try:
        outcome = command()
    except Exception:
        # Both: the log is where an unattended run's cause is found later, and the
        # error stream is where a script that asked for `--json` (console log off,
        # so the log line never reaches the terminal) finds it now.
        logger.exception("[cli-exit] unexpected failure")
        traceback.print_exc(file=sys.stderr)
        return int(ExitCode.ERROR)
    if outcome is not None and outcome.message:
        message = outcome.message
        if not outcome.succeeded:
            message = styled_error_message(message, sys.stderr)
        sys.stderr.write(message + "\n")
    status = exit_status_of(outcome)
    logger.debug("[cli-exit] command finished with status %d", status)
    return status
