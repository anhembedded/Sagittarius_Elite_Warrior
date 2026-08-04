import argparse
import shlex
from pydantic import ValidationError

from sagittarius_engine import App
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

class SyncCliHandler:
    @staticmethod
    def handle(arg_str: str, app: App) -> None:
        parser = argparse.ArgumentParser(prog="sync", exit_on_error=False, description="Synchronize market data from Binance")
        parser.add_argument(
            "--symbols",
            type=str,
            required=True,
            help="Comma separated list of symbols (e.g. BTCUSDT,ETHUSDT)",
        )
        parser.add_argument(
            "--interval",
            type=str,
            default="1m",
            help="Timeframe interval (e.g. 1m, 1h, 1d)",
        )
        parser.add_argument(
            "--days", type=int, default=30, help="Days back to sync if DB is empty"
        )
        
        try:
            args = parser.parse_args(shlex.split(arg_str))
        except SystemExit:
            # -h or invalid argument triggers SystemExit
            return
        except argparse.ArgumentError as e:
            print(f"❌ Argument Error: {e}")
            return
            
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
        try:
            cmd = SyncMarketDataCommand(
                symbols=symbols,
                interval=TimeFrame(args.interval),
                days_back_if_empty=args.days
            )
            print(f"🔄 Syncing historical data for {symbols}...")
            response = app.dispatch(SyncMarketDataCommand, cmd)
            if response.success:
                print(f"✅ Sync complete.")
            else:
                print(f"❌ Sync failed: {response.message}")
        except ValueError as e:
            print(f"❌ Validation Error: {e}")
        except ValidationError as e:
            print(f"❌ Validation Error: {e}")
