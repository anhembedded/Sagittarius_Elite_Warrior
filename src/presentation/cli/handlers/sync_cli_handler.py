import argparse
import shlex
from pydantic import ValidationError

from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.presentation.cli.cli_parser import build_handler_parser

class SyncCliHandler:
    @staticmethod
    def handle(arg_str: str, app: App) -> None:
        config = app.container.resolve(IConfig)
        parser = build_handler_parser(config, "sync")
        
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
            if response is None or getattr(response, 'success', True):
                print(f"✅ Sync complete.")
            else:
                print(f"❌ Sync failed: {getattr(response, 'message', 'Unknown error')}")
        except ValueError as e:
            print(f"❌ Validation Error: {e}")
        except ValidationError as e:
            print(f"❌ Validation Error: {e}")
