import argparse
import shlex
from pydantic import ValidationError

from sagittarius_engine import App
from Binace_Bot.src.application.use_cases.start_live_stream import StartLiveStreamCommand
from Binace_Bot.src.application.use_cases.stop_live_stream import StopLiveStreamCommand
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

class StreamCliHandler:
    @staticmethod
    def handle(arg_str: str, app: App) -> None:
        parser = argparse.ArgumentParser(prog="stream", exit_on_error=False, description="Manage live websocket market stream")
        subparsers = parser.add_subparsers(dest="action", required=True)
        
        start_parser = subparsers.add_parser("start", help="Start live stream")
        start_parser.add_argument(
            "--symbols",
            type=str,
            required=True,
            help="Comma-separated list of symbols (e.g. BTCUSDT)",
        )
        start_parser.add_argument(
            "--interval", type=str, required=True, help="Timeframe (e.g. 1m)"
        )
        
        subparsers.add_parser("stop", help="Stop live stream")

        try:
            args = parser.parse_args(shlex.split(arg_str))
        except SystemExit:
            return
        except argparse.ArgumentError as e:
            print(f"❌ Argument Error: {e}")
            return

        if args.action == "start":
            symbols = [s.strip().upper() for s in args.symbols.split(",")]
            try:
                cmd = StartLiveStreamCommand(
                    symbols=symbols, interval=TimeFrame(args.interval)
                )
                response = app.dispatch(StartLiveStreamCommand, cmd)
                if response.success:
                    print(f"✅ Live stream started for {symbols} at {args.interval} in the background.")
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
                print(f"✅ Live stream stopped.")
            else:
                print(f"❌ Failed to stop stream: {response.message}")
