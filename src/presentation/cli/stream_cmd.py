import sys
import time

from Sagittarius_Elite_Warrior.src.application.use_cases.stream.start_live_stream import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
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

    cmd = StartLiveStreamCommand(symbols=symbols_list, interval=timeframe)
    response = app.dispatch(StartLiveStreamCommand, cmd)

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
