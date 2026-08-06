import sys
from sagittarius_engine import App
from Binace_Bot.src.application.use_cases.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame


def execute_sync(app: App, args):
    symbols_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    try:
        timeframe = TimeFrame(args.interval)
    except ValueError:
        print(
            f"Invalid interval: {args.interval}. Must be one of {[t.value for t in TimeFrame]}"
        )
        sys.exit(1)

    command = SyncMarketDataCommand(
        symbols=symbols_list, interval=timeframe, days_back_if_empty=args.days
    )

    # Dispatch to Application Layer
    app.dispatch(SyncMarketDataCommand, command)
