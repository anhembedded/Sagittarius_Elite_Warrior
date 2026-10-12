"""What a command-line command ends with: an exit code and, optionally, a sentence.

`EPIC-038B`. `ICliCommandHandler.handle` returned `None` and `main()` never
called `sys.exit`, so a failed `sync` and a good one both exited 0 and a script
could not tell them apart. The result is now a value the handler *returns*,
not an exception it raises: a handler stays testable without catching
`SystemExit`, and `None` still means success, so every handler written before
this file keeps working unchanged.

The table below is the documented contract. A number is never reused for a
different meaning, because a supervisor's restart policy is keyed on it
(`RestartPreventExitStatus` is generated from the table: today `2 3 4 5`). The meanings, the commands that use each
code and what a supervisor should do are generated from this enum into
`Docs/OPERATIONS/exit_codes.md` (`support/cli_host/exit_code_table.py`), so the
prose cannot differ from the code.

@par Extension cases
  · a new exit code — one member here, one row in `exit_code_table.py` (a test
    fails until the row exists), and a line in the commands that return it;
  · a command that fails in a new way — it returns `CliOutcome(<existing code>)`;
    nothing in `main()` or the host changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ExitCode(IntEnum):
    """The process exit statuses a command may end with (DESIGN §7)."""

    #: Success, or a clean shutdown.
    SUCCESS = 0
    #: An unexpected error: a bug or a condition nobody named. Restarted.
    ERROR = 1
    #: The request itself is unusable (argparse already exits 2 for a bad flag).
    USAGE = 2
    #: Another copy holds the data root's lock.
    LOCK_HELD = 3
    #: A pre-flight check failed.
    PREFLIGHT_FAILED = 4
    #: Configuration or credentials are missing, or refused by the application.
    CONFIGURATION = 5
    #: The exchange was unreachable or rejected the request (`-2015`, `-1021`).
    EXCHANGE = 6
    #: `status`: no host is running.
    HOST_NOT_RUNNING = 10
    #: `status`: a host is running but its snapshot is stale or a section is unavailable.
    HOST_UNHEALTHY = 11


@dataclass(frozen=True, slots=True)
class CliOutcome:
    """A command's result: the exit code, and a sentence for the operator.

    `message` is written to the error stream by the entry point when it is not
    empty. A handler that has already printed its own explanation (every
    command that existed before this contract) leaves it empty.
    """

    code: ExitCode
    message: str = ""

    @property
    def succeeded(self) -> bool:
        return self.code is ExitCode.SUCCESS
