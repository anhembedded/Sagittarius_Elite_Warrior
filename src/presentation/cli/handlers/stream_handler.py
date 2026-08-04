from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig
from Binace_Bot.src.presentation.cli.handlers.base_handler import IMenuHandler
from Binace_Bot.src.application.use_cases.start_live_stream import (
    StartLiveStreamCommand,
    StartLiveStreamResponse,
)
from Binace_Bot.src.application.use_cases.stop_live_stream import (
    StopLiveStreamCommand,
    StopLiveStreamResponse,
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from pydantic import ValidationError


class StartStreamMenuHandler(IMenuHandler):
    """
    @brief Interactive menu handler to start Live Market Stream.
    """

    def handle(self, app: App) -> None:
        config = app.container.resolve(IConfig)
        default_symbols = ",".join(
            config.get("DEFAULT_SYMBOLS", ["BTCUSDT", "ETHUSDT"])
        )
        default_interval = config.get("DEFAULT_INTERVAL", "1m")

        print("\n--- Start Live Market Stream ---")

        symbols_input = input(
            f"Enter Symbols (comma-separated, e.g. BTCUSDT,ETHUSDT) [{default_symbols}]: "
        ).strip()
        if not symbols_input:
            symbols_input = default_symbols

        interval_input = input(
            f"Enter Interval (e.g. 1m, 1h, 1d) [{default_interval}]: "
        ).strip()
        if not interval_input:
            interval_input = default_interval

        symbols = [s.strip().upper() for s in symbols_input.split(",")]

        try:
            cmd = StartLiveStreamCommand(
                symbols=symbols, interval=TimeFrame(interval_input)
            )
        except ValueError as e:
            print(f"\n❌ Validation Error: {e}")
            return
        except ValidationError as e:
            print(f"\n❌ Validation Error: {e}")
            return

        response: StartLiveStreamResponse = app.dispatch(StartLiveStreamCommand, cmd)

        if response.success:
            print(f"\n✅ {response.message} ({symbols} at {interval_input})")
            print("The system will now process MarketTickEvent in the background.")
        else:
            print(f"\n❌ {response.message}")


class StopStreamMenuHandler(IMenuHandler):
    """
    @brief Interactive menu handler to stop Live Market Stream.
    """

    def handle(self, app: App) -> None:
        print("\n--- Stop Live Market Stream ---")

        # Dispatch to Application Layer
        cmd = StopLiveStreamCommand()
        response: StopLiveStreamResponse = app.dispatch(StopLiveStreamCommand, cmd)

        if response.success:
            print(f"\n✅ {response.message}")
        else:
            print(f"\n❌ {response.message}")
