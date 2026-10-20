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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    ICliCommandTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import (
    VERBOSE_DEST,
    build_parser,
)
from Sagittarius_Elite_Warrior.src.shell.app_config import (
    dev_mode_banner,
    load_app_config,
    log_directory,
)
from Sagittarius_Elite_Warrior.src.shell.cli_log_routing import (
    CliLogRouting,
    prepare_cli_log,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import (
    acquire_instance_access,
    create_app,
    read_only_instance_access,
)
from Sagittarius_Elite_Warrior.src.shell.console_log_stream import console_log_to
from Sagittarius_Elite_Warrior.src.support.cli_host.command_access import (
    command_is_read_only,
    command_keeps_log_off_console,
    command_needed_modules,
    command_owns_its_lifecycle,
    command_requires_writable_instance,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.exit_status import run_command
from Sagittarius_Elite_Warrior.src.support.cli_host.launcher_verb import (
    LauncherVerb,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.report_output import (
    wants_machine_output,
)
from Sagittarius_Elite_Warrior.src.support.log_view.log_viewer_cli import (
    configure_logs_parser,
    run_logs,
    system_environment,
)
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.presentation.cli.interactive_shell import (
        InteractiveShell,
    )

#: One command, run against a booted app. Named by import path (`Deferred`), so a
#: word imports the module that runs it and no other: `bot list` pays nothing for the
#: exchange SDK that `sync` and `trade-once` need (`PRO-014`).
HeadlessCommand = Deferred[CliOutcome | None]

_COMMANDS_PACKAGE = "Sagittarius_Elite_Warrior.src"

#: The headless commands this entry point names. A command a module declares
#: with `declare_cli` and that is not listed here is found in the shell's
#: table (`_dispatch`), so a new command is one declaration, not an edit here.
_HEADLESS_COMMANDS: dict[str, HeadlessCommand] = {
    "sync": Deferred(
        f"{_COMMANDS_PACKAGE}.modules.market_data.cli.sync_cmd:execute_sync"
    ),
    "stream": Deferred(
        f"{_COMMANDS_PACKAGE}.modules.market_data.cli.stream_cmd:execute_stream"
    ),
    "exchange-status": Deferred(
        f"{_COMMANDS_PACKAGE}.presentation.cli.exchange_status_cmd:execute_exchange_status"
    ),
    "order-preview": Deferred(
        f"{_COMMANDS_PACKAGE}.presentation.cli.order_preview_cmd:execute_order_preview"
    ),
    "order-dry-run": Deferred(
        f"{_COMMANDS_PACKAGE}.presentation.cli.order_dry_run_cmd:execute_order_dry_run"
    ),
    "trade-once": Deferred(
        f"{_COMMANDS_PACKAGE}.modules.strategy.cli.trade_once_cmd:execute_trade_once"
    ),
}

#: The interactive prompt, named by path for the same reason (`PRO-014`): only the `shell` word
#: builds it, and its import brings the Engine's hosted-service runtime.
_INTERACTIVE_SHELL: "Deferred[InteractiveShell]" = Deferred(
    f"{_COMMANDS_PACKAGE}.presentation.cli.interactive_shell:InteractiveShell"
)

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
    shell = _INTERACTIVE_SHELL(app)
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
    LauncherVerb(
        "logs",
        "Show a plain log read from a pipe or --file, params coloured on a terminal",
        configure=configure_logs_parser,
    ),
)


def _app_work_for(
    args: argparse.Namespace, commands: Mapping[str, object]
) -> Callable[[App], CliOutcome | None]:
    """What a word that runs against the built app does with it."""
    if args.command == "shell":
        return _run_interactive_mode
    if command_owns_its_lifecycle(commands, args):
        # `run` (`EPIC-038D`) boots and stops the app itself: it checks the machine
        # before the bots are restored and waits between boot and stop.
        return lambda app: _dispatch(app, args)
    return lambda app: _run_headless_mode(app, args)


def _quiet_log_for(quiet: bool, args: argparse.Namespace) -> CliLogRouting | None:
    """`BOT-185`, `BOT-186` - a command that reads, or a short-lived one that writes, shows
    its result and nothing else: its log goes to a file (`--verbose` keeps it on the
    console). A command that keeps its console log (`run`'s is the supervisor's) is left."""
    if not quiet or getattr(args, VERBOSE_DEST, False):
        return None
    return prepare_cli_log(log_directory())


@dataclass(frozen=True, slots=True)
class _Boot:
    """What the command line decided about building the app, besides the configuration."""

    instance: IInstanceAccess
    report_on_stdout: bool
    cli_log: CliLogRouting | None
    #: The bounded contexts the command declared (`PRO-014`); `None` builds them all.
    needed_modules: frozenset[str] | None


def _build_app(config_manager: ConfigManager, boot: _Boot) -> App:
    """The object graph; its console log leaves by stderr when stdout is a report."""

    def create() -> App:
        return create_app(
            config_manager, boot.instance, boot.cli_log, boot.needed_modules
        )

    if boot.report_on_stdout:
        with console_log_to(sys.stderr):
            return create()
    return create()


def _lock_held(command: str, instance: IInstanceAccess) -> CliOutcome:
    return CliOutcome(
        ExitCode.LOCK_HELD,
        f"{instance.reason} `{command}` needs to be the writable copy and starts nothing "
        "on a read-only one.",
    )


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
    if args.command == "logs":
        # `BOT-199`: a viewer of text; it builds no app and takes no lock.
        return run_command(lambda: run_logs(args, system_environment()))

    commands = config_manager.get(ConfigKeys.CLI_COMMANDS.value, {})
    work = _app_work_for(args, commands)
    # `--json` / `--format <name>`: stdout is the report, nothing else. The
    # Engine's console logger writes to stdout, so for such a run the app is built
    # with that logger on stderr (`EPIC-038D`): the log is kept, and so is the
    # document. The traceback of a failure reaches stderr as before.
    machine_output = wants_machine_output(args)
    if machine_output:
        banner = None
    if banner is not None:
        print(banner)
    # `EPIC-035H` — the first copy on the data root trades; any other reads.
    # `EPIC-038C` — a command that only reads (`"read_only": true` in
    # `cli_commands.json`) is never the writable copy: its boot would apply the
    # restart rule to the bots, and it would hold the lock `status` asks about.
    read_only = command_is_read_only(commands, args)
    cli_log = _quiet_log_for(command_keeps_log_off_console(commands, args), args)
    instance = read_only_instance_access() if read_only else acquire_instance_access()
    try:
        if instance.read_only and command_requires_writable_instance(commands, args):
            # `EPIC-038D` - a host that is not the writable copy would look alive to its
            # supervisor while trading nothing; refuse, start nothing, and say why.
            return run_command(lambda: _lock_held(args.command, instance))
        boot = _Boot(
            instance, machine_output, cli_log, command_needed_modules(commands, args)
        )
        return run_command(lambda: work(_build_app(config_manager, boot)))
    finally:
        instance.release()


if __name__ == "__main__":
    sys.exit(main())
