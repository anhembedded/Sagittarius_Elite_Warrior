"""`sync` at the interactive prompt — fetch history for one or more symbols."""

from __future__ import annotations

import argparse

from pydantic import ValidationError
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from sagittarius_engine import App


class SyncCliHandler(ICliCommandHandler):
    """Turns a parsed `sync` line into one `SyncMarketDataCommand`."""

    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> None:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
        try:
            # `EPIC-027A` — the CLI has no `--market` flag yet (Phase 1 has no
            # market to choose from). Pinned to Spot, what this command has
            # always fetched.
            cmd = SyncMarketDataCommand(
                symbols=symbols,
                interval=TimeFrame(args.interval),
                market=MarketType.SPOT,
                days_back_if_empty=args.days,
            )
            print(f"🔄 Syncing historical data for {symbols}...")
            # Through this app's own `ICommandDispatcher`, never the Engine's
            # `App.dispatch`: module code names Engine types only through a
            # port (`architecture-rule.md`, `EPIC-008F`), and the Engine's
            # annotation expects a *handler* type while this app passes the
            # *command* type as the container key.
            #
            # The result is discarded on purpose.
            # `SyncMarketDataCommandHandler.execute()` returns `None` on
            # success; a real failure (network, DB) raises rather than handing
            # back `success=False` — the same contract
            # `BulkSyncMarketDataCommandHandler` already relies on for this
            # exact command. There is no `.success` to read here, unlike
            # Start/Stop Stream, which is why this call needs no cast.
            app.container.resolve(ICommandDispatcher).dispatch(
                SyncMarketDataCommand, cmd
            )
            print("✅ Sync complete.")
        except ValueError as e:
            print(f"❌ Validation Error: {e}")
        except ValidationError as e:
            print(f"❌ Validation Error: {e}")
        except Exception as e:  # noqa: BLE001 - CLI boundary: report the real failure instead of an uncaught traceback
            print(f"❌ Sync failed: {e}")
