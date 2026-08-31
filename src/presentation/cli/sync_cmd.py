import sys

from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from sagittarius_engine import App


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
    try:
        app.dispatch(SyncMarketDataCommand, command)
    except Exception as e:  # noqa: BLE001 - CLI boundary: report the real failure instead of an uncaught traceback
        print(f"❌ Sync failed: {e}")
        sys.exit(1)
