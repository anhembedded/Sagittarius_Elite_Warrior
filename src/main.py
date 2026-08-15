import argparse
import sys

from Sagittarius_Elite_Warrior.src.binance_bot_module import BinanceBotModule
from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import build_parser
from Sagittarius_Elite_Warrior.src.presentation.cli.interactive_shell import (
    InteractiveShell,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.stream_cmd import (
    execute_stream,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.sync_cmd import execute_sync
from sagittarius_engine import App
from sagittarius_engine.extensions.dependency_validator import (
    DependencyValidatorExtension,
)
from sagittarius_engine.extensions.health.health_module import HealthExtension
from sagittarius_engine.extensions.logger.logger_module import LoggerExtension
from sagittarius_engine.extensions.thread_manager.thread_manager_module import (
    ThreadManagerExtension,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.middleware.pydantic_validation_middleware import (
    PydanticValidationMiddleware,
)
from sagittarius_engine.utils.path_utils import PathUtils


def create_app(config_manager: ConfigManager) -> App:
    container = StdLibContainer()
    event_bus = MemoryEventBus()

    # Register core ports
    container.singleton(IContainer, container)
    container.singleton(IEventBus, event_bus)
    container.singleton(IConfig, config_manager)

    app = App(container, event_bus)

    # Load Framework Extensions
    app.use(
        DependencyValidatorExtension(
            ["PySide6", "pyqtgraph", "qdarktheme", "sqlalchemy"]
        )
    )

    app.use(LoggerExtension())
    app.use(ThreadManagerExtension())

    # Load Domain Module (Registers Repositories & UseCases)
    app.use(BinanceBotModule())

    # Load Health Check Diagnostic Extension after domain modules
    app.use(HealthExtension())

    # Register Global Validation Middleware
    app.use_middleware(PydanticValidationMiddleware(container))

    return app


def _load_configuration() -> ConfigManager:
    config_manager = ConfigManager()
    app_json = PathUtils.get_relative_path(__file__, "config", "app_config.json")
    user_json = PathUtils.get_relative_path(__file__, "config", "user_config.json")
    cli_json = PathUtils.get_relative_path(__file__, "config", "cli_commands.json")

    config_manager.load_json(app_json)
    config_manager.load_json(user_json, writable=True)

    try:
        config_manager.load_json(cli_json)
    except FileNotFoundError:
        pass  # Will fail if missing

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
