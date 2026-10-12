"""The command-line entry point: what a word on the command line starts, and the exit status it ends with.

`python src/main.py <word> ...`

| Word | Starts | Exit status |
| :--- | :--- | :--- |
| *(none)* | prints the help | `2` (`EPIC-038B`, D8: a supervisor that starts it by mistake neither opens a window nor waits on input) |
| `gui` | the desktop window (what `run.ps1 -UI` runs) | the window's |
| `shell` | the interactive prompt | `0` |
| a command (`sync`, `exchange-status`, ...) | that command, once | its outcome (`ExitCode`, `Docs/OPERATIONS/exit_codes.md`) |

Every path ends in `run_command`, the one mapping from a result to a status: a
handler returning `None` is a success, an outcome is its code, an exception is
status 1 with the traceback in the log.
"""

import argparse
import sys
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    ICliCommandTable,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.stream_cmd import (
    execute_stream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.sync_cmd import execute_sync
from Sagittarius_Elite_Warrior.src.modules.strategy.cli.trade_once_cmd import (
    execute_trade_once,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import build_parser
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_cmd import (
    execute_exchange_status,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.interactive_shell import (
    InteractiveShell,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.order_dry_run_cmd import (
    execute_order_dry_run,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.order_preview_cmd import (
    execute_order_preview,
)
from Sagittarius_Elite_Warrior.src.shell.app_config import (
    dev_mode_banner,
    load_app_config,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import (
    acquire_instance_access,
    create_app,
    read_only_instance_access,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.command_access import (
    command_is_read_only,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.exit_status import run_command
from Sagittarius_Elite_Warrior.src.support.cli_host.launcher_verb import (
    LauncherVerb,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.report_output import (
    wants_machine_output,
)
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

#: One command, run against a booted app.
HeadlessCommand = Callable[[App, argparse.Namespace], CliOutcome | None]

#: The headless commands this entry point names. A command a module declares
#: with `declare_cli` and that is not listed here is found in the shell's
#: table (`_dispatch`), so a new command is one declaration, not an edit here.
_HEADLESS_COMMANDS: dict[str, HeadlessCommand] = {
    "sync": execute_sync,
    "stream": execute_stream,
    "exchange-status": execute_exchange_status,
    "order-preview": execute_order_preview,
    "order-dry-run": execute_order_dry_run,
    "trade-once": execute_trade_once,
}

#: The desktop application's own entry point, named by path so this module
#: imports no Qt: a server without PySide6 runs every other word.
_GUI_MAIN: Deferred[None] = Deferred(
    "Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper:main"
)


def _load_configuration() -> tuple[ConfigManager, str | None]:
    """The shell's loader, so the headless path reads exactly what the GUI
    reads — including `--dev` / `--debug`, which used to be parsed only by the
    GUI bootstrapper (Phase 0's one declared behaviour change). Returns the
    banner too, which the caller prints only for a mode that does not print
    its own (`gui`)."""
    config_manager, dev_mode = load_app_config(sys.argv)
    return config_manager, dev_mode_banner(dev_mode)


def _dispatch(app: App, args: argparse.Namespace) -> CliOutcome | None:
    command = _HEADLESS_COMMANDS.get(args.command)
    if command is not None:
        return command(app, args)
    handler = app.container.resolve(ICliCommandTable).handlers().get(args.command)
    if handler is None:
        return CliOutcome(ExitCode.USAGE, f"Unknown command: {args.command}")
    # The port takes the parsed arguments first, the command functions the app.
    return handler.handle(args, app)


def _run_headless_mode(app: App, args: argparse.Namespace) -> CliOutcome | None:
    app.boot()
    try:
        return _dispatch(app, args)
    finally:
        app.stop()


def _run_interactive_mode(app: App) -> CliOutcome | None:
    # Register the Interactive Shell Hosted Service
    shell = InteractiveShell(app)
    app.context.hosted_services.register(shell)

    # Boot Engine
    app.boot()
    try:
        # Block main thread until the shell loop exits
        shell.wait_for_exit()
    finally:
        app.stop()
    return None


def _run_gui() -> CliOutcome | None:
    """Hand over to the desktop application, which loads its own configuration
    and takes its own lock; this process does neither, or the window would
    start read-only behind its own parent. It ends with `sys.exit`, which
    passes through `run_command` untouched."""
    _GUI_MAIN()
    return None


#: The words that start a mode. `LauncherVerb` is what `--help` lists; what each
#: starts is `main()`'s branch on `args.command`.
_LAUNCHER_VERBS = (
    LauncherVerb(
        "gui", "Open the desktop application", ("--dev", "--debug", "--self-check")
    ),
    LauncherVerb("shell", "Open the interactive prompt", ("--dev", "--debug")),
)


def _app_work_for(args: argparse.Namespace) -> Callable[[App], CliOutcome | None]:
    """What a word that runs against the built app does with it."""
    if args.command == "shell":
        return _run_interactive_mode
    return lambda app: _run_headless_mode(app, args)


def main() -> int:
    """Parse the command line and run what it names; the return value is the exit status."""
    config_manager, banner = _load_configuration()
    parser = build_parser(config_manager, _LAUNCHER_VERBS)
    args = parser.parse_args()
    if args.command is None:
        # D8 — a bare `main.py` is not a request for anything: say what is on
        # offer and fail, so a supervisor that starts it by mistake neither
        # opens a window nor waits for input.
        parser.print_help()
        return int(ExitCode.USAGE)
    if args.command == "gui":
        return run_command(_run_gui)

    work = _app_work_for(args)
    if wants_machine_output(args):
        # `--json` / `--format <name>`: stdout is the report, nothing else. The
        # Engine's console logger writes to stdout, so it is off for this run
        # (the same key an operator sets in `user_config.json`); the traceback
        # of a failure still reaches stderr, and a configured log file is kept.
        config_manager.load_dict({ConfigKeys.LOG_CONSOLE_ENABLED.value: False})
        banner = None
    if banner is not None:
        print(banner)
    # `EPIC-035H` — the first copy on the data root trades; any other reads.
    # `EPIC-038C` — a command that only reads (`"read_only": true` in
    # `cli_commands.json`) is never the writable copy: its boot would apply the
    # restart rule to the bots, and it would hold the lock `status` asks about.
    commands = config_manager.get(ConfigKeys.CLI_COMMANDS.value, {})
    instance = (
        read_only_instance_access()
        if command_is_read_only(commands, args)
        else acquire_instance_access()
    )
    try:
        return run_command(lambda: work(create_app(config_manager, instance)))
    finally:
        instance.release()


if __name__ == "__main__":
    sys.exit(main())
