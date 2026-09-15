"""Restarting the application after the developer-mode switch (SDD §4, ADR D14).

`dev.mode` is read **once**, at boot: it gates a surface, and a value that
could change mid-run would mean loading or unloading a module, which the
contribution mechanism deliberately cannot do (`shell/dev_mode.py` says so in
its own words). So the switch writes the file and the app restarts — there is
no third option that is honest.

Two things here, split on purpose:

- `argv_for_restart()` is a **pure function**, so what the next process is told
  is testable without spawning anything. It is also where the one real subtlety
  lives: `--dev` / `--debug` on the old command line would *win over the file*
  on the next run (`resolve_dev_mode()` checks the flag first), so a user who
  turns developer mode **off** from a session that was started with the flag
  must not have it handed back to them. The flags are stripped in that case and
  kept in the other, where they agree with what was just written.
- `restart_now()` takes the two side effects as arguments — starting the new
  process and quitting this one. A test drives the decision; only the
  application passes Qt's own implementations.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

logger = logging.getLogger("App.Shell.Restart")

#: The flags `resolve_dev_verbosity()` parses, and therefore the ones that
#: would override `dev.mode` from the file on the next run.
DEV_FLAGS: frozenset[str] = frozenset({"--dev", "--debug"})


def argv_for_restart(argv: Sequence[str], *, dev_mode_enabled: bool) -> list[str]:
    """The arguments the next process should get.

    `argv[0]` — the script path — is kept: the app is started as
    `python -m ...` or as a script, and the next process has to be started the
    same way it was, not guessed.
    """
    if not argv:
        return []
    script, *arguments = argv
    if dev_mode_enabled:
        return [script, *arguments]
    return [script, *(argument for argument in arguments if argument not in DEV_FLAGS)]


def restart_now(
    argv: Sequence[str],
    *,
    dev_mode_enabled: bool,
    start_detached: Callable[[Sequence[str]], bool],
    quit_application: Callable[[], None],
) -> bool:
    """Starts a fresh process and quits this one. `False` when the start
    failed, in which case **this process keeps running** — a user left with no
    application at all would be a worse outcome than a switch that needs a
    manual relaunch, and the log line says which happened.
    """
    arguments = argv_for_restart(argv, dev_mode_enabled=dev_mode_enabled)
    if not start_detached(arguments):
        logger.error(
            "Restart failed: could not start a new process (%s). This session "
            "is still running; developer mode is already written to "
            "configuration and applies the next time the app starts.",
            arguments,
        )
        return False
    logger.info(
        "Restarting with developer mode %s.", "on" if dev_mode_enabled else "off"
    )
    quit_application()
    return True
