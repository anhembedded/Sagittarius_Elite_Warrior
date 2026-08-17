import argparse
import shlex

from pydantic import ValidationError

from Sagittarius_Elite_Warrior.src.application.use_cases.stream.start_live_stream import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.stream.stop_live_stream import (
    StopLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import (
    build_handler_parser,
)
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig


class StreamCliHandler:
    @staticmethod
    def handle(arg_str: str, app: App) -> None:
        config = app.container.resolve(IConfig)
        parser = build_handler_parser(config, "stream")

        try:
            args = parser.parse_args(shlex.split(arg_str))
        except SystemExit:
            return
        except argparse.ArgumentError as e:
            print(f"❌ Argument Error: {e}")
            return

        # Fallback if no action is provided but argparse didn't catch it
        if not hasattr(args, "action") or not args.action:
            parser.print_help()
            return

        if args.action == "start":
            symbols = [s.strip().upper() for s in args.symbols.split(",")]
            try:
                cmd = StartLiveStreamCommand(
                    symbols=symbols, interval=TimeFrame(args.interval)
                )
                response = app.dispatch(StartLiveStreamCommand, cmd)
                if response.success:
                    print(
                        f"✅ Live stream started for {symbols} at {args.interval} in the background."
                    )
                else:
                    print(f"❌ Failed to start stream: {response.message}")
            except ValueError as e:
                print(f"❌ Validation Error: {e}")
            except ValidationError as e:
                print(f"❌ Validation Error: {e}")

        elif args.action == "stop":
            cmd = StopLiveStreamCommand()
            response = app.dispatch(StopLiveStreamCommand, cmd)
            if response.success:
                print("✅ Live stream stopped.")
            else:
                print(f"❌ Failed to stop stream: {response.message}")
