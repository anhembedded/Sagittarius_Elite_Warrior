import logging
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig

from Binace_Bot.src.presentation.cli.handlers.base_handler import IMenuHandler
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from pydantic import ValidationError


class SyncMenuHandler(IMenuHandler):
    """
    @brief Interactive menu handler for Synchronizing Market Data.
    """

    def handle(self, app: App) -> None:
        config = app.container.resolve(IConfig)
        default_symbols = ",".join(
            config.get("DEFAULT_SYMBOLS", ["BTCUSDT", "ETHUSDT"])
        )
        default_interval = config.get("DEFAULT_INTERVAL", "1m")
        default_days = config.get("DEFAULT_SYNC_DAYS", 30)

        print("\n--- Synchronize Market Data ---")

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

        days_input = input(
            f"Enter Days back to sync if empty [{default_days}]: "
        ).strip()
        if not days_input:
            days = default_days
        else:
            try:
                days = int(days_input)
            except ValueError:
                print("❌ Days must be an integer.")
                return

        symbols = [s.strip().upper() for s in symbols_input.split(",")]

        print(f"\n⏳ Starting sync for {symbols} at {interval_input} (Days: {days})...")

        try:
            cmd = SyncMarketDataCommand(
                symbols=symbols,
                interval=TimeFrame(interval_input),
                days_back_if_empty=days,
            )
        except ValueError as e:
            print(f"\n❌ Validation Error: {e}")
            return
        except ValidationError as e:
            print(f"\n❌ Validation Error: {e}")
            return

        try:
            # Sync runs on main thread or we can dispatch it. Since we are in the menu background thread,
            # this will block the menu thread until sync is complete, which is fine for UX.
            # But wait, app.dispatch relies on container resolving the handler.
            app.dispatch(SyncMarketDataCommand, cmd)
            print("✅ Sync Completed Successfully!")
        except Exception as e:
            print(f"❌ Error during sync: {e}")
            logging.getLogger(__name__).exception("Sync Error")
