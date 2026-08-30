import argparse
import shlex

from pydantic import ValidationError
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import (
    build_handler_parser,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.handlers.i_cli_command_handler import (
    ICliCommandHandler,
)
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig


class SyncCliHandler(ICliCommandHandler):
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
                days_back_if_empty=args.days,
            )
            print(f"🔄 Syncing historical data for {symbols}...")
            # SyncMarketDataCommandHandler.execute() -> None on success; a
            # real sync failure (network, DB) raises rather than returning a
            # success=False result — the same contract
            # BulkSyncMarketDataCommandHandler already relies on for this
            # exact command (see its own dispatch() call). No response
            # object to read a `.success` off of, unlike Start/Stop Stream.
            app.dispatch(SyncMarketDataCommand, cmd)
            print("✅ Sync complete.")
        except ValueError as e:
            print(f"❌ Validation Error: {e}")
        except ValidationError as e:
            print(f"❌ Validation Error: {e}")
        except Exception as e:  # noqa: BLE001 - CLI boundary: report the real failure instead of an uncaught traceback
            print(f"❌ Sync failed: {e}")
