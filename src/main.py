import argparse
import sys
import logging
from sagittarius_engine import App
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

from Binace_Bot.src.infrastructure.extensions.data_sync_extension import DataSyncExtension
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.application.use_cases.sync_market_data_handler import SyncMarketDataCommandHandler
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def main():
    parser = argparse.ArgumentParser(description="Binance Trading Bot CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # sync command
    sync_parser = subparsers.add_parser("sync", help="Synchronize market data from Binance")
    sync_parser.add_argument("--symbols", type=str, required=True, help="Comma separated list of symbols (e.g. BTCUSDT,ETHUSDT)")
    sync_parser.add_argument("--interval", type=str, default="1m", help="Timeframe interval (e.g. 1m, 1h, 1d)")
    sync_parser.add_argument("--days", type=int, default=30, help="Days back to sync if DB is empty")
    
    args = parser.parse_args()
    
    if args.command == "sync":
        setup_logging()
        
        # 1. Boot Sagittarius Engine
        container = StdLibContainer()
        event_bus = MemoryEventBus()
        app = App(container, event_bus)
        
        app.use(DataSyncExtension())
        app.boot()
        
        # 2. Parse arguments
        symbols_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        try:
            timeframe = TimeFrame(args.interval)
        except ValueError:
            print(f"Invalid interval: {args.interval}. Must be one of {[t.value for t in TimeFrame]}")
            sys.exit(1)
            
        # 3. Create Command
        command = SyncMarketDataCommand(
            symbols=symbols_list,
            interval=timeframe,
            days_back_if_empty=args.days
        )
        
        # 4. Resolve Handler and Execute (In full CQRS, App.dispatch(command) handles this)
        handler = app.container.resolve(SyncMarketDataCommandHandler)
        handler.execute(command)
        
        # 5. Graceful shutdown
        app.stop()

if __name__ == "__main__":
    main()
