"""Where a read-only command's log goes: a file of its own, and warnings on the console.

Capability: Keep a short read-only command's log off its console, in a bounded file under the data root
    Also: --verbose, quiet console, bot list prints 60 log lines, cli log file, log rotation, one log file per process, stderr warnings only
    Use: prepare_cli_log, CliLogRouting
    User: src/main.py
    Status: stable

`BOT-185`. A command that only reads (`"read_only": true` in `cli_commands.json`)
boots the whole application to print one table, and the Engine's console handler
wrote every INFO record of that boot to stdout around it. For such a run the table
is all the console shows; the records go to `<data root>/logs/cli-<ts>-<pid>.log`,
and `--verbose` puts them back on the console. `run` and every command that may
change something keep the log on stdout as before: a service's log is the
supervisor's to rotate (`Docs/OPERATIONS/LOGGING.md` §1).

@par What stays on the console
  A WARNING, ERROR or CRITICAL record is written to stderr, in the log's own format,
  whatever the command: a failed command is never silent, and stdout (the table, or
  the `--json` document) carries nothing but the result.

@par Why one file per process, not one rotating file
  Several short commands run at once (a cron job beside an operator's `bot list`).
  Python's `RotatingFileHandler` is not safe across processes: two renames of the
  same file lose records, and on Windows the rename fails with `PermissionError`
  while another process holds the file, which `logging` then prints to stderr. A file
  per process has no writer to race with; the size is bounded by pruning the oldest
  files at start (`FILES_KEPT`) and by a per-file cap (`MAX_FILE_BYTES`, one backup).
  Two processes pruning together may both delete the same file (the second finds it
  gone and moves on) or leave a few more than `FILES_KEPT` until the next start.

The Engine is not changed (`ONBOARDING.md` §2): its `StdLogger` builds its handlers
from configuration and clears them whenever one is constructed, which `create_app`
does twice, so `apply` runs after each construction.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_decision_log = logging.getLogger("App.CliLog")

#: A file's name: `cli-<UTC ts>-<pid>.log`; `.log.1` is its one backup.
FILE_PREFIX = "cli-"
_FILE_PATTERN = f"{FILE_PREFIX}*.log*"
#: Per-file cap, and the number of files (backups included) one directory keeps:
#: the directory holds at most `FILES_KEPT * MAX_FILE_BYTES` = 20 MiB of these.
MAX_FILE_BYTES = 512 * 1024
FILES_KEPT = 40
#: The records still shown on the console of a quiet run.
CONSOLE_LEVEL = logging.WARNING
#: The fixed-field format of `logging-rule.md` §8, the Engine's own.
_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class _CliFileHandler(RotatingFileHandler):
    """Marks the handler this module added, so `apply` replaces it, never doubles it."""


class _CliConsoleHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """The stderr handler for WARNING and above; marked for the same reason."""


@dataclass(frozen=True, slots=True)
class CliLogRouting:
    """What a quiet run decided: the file its records go to, or why there is none."""

    log_file: Path | None
    #: Set when `log_file` is `None`: the data root's `logs/` could not be used.
    unavailable_reason: str | None = None

    def apply(self) -> None:
        """Take the Engine's stdout handler off the `App` logger and add ours.

        Call it after every `StdLogger` construction. The Engine's file handler
        (`log.file`, or a developer's `--dev` log) is left alone: the operator asked
        for that one by name."""
        logger = logging.getLogger(
            "App"
        )  # the Engine's logger every `App.*` record reaches
        for handler in list(logger.handlers):
            # Exactly `StreamHandler`: the Engine's console handler. A file handler
            # is a subclass and stays; so would a handler of anyone else's.
            if type(handler) is logging.StreamHandler or isinstance(
                handler, _CliFileHandler | _CliConsoleHandler
            ):
                logger.removeHandler(handler)
                handler.close()
        formatter = logging.Formatter(_LOG_FORMAT)
        if self.log_file is not None:
            file_handler = _CliFileHandler(
                self.log_file,
                maxBytes=MAX_FILE_BYTES,
                backupCount=1,
                encoding="utf-8",
                delay=True,
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        console = _CliConsoleHandler(sys.stderr)
        console.setLevel(CONSOLE_LEVEL)
        console.setFormatter(formatter)
        logger.addHandler(console)

    def log_decision(self) -> None:
        """The first line of the run's log, and a console line when there is no file."""
        if self.log_file is None:
            _decision_log.warning(
                "[cli-log] no log file (%s); only warnings and errors are shown",
                self.unavailable_reason,
            )
            return
        _decision_log.info(
            "[cli-log] console shows warnings and errors only; records go to %s "
            "(--verbose puts them on the console)",
            self.log_file,
        )


def prepare_cli_log(log_dir: Path, *, now: datetime | None = None) -> CliLogRouting:
    """The routing for this process: make room in `log_dir` and name its file.

    Never raises: a read-only command must not fail because its log cannot be
    written (a service account's data root seen from another user). The routing then
    has no file and says why."""
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(log_dir, os.W_OK):
            raise PermissionError(f"{log_dir} is not writable")
        _prune(log_dir, keep=FILES_KEPT - 1)
    except OSError as error:
        return CliLogRouting(None, f"{type(error).__name__}: {error}")
    stamp = _file_stamp(now or datetime.now(UTC))
    return CliLogRouting(log_dir / f"{FILE_PREFIX}{stamp}-{os.getpid()}.log")


def _file_stamp(moment: datetime) -> str:
    """`20261017T140143`: a file name, not display text, so it is not the formatter's."""
    utc = moment.astimezone(UTC).replace(tzinfo=None)
    return utc.isoformat(timespec="seconds").translate(str.maketrans("", "", "-:"))


def _prune(log_dir: Path, keep: int) -> None:
    """Delete the oldest `cli-*` files beyond `keep`; a file already gone is fine."""
    dated: list[tuple[float, Path]] = []
    for path in log_dir.glob(_FILE_PATTERN):
        with suppress(OSError):
            dated.append((path.stat().st_mtime, path))
    dated.sort(key=lambda entry: entry[0], reverse=True)
    for _, path in dated[keep:]:
        with suppress(OSError):
            path.unlink()
