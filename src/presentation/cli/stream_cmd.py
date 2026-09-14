import sys
import time

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream import (
    StartLiveStreamCommand,
)
from sagittarius_engine import App


def execute_stream(app: App, args):
    """
    Executes the stream command.
    The actual WebSocket streaming is managed by the LiveStreamExtension's HostedService.
    This function simply blocks the main thread to keep the application alive.
    """
    symbols_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    try:
        timeframe = TimeFrame(args.interval)
    except ValueError:
        print(
            f"Invalid interval: {args.interval}. Must be one of {[t.value for t in TimeFrame]}"
        )
        sys.exit(1)

    cmd = StartLiveStreamCommand(owner="cli", symbols=symbols_list, interval=timeframe)
    try:
        response = app.dispatch(StartLiveStreamCommand, cmd)
    except Exception as e:  # noqa: BLE001 - CLI boundary: report the real failure instead of an uncaught traceback
        print(f"❌ Failed to start stream: {e}")
        sys.exit(1)

    if not response.success:
        print(f"Failed to start stream: {response.message}")
        sys.exit(1)

    print(
        f"Live stream started for {symbols_list} at {timeframe.value} in the background. Press Ctrl+C to stop."
    )
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nReceived KeyboardInterrupt. Shutting down gracefully...")
