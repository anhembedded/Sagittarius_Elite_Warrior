import argparse
import sys

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
from Sagittarius_Elite_Warrior.src.presentation.cli.stream_cmd import (
    execute_stream,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.sync_cmd import execute_sync
from Sagittarius_Elite_Warrior.src.presentation.cli.trade_once_cmd import (
    execute_trade_once,
)
from Sagittarius_Elite_Warrior.src.shell.app_config import (
    dev_mode_banner,
    load_app_config,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


def _load_configuration() -> ConfigManager:
    """The shell's loader, so the headless path reads exactly what the GUI
    reads — including `--dev` / `--debug`, which used to be parsed only by the
    GUI bootstrapper (Phase 0's one declared behaviour change)."""
    config_manager, dev_mode = load_app_config(sys.argv)
    banner = dev_mode_banner(dev_mode)
    if banner is not None:
        print(banner)
    return config_manager


def _run_interactive_mode(app: App) -> None:
    # Register the Interactive Shell Hosted Service
    shell = InteractiveShell(app)
    app.context.hosted_services.register(shell)

    # Boot Engine
    app.boot()

    # Block main thread until the shell loop exits
    shell.wait_for_exit()
    app.stop()


def _run_headless_mode(app: App, args: argparse.Namespace) -> None:
    # Headless Mode
    app.boot()

    if args.command == "sync":
        execute_sync(app, args)
        app.stop()
    elif args.command == "stream":
        execute_stream(app, args)
        app.stop()
    elif args.command == "exchange-status":
        execute_exchange_status(app)
        app.stop()
    elif args.command == "order-preview":
        execute_order_preview(app, args)
        app.stop()
    elif args.command == "order-dry-run":
        execute_order_dry_run(app, args)
        app.stop()
    elif args.command == "trade-once":
        execute_trade_once(app, args)
        app.stop()


def main() -> None:
    config_manager = _load_configuration()

    # If no arguments are provided, switch to Interactive Menu Mode
    if len(sys.argv) == 1:
        interactive_mode = True
    else:
        interactive_mode = False
        parser = build_parser(config_manager)
        args = parser.parse_args()

    app = create_app(config_manager)

    if interactive_mode:
        _run_interactive_mode(app)
    else:
        _run_headless_mode(app, args)


if __name__ == "__main__":
    main()
