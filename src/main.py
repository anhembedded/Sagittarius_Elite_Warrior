import sys
from sagittarius_engine import App
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.utils.path_utils import PathUtils
from sagittarius_engine.extensions.logger.logger_module import LoggerExtension
from sagittarius_engine.middleware.pydantic_validation_middleware import (
    PydanticValidationMiddleware,
)

from Binace_Bot.src.binance_bot_module import BinanceBotModule
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.presentation.cli.cli_parser import build_parser
from Binace_Bot.src.presentation.cli.sync_cmd import execute_sync
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_config import IConfig


def _on_market_tick(event: MarketTickEvent):
    # Log handled by the framework's configured logger
    pass


def create_app() -> App:
    # Set up configuration manager using common utility
    config_manager = ConfigManager()

    app_json = PathUtils.get_relative_path(__file__, "config", "app_config.json")
    user_json = PathUtils.get_relative_path(__file__, "config", "user_config.json")

    config_manager.load_json(app_json)
    config_manager.load_json(user_json)

    container = StdLibContainer()
    event_bus = MemoryEventBus()

    # Register core ports
    container.singleton(IEventBus, event_bus)
    container.singleton(IConfig, config_manager)

    # Register core events
    event_bus.on(MarketTickEvent, _on_market_tick)

    app = App(container, event_bus)

    # Load Framework Extensions
    app.use(LoggerExtension())

    # Load Domain Module (Registers Repositories & UseCases)
    app.use(BinanceBotModule())

    # Register Global Validation Middleware
    app.use_middleware(PydanticValidationMiddleware(container))

    return app


def main() -> None:
    # If no arguments are provided, switch to Interactive Menu Mode
    if len(sys.argv) == 1:
        interactive_mode = True
    else:
        interactive_mode = False
        parser = build_parser()
        args = parser.parse_args()

    app = create_app()

    if interactive_mode:
        # Register the Interactive Terminal Menu Hosted Service
        from Binace_Bot.src.presentation.cli.menu_service import TerminalMenuService

        menu = TerminalMenuService(app)
        app.context.hosted_services.register(menu)

        # Boot Engine
        app.boot()

        # Block main thread until the menu loop exits
        menu.wait_for_exit()
        app.stop()

    else:
        # Headless Mode
        app.boot()

        if args.command == "sync":
            execute_sync(app, args)
            app.stop()
        elif args.command == "stream":
            from Binace_Bot.src.presentation.cli.stream_cmd import execute_stream

            execute_stream(app, args)
            app.stop()


if __name__ == "__main__":
    main()
