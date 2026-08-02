# PROJECT CONTEXT

**Roots:**
- `C:\Users\hoang\Documents\Sagittarius_ForkBoy\Binace_Bot`

**Pattern:** `*.py`
**Generated:** 2026-08-03 00:24:14

## Directory Tree: C:\Users\hoang\Documents\Sagittarius_ForkBoy\Binace_Bot

```
Binace_Bot
├── src
│   ├── application
│   │   ├── contracts
│   │   │   └── i_live_stream_service.py
│   │   ├── interfaces
│   │   │   ├── i_exchange_client.py
│   │   │   └── i_market_data_repository.py
│   │   └── use_cases
│   │       ├── manage_live_stream.py
│   │       ├── sync_market_data_handler.py
│   │       └── sync_market_data.py
│   ├── binance_bot_module.py
│   ├── domain
│   │   ├── entities
│   │   │   └── market_data.py
│   │   ├── events
│   │   │   └── market_tick_event.py
│   │   └── value_objects
│   │       └── timeframe.py
│   ├── infrastructure
│   │   ├── binance
│   │   │   ├── binance_websocket_service.py
│   │   │   └── client.py
│   │   └── persistence
│   │       └── sqlalchemy_repository.py
│   ├── main.py
│   └── presentation
│       └── cli
│           ├── cli_parser.py
│           ├── handlers
│           │   ├── base_handler.py
│           │   ├── stream_handler.py
│           │   └── sync_handler.py
│           ├── menu_service.py
│           ├── stream_cmd.py
│           └── sync_cmd.py
└── tests
    ├── integration
    │   └── infrastructure
    │       ├── binance
    │       │   └── test_python_binance_client.py
    │       └── persistence
    │           └── test_sqlalchemy_repository.py
    └── unit
        ├── application
        │   └── use_cases
        │       └── test_sync_market_data_handler.py
        ├── infrastructure
        │   └── binance
        │       └── test_binance_websocket_service.py
        └── presentation
            └── cli
                ├── handlers
                │   ├── test_stream_handler.py
                │   └── test_sync_handler.py
                └── test_menu_service.py
```

---

# FILE: src\application\contracts\i_live_stream_service.py

```python
from abc import ABC, abstractmethod
from typing import List

class ILiveStreamService(ABC):

@abstractmethod
    def start_stream(self, symbols: List[str], interval_str: str) -> bool:
        
        pass
        
    @abstractmethod
    def stop_stream(self) -> bool:
        
        pass
``````

# FILE: src\application\interfaces\i_exchange_client.py

```python
from abc import ABC, abstractmethod
from datetime import datetime
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

class IExchangeClient(ABC):

@abstractmethod
    def get_historical_klines(
        self, symbol: str, interval: TimeFrame, start_str: str | datetime
    ) -> list[MarketData]:
        
        pass
``````

# FILE: src\application\interfaces\i_market_data_repository.py

```python
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

class IMarketDataRepository(ABC):

@abstractmethod
    def save_klines(self, klines: list[MarketData]) -> None:
        
        pass

    @abstractmethod
    def get_latest_kline_time(self, symbol: str, interval: TimeFrame) -> Optional[datetime]:
        
        pass
        
    @abstractmethod
    def get_klines(self, symbol: str, interval: TimeFrame, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> list[MarketData]:
        
        pass
``````

# FILE: src\application\use_cases\manage_live_stream.py

```python
from dataclasses import dataclass
from typing import List
from Binace_Bot.src.application.contracts.i_live_stream_service import ILiveStreamService
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

@dataclass(frozen=True)
class StartLiveStreamCommand:
    
    symbols: List[str]
    interval: TimeFrame

@dataclass(frozen=True)
class StartLiveStreamResponse:
    success: bool
    message: str

class StartLiveStreamCommandHandler:
    def __init__(self, stream_service: ILiveStreamService):
        self._stream_service = stream_service
        
    def execute(self, request: StartLiveStreamCommand) -> StartLiveStreamResponse:
        success = self._stream_service.start_stream(request.symbols, request.interval.value)
        if success:
            return StartLiveStreamResponse(success=True, message="Stream started successfully.")
        else:
            return StartLiveStreamResponse(success=False, message="Stream is already running or failed to start.")

@dataclass(frozen=True)
class StopLiveStreamCommand:
    
    pass

@dataclass(frozen=True)
class StopLiveStreamResponse:
    success: bool
    message: str

class StopLiveStreamCommandHandler:
    def __init__(self, stream_service: ILiveStreamService):
        self._stream_service = stream_service
        
    def execute(self, request: StopLiveStreamCommand) -> StopLiveStreamResponse:
        success = self._stream_service.stop_stream()
        if success:
            return StopLiveStreamResponse(success=True, message="Stream stopped successfully.")
        else:
            return StopLiveStreamResponse(success=False, message="Stream is not running.")
``````

# FILE: src\application\use_cases\sync_market_data_handler.py

```python
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sagittarius_engine.interfaces import ILogger
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.application.interfaces.i_exchange_client import IExchangeClient
from Binace_Bot.src.application.interfaces.i_market_data_repository import IMarketDataRepository

class SyncMarketDataCommandHandler:

def __init__(self, exchange_client: IExchangeClient, repo: IMarketDataRepository, logger: Optional[ILogger] = None) -> None:
        self.exchange_client = exchange_client
        self.repo = repo
        self.logger = logger or logging.getLogger("SyncMarketData")

    def execute(self, command: SyncMarketDataCommand) -> None:
        
        self.logger.info(f"Starting sync for symbols: {command.symbols} at interval {command.interval.value}")
        
        for symbol in command.symbols:
            latest_time = self.repo.get_latest_kline_time(symbol, command.interval)
            
            if latest_time is None:

                start_time = datetime.now(timezone.utc) - timedelta(days=command.days_back_if_empty)
                self.logger.info(f"[{symbol}] No existing data found. Syncing from {command.days_back_if_empty} days ago: {start_time}")
            else:

                start_time = latest_time
                self.logger.info(f"[{symbol}] Syncing from latest timestamp: {start_time}")
                
            klines = self.exchange_client.get_historical_klines(symbol, command.interval, start_time)
            
            if klines:
                self.repo.save_klines(klines)
                self.logger.info(f"[{symbol}] Successfully synced {len(klines)} klines.")
            else:
                self.logger.info(f"[{symbol}] Already up to date.")
``````

# FILE: src\application\use_cases\sync_market_data.py

```python
from dataclasses import dataclass
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

@dataclass(frozen=True)
class SyncMarketDataCommand:
    
    symbols: list[str]
    interval: TimeFrame
    days_back_if_empty: int = 30
``````

# FILE: src\binance_bot_module.py

```python
from sagittarius_engine.base import BaseModule
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_config import IConfig

from Binace_Bot.src.application.interfaces.i_market_data_repository import IMarketDataRepository
from Binace_Bot.src.infrastructure.persistence.sqlalchemy_repository import SQLAlchemyMarketDataRepository
from Binace_Bot.src.application.interfaces.i_exchange_client import IExchangeClient
from Binace_Bot.src.infrastructure.binance.client import PythonBinanceClient
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.application.use_cases.sync_market_data_handler import SyncMarketDataCommandHandler
from Binace_Bot.src.application.use_cases.manage_live_stream import (
    StartLiveStreamCommand, StartLiveStreamCommandHandler,
    StopLiveStreamCommand, StopLiveStreamCommandHandler
)
from Binace_Bot.src.application.contracts.i_live_stream_service import ILiveStreamService
from Binace_Bot.src.infrastructure.binance.binance_websocket_service import BinanceWebsocketService

class BinanceBotModule(BaseModule):
    
    def __init__(self, load_stream: bool = False):
        self.load_stream = load_stream

    def register(self, app: App) -> None:

        app.container.singleton(IMarketDataRepository, SQLAlchemyMarketDataRepository)
        app.container.singleton(IExchangeClient, PythonBinanceClient)

app.container.bind(SyncMarketDataCommand, SyncMarketDataCommandHandler)
        app.container.bind(StartLiveStreamCommand, StartLiveStreamCommandHandler)
        app.container.bind(StopLiveStreamCommand, StopLiveStreamCommandHandler)

app.container.singleton(ILiveStreamService, BinanceWebsocketService)
        app.container.singleton(BinanceWebsocketService, BinanceWebsocketService)

    def boot(self, app: App) -> None:

service = app.container.resolve(BinanceWebsocketService)
        if self.load_stream:

app.context.hosted_services.register(service)
``````

# FILE: src\domain\entities\market_data.py

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class MarketData:
    
    symbol: str
    interval: str
    open_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    close_time: datetime
    quote_asset_volume: float
    number_of_trades: int
    taker_buy_base_asset_volume: float
    taker_buy_quote_asset_volume: float
    is_closed: bool = True
``````

# FILE: src\domain\events\market_tick_event.py

```python
from dataclasses import dataclass
from sagittarius_engine.domain.base_event import BaseEvent
from Binace_Bot.src.domain.entities.market_data import MarketData

@dataclass(frozen=True)
class MarketTickEvent(BaseEvent):
    
    market_data: MarketData
``````

# FILE: src\domain\value_objects\timeframe.py

```python
from enum import Enum

class TimeFrame(str, Enum):
    
    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    EIGHT_HOURS = "8h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    THREE_DAYS = "3d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"
``````

# FILE: src\infrastructure\binance\binance_websocket_service.py

```python
import asyncio
import logging
from typing import List, Optional
from datetime import datetime, timezone

from binance import AsyncClient, BinanceSocketManager
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService
from Binace_Bot.src.application.contracts.i_live_stream_service import ILiveStreamService

from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent

logger = logging.getLogger(__name__)

class BinanceWebsocketService(IHostedService, ILiveStreamService):
    def __init__(self, event_bus: IEventBus, config: IConfig):
        self._event_bus = event_bus
        self._config = config
        self._client: Optional[AsyncClient] = None
        self._bsm: Optional[BinanceSocketManager] = None
        self._running = False
        self._task = None
        self._engine_context: Optional[IEngineContext] = None

    def start(self, context: IEngineContext) -> None:
        
        self._engine_context = context
        logger.info("BinanceWebsocketService initialized and awaiting commands.")

    def start_stream(self, symbols: List[str], interval_str: str) -> bool:
        
        if self._running:
            logger.warning("Stream is already running. Stop it first.")
            return False
            
        if not self._engine_context:
            logger.error("Engine context not available.")
            return False

        interval = TimeFrame(interval_str)
        self._running = True
        logger.info(f"Starting Binance WebSocket stream for {symbols} at {interval.value}")
        
        self._task = self._engine_context.async_runtime.run_coroutine(self._run_stream(symbols, interval))
        return True

    async def _run_stream(self, symbols: List[str], interval: TimeFrame) -> None:

self._client = await AsyncClient.create()
        self._bsm = BinanceSocketManager(self._client)

streams = [f"{symbol.lower()}@kline_{interval.value}" for symbol in symbols]
        
        if len(streams) == 1:
            socket = self._bsm.kline_socket(symbols[0].upper(), interval=interval.value)
        else:
            socket = self._bsm.multiplex_socket(streams)
            
        async with socket as tscm:
            while self._running:
                try:
                    res = await tscm.recv()
                    
                    if res:

                        if 'data' in res:
                            res = res['data']

if res.get('e') == 'kline':
                            market_data = self._parse_kline(res)

self._event_bus.emit(MarketTickEvent(market_data=market_data))
                            
                except Exception as e:
                    logger.error(f"Error receiving from websocket: {e}")

                    await asyncio.sleep(1)

    def _parse_kline(self, msg: dict) -> MarketData:
        k = msg['k']
        return MarketData(
            symbol=k['s'],
            interval=k['i'],
            open_time=datetime.fromtimestamp(k['t'] / 1000.0, tz=timezone.utc),
            open_price=float(k['o']),
            high_price=float(k['h']),
            low_price=float(k['l']),
            close_price=float(k['c']),
            volume=float(k['v']),
            close_time=datetime.fromtimestamp(k['T'] / 1000.0, tz=timezone.utc),
            quote_asset_volume=float(k['q']),
            number_of_trades=int(k['n']),
            taker_buy_base_asset_volume=float(k['V']),
            taker_buy_quote_asset_volume=float(k['Q']),
            is_closed=bool(k['x'])
        )

    def stop_stream(self) -> bool:
        
        if not self._running:
            logger.warning("Stream is not running.")
            return False
            
        logger.info("Stopping Binance WebSocket stream...")
        self._running = False
        
        if self._task:
            self._task.cancel()
            
        if self._client and self._engine_context:
            self._engine_context.async_runtime.run_coroutine(self._client.close_connection())
            
        logger.info("Binance WebSocket stream stopped.")
        return True

    def stop(self, context: IEngineContext) -> None:
        
        self.stop_stream()
``````

# FILE: src\infrastructure\binance\client.py

```python
from binance.client import Client
from datetime import datetime, timezone
from Binace_Bot.src.application.interfaces.i_exchange_client import IExchangeClient
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

class PythonBinanceClient(IExchangeClient):

def __init__(self, api_key: str = "", api_secret: str = "") -> None:

self.client = Client(api_key, api_secret)
        
    def get_historical_klines(self, symbol: str, interval: TimeFrame, start_str: str | datetime) -> list[MarketData]:

if isinstance(start_str, datetime):

            start_str = start_str.astimezone(timezone.utc).strftime("%d %b %Y %H:%M:%S")
            
        raw_klines = self.client.get_historical_klines(symbol, interval.value, start_str)
        
        market_data_list = []
        for k in raw_klines:
            market_data_list.append(MarketData(
                symbol=symbol,
                interval=interval.value,
                open_time=datetime.fromtimestamp(k[0] / 1000.0, tz=timezone.utc),
                open_price=float(k[1]),
                high_price=float(k[2]),
                low_price=float(k[3]),
                close_price=float(k[4]),
                volume=float(k[5]),
                close_time=datetime.fromtimestamp(k[6] / 1000.0, tz=timezone.utc),
                quote_asset_volume=float(k[7]),
                number_of_trades=int(k[8]),
                taker_buy_base_asset_volume=float(k[9]),
                taker_buy_quote_asset_volume=float(k[10])
            ))
            
        return market_data_list
``````

# FILE: src\infrastructure\persistence\sqlalchemy_repository.py

```python
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import Optional
from datetime import datetime, timezone
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.application.interfaces.i_market_data_repository import IMarketDataRepository
import os

Base = declarative_base()

class KlineModel(Base):
    __tablename__ = 'klines'

symbol = sa.Column(sa.String, primary_key=True)
    interval = sa.Column(sa.String, primary_key=True)
    open_time = sa.Column(sa.DateTime, primary_key=True)
    
    open_price = sa.Column(sa.Float, nullable=False)
    high_price = sa.Column(sa.Float, nullable=False)
    low_price = sa.Column(sa.Float, nullable=False)
    close_price = sa.Column(sa.Float, nullable=False)
    volume = sa.Column(sa.Float, nullable=False)
    close_time = sa.Column(sa.DateTime, nullable=False)
    quote_asset_volume = sa.Column(sa.Float, nullable=False)
    number_of_trades = sa.Column(sa.Integer, nullable=False)
    taker_buy_base_asset_volume = sa.Column(sa.Float, nullable=False)
    taker_buy_quote_asset_volume = sa.Column(sa.Float, nullable=False)

class SQLAlchemyMarketDataRepository(IMarketDataRepository):

def __init__(self, db_url: Optional[str] = None) -> None:
        if db_url is None:

            db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..", "database", "trading.db"))
            db_url = f"sqlite:///{db_path}"

engine = sa.create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 15}
        )

@sa.event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
            
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def save_klines(self, klines: list[MarketData]) -> None:
        
        if not klines:
            return
            
        with self.Session() as session:
            for kline in klines:
                model = KlineModel(
                    symbol=kline.symbol,
                    interval=kline.interval,
                    open_time=kline.open_time,
                    open_price=kline.open_price,
                    high_price=kline.high_price,
                    low_price=kline.low_price,
                    close_price=kline.close_price,
                    volume=kline.volume,
                    close_time=kline.close_time,
                    quote_asset_volume=kline.quote_asset_volume,
                    number_of_trades=kline.number_of_trades,
                    taker_buy_base_asset_volume=kline.taker_buy_base_asset_volume,
                    taker_buy_quote_asset_volume=kline.taker_buy_quote_asset_volume
                )
                session.merge(model)
            session.commit()

    def get_latest_kline_time(self, symbol: str, interval: TimeFrame) -> Optional[datetime]:
        with self.Session() as session:
            latest = session.query(sa.func.max(KlineModel.open_time)).filter_by(
                symbol=symbol,
                interval=interval.value
            ).scalar()
            if latest:
                return latest.replace(tzinfo=timezone.utc)
            return None

    def get_klines(self, symbol: str, interval: TimeFrame, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> list[MarketData]:
        with self.Session() as session:
            query = session.query(KlineModel).filter_by(symbol=symbol, interval=interval.value)
            
            if start_time:
                query = query.filter(KlineModel.open_time >= start_time)
            if end_time:
                query = query.filter(KlineModel.open_time <= end_time)
                
            query = query.order_by(KlineModel.open_time.asc())
            
            results = []
            for row in query.all():
                results.append(MarketData(
                    symbol=row.symbol,
                    interval=row.interval,
                    open_time=row.open_time.replace(tzinfo=timezone.utc) if row.open_time else None,
                    open_price=row.open_price,
                    high_price=row.high_price,
                    low_price=row.low_price,
                    close_price=row.close_price,
                    volume=row.volume,
                    close_time=row.close_time.replace(tzinfo=timezone.utc) if row.close_time else None,
                    quote_asset_volume=row.quote_asset_volume,
                    number_of_trades=row.number_of_trades,
                    taker_buy_base_asset_volume=row.taker_buy_base_asset_volume,
                    taker_buy_quote_asset_volume=row.taker_buy_quote_asset_volume
                ))
            return results
``````

# FILE: src\main.py

```python
import sys
from sagittarius_engine import App
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.utils.path_utils import PathUtils
from sagittarius_engine.extensions.logger.logger_module import LoggerExtension

from Binace_Bot.src.binance_bot_module import BinanceBotModule
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.presentation.cli.cli_parser import build_parser
from Binace_Bot.src.presentation.cli.sync_cmd import execute_sync
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_config import IConfig
import os

def _on_market_tick(event: MarketTickEvent):

    pass

def create_app(load_stream: bool = False) -> App:

    config_manager = ConfigManager()
    
    app_json = PathUtils.get_relative_path(__file__, "config", "app_config.json")
    user_json = PathUtils.get_relative_path(__file__, "config", "user_config.json")
    
    config_manager.load_json(app_json)
    config_manager.load_json(user_json)
    
    container = StdLibContainer()
    event_bus = MemoryEventBus()

container.singleton(IEventBus, event_bus)
    container.singleton(IConfig, config_manager)

event_bus.on(MarketTickEvent, _on_market_tick)
    
    app = App(container, event_bus)

app.use(LoggerExtension())

app.use(BinanceBotModule(load_stream=load_stream))
    
    return app

def main() -> None:

    if len(sys.argv) == 1:
        interactive_mode = True
        load_stream = False
    else:
        interactive_mode = False
        parser = build_parser()
        args = parser.parse_args()
        load_stream = (args.command == "stream")

    app = create_app(load_stream=load_stream)
    
    if interactive_mode:

        from Binace_Bot.src.presentation.cli.menu_service import TerminalMenuService
        menu = TerminalMenuService(app)
        app.context.hosted_services.register(menu)

app.boot()

menu.wait_for_exit()
        app.stop()
        
    else:

        app.boot()
        
        if args.command == "sync":
            execute_sync(app, args)
            app.stop()
        elif args.command == "stream":

            import time
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                app.stop()

if __name__ == "__main__":
    main()
``````

# FILE: src\presentation\cli\cli_parser.py

```python
import argparse

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Binance Trading Bot CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

sync_parser = subparsers.add_parser("sync", help="Synchronize market data from Binance")
    sync_parser.add_argument("--symbols", type=str, required=True, help="Comma separated list of symbols (e.g. BTCUSDT,ETHUSDT)")
    sync_parser.add_argument("--interval", type=str, default="1m", help="Timeframe interval (e.g. 1m, 1h, 1d)")
    sync_parser.add_argument("--days", type=int, default=30, help="Days back to sync if DB is empty")

stream_parser = subparsers.add_parser("stream", help="Start live websocket market stream")
    stream_parser.add_argument("--symbols", type=str, required=True, help="Comma-separated list of symbols (e.g. BTCUSDT)")
    stream_parser.add_argument("--interval", type=str, required=True, help="Timeframe (e.g. 1m)")

    return parser
``````

# FILE: src\presentation\cli\handlers\base_handler.py

```python
from abc import ABC, abstractmethod
from sagittarius_engine import App

class IMenuHandler(ABC):
    
    @abstractmethod
    def handle(self, app: App) -> None:
        
        pass
``````

# FILE: src\presentation\cli\handlers\stream_handler.py

```python
from sagittarius_engine import App
from Binace_Bot.src.presentation.cli.handlers.base_handler import IMenuHandler
from Binace_Bot.src.application.use_cases.manage_live_stream import (
    StartLiveStreamCommand, 
    StartLiveStreamResponse,
    StopLiveStreamCommand,
    StopLiveStreamResponse
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

class StartStreamMenuHandler(IMenuHandler):
    
    def handle(self, app: App) -> None:
        print("\n--- Start Live Market Stream ---")
        
        symbols_input = input("Enter Symbols (comma-separated, e.g. BTCUSDT): ").strip()
        if not symbols_input:
            print("❌ Symbols cannot be empty.")
            return
            
        interval_input = input("Enter Interval (e.g. 1m, 1h, 1d) [1m]: ").strip()
        if not interval_input:
            interval_input = "1m"
            
        symbols = [s.strip().upper() for s in symbols_input.split(",")]

cmd = StartLiveStreamCommand(symbols=symbols, interval=TimeFrame(interval_input))
        response: StartLiveStreamResponse = app.dispatch(StartLiveStreamCommand, cmd)
        
        if response.success:
            print(f"\n✅ {response.message} ({symbols} at {interval_input})")
            print("The system will now process MarketTickEvent in the background.")
        else:
            print(f"\n❌ {response.message}")

class StopStreamMenuHandler(IMenuHandler):
    
    def handle(self, app: App) -> None:
        print("\n--- Stop Live Market Stream ---")

cmd = StopLiveStreamCommand()
        response: StopLiveStreamResponse = app.dispatch(StopLiveStreamCommand, cmd)
        
        if response.success:
            print(f"\n✅ {response.message}")
        else:
            print(f"\n❌ {response.message}")
``````

# FILE: src\presentation\cli\handlers\sync_handler.py

```python
import logging
from sagittarius_engine import App

from Binace_Bot.src.presentation.cli.handlers.base_handler import IMenuHandler
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

class SyncMenuHandler(IMenuHandler):
    
    def handle(self, app: App) -> None:
        print("\n--- Synchronize Market Data ---")
        
        symbols_input = input("Enter Symbols (comma-separated, e.g. BTCUSDT,ETHUSDT): ").strip()
        if not symbols_input:
            print("❌ Symbols cannot be empty.")
            return
            
        interval_input = input("Enter Interval (e.g. 1m, 1h, 1d) [1m]: ").strip()
        if not interval_input:
            interval_input = "1m"
            
        days_input = input("Enter Days back to sync if empty [30]: ").strip()
        if not days_input:
            days = 30
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
                days_back_if_empty=days
            )

app.dispatch(SyncMarketDataCommand, cmd)
            print("✅ Sync Completed Successfully!")
        except Exception as e:
            print(f"❌ Error during sync: {e}")
            logging.getLogger(__name__).exception("Sync Error")
``````

# FILE: src\presentation\cli\menu_service.py

```python
import sys
from typing import Optional

from sagittarius_engine import App
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from Binace_Bot.src.presentation.cli.handlers.sync_handler import SyncMenuHandler
from Binace_Bot.src.presentation.cli.handlers.stream_handler import StartStreamMenuHandler, StopStreamMenuHandler

class TerminalMenuService(IHostedService):
    
    def __init__(self, app: App):
        self.app = app
        self.token = CancellationToken()
        self.task: Optional[ITaskHandle] = None

self.handlers = {
            "1": SyncMenuHandler(),
            "2": StartStreamMenuHandler(),
            "3": StopStreamMenuHandler(),
        }

    def start(self, context: IEngineContext) -> None:

        self.task = context.tasks.spawn(
            self._run_loop, name="TerminalMenuUI", token=self.token
        )

    def stop(self, context: IEngineContext) -> None:
        self.token.cancel()

    def wait_for_exit(self) -> None:
        
        if self.task and self.task.future:
            try:
                self.task.future.result()
            except Exception:
                pass

    def _run_loop(self, token: CancellationToken) -> None:
        while not token.is_cancelled():
            self._print_header()
            print("1. Sync Market Data (Historical)")
            print("2. Start Live Stream (Websocket)")
            print("3. Stop Live Stream")
            print("4. Exit")
            print()
            
            try:
                choice = input("Select an option: ").strip()
            except (EOFError, KeyboardInterrupt):

                print("\nGracefully shutting down...")
                break

            if not choice:
                continue

            if choice == "4":
                print("Goodbye!")
                break
                
            handler = self.handlers.get(choice)
            if handler:
                handler.handle(self.app)
            else:
                print("❌ Invalid selection. Please choose a valid option.")
                
            try:
                input("\nPress Enter to continue...")
            except (EOFError, KeyboardInterrupt):
                break

    def _print_header(self) -> None:
        print("\n" + "="*40)
        print(" 🤖 BINANCE TRADING BOT - INTERACTIVE ")
        print("="*40)
``````

# FILE: src\presentation\cli\stream_cmd.py

```python
import sys
import time
from sagittarius_engine import App

def execute_stream(app: App, args):
    
    print("Live stream started in the background. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nReceived KeyboardInterrupt. Shutting down gracefully...")
``````

# FILE: src\presentation\cli\sync_cmd.py

```python
import sys
from sagittarius_engine import App
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.application.use_cases.sync_market_data_handler import SyncMarketDataCommandHandler
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

def execute_sync(app: App, args):
    symbols_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    try:
        timeframe = TimeFrame(args.interval)
    except ValueError:
        print(f"Invalid interval: {args.interval}. Must be one of {[t.value for t in TimeFrame]}")
        sys.exit(1)
        
    command = SyncMarketDataCommand(
        symbols=symbols_list,
        interval=timeframe,
        days_back_if_empty=args.days
    )
    
    handler = app.container.resolve(SyncMarketDataCommandHandler)
    handler.execute(command)
``````

# FILE: tests\integration\infrastructure\binance\test_python_binance_client.py

```python
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.infrastructure.binance.client import PythonBinanceClient

@pytest.fixture
def client():

    with patch("Binace_Bot.src.infrastructure.binance.client.Client") as MockClient:

        mock_instance = MockClient.return_value

mock_instance.get_historical_klines.return_value = [
            [
                1672531200000, 
                "16500.0", 
                "16600.0", 
                "16400.0", 
                "16550.0", 
                "100.5", 
                1672534799999, 
                "1660000.0", 
                5000, 
                "50.0", 
                "825000.0", 
                "0"
            ]
        ]
        
        yield PythonBinanceClient(api_key="", api_secret="")

def test_get_historical_klines_parsing(client):
    start_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    
    klines = client.get_historical_klines("BTCUSDT", TimeFrame.ONE_HOUR, start_time)
    
    assert len(klines) == 1
    kline = klines[0]
    
    assert kline.symbol == "BTCUSDT"
    assert kline.interval == "1h"

assert kline.open_time == datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert kline.close_time == datetime(2023, 1, 1, 0, 59, 59, 999000, tzinfo=timezone.utc)
    
    assert kline.open_price == 16500.0
    assert kline.high_price == 16600.0
    assert kline.low_price == 16400.0
    assert kline.close_price == 16550.0
    
    assert kline.volume == 100.5
    assert kline.quote_asset_volume == 1660000.0
    assert kline.number_of_trades == 5000
    assert kline.taker_buy_base_asset_volume == 50.0
    assert kline.taker_buy_quote_asset_volume == 825000.0

def test_get_historical_klines_arguments(client):

    start_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    client.get_historical_klines("ETHUSDT", TimeFrame.ONE_MINUTE, start_time)

underlying_mock = client.client
    underlying_mock.get_historical_klines.assert_called_once_with(
        "ETHUSDT", "1m", "01 Jan 2023 12:00:00"
    )
``````

# FILE: tests\integration\infrastructure\persistence\test_sqlalchemy_repository.py

```python
import pytest
from datetime import datetime, timezone
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.infrastructure.persistence.sqlalchemy_repository import SQLAlchemyMarketDataRepository

@pytest.fixture
def repo():

    return SQLAlchemyMarketDataRepository(db_url="sqlite:///:memory:")

def create_mock_kline(symbol: str, timestamp: datetime) -> MarketData:
    return MarketData(
        symbol=symbol,
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=timestamp,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=timestamp,
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0
    )

def test_save_and_get_klines(repo):
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=timezone.utc)
    
    klines = [
        create_mock_kline("BTCUSDT", dt1),
        create_mock_kline("BTCUSDT", dt2)
    ]
    
    repo.save_klines(klines)
    
    fetched = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE)
    
    assert len(fetched) == 2
    assert fetched[0].open_time == dt1
    assert fetched[1].open_time == dt2
    assert fetched[0].close_price == 105.0

def test_upsert_behavior(repo):
    dt = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    kline1 = create_mock_kline("ETHUSDT", dt)
    
    repo.save_klines([kline1])

kline2 = create_mock_kline("ETHUSDT", dt)

    object.__setattr__(kline2, 'close_price', 200.0)
    
    repo.save_klines([kline2])
    
    fetched = repo.get_klines("ETHUSDT", TimeFrame.ONE_MINUTE)
    
    assert len(fetched) == 1
    assert fetched[0].close_price == 200.0

def test_get_latest_kline_time(repo):
    assert repo.get_latest_kline_time("BNBUSDT", TimeFrame.ONE_MINUTE) is None
    
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=timezone.utc)
    
    repo.save_klines([
        create_mock_kline("BNBUSDT", dt1),
        create_mock_kline("BNBUSDT", dt2)
    ])
    
    latest = repo.get_latest_kline_time("BNBUSDT", TimeFrame.ONE_MINUTE)
    
    assert latest == dt2

def test_get_klines_with_time_range(repo):
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=timezone.utc)
    dt3 = datetime(2023, 1, 1, 12, 2, tzinfo=timezone.utc)
    
    repo.save_klines([
        create_mock_kline("BTCUSDT", dt1),
        create_mock_kline("BTCUSDT", dt2),
        create_mock_kline("BTCUSDT", dt3)
    ])

fetched = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE, start_time=dt2, end_time=dt2)
    assert len(fetched) == 1
    assert fetched[0].open_time == dt2

fetched2 = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE, start_time=dt2)
    assert len(fetched2) == 2
    assert fetched2[0].open_time == dt2
    assert fetched2[1].open_time == dt3
``````

# FILE: tests\unit\application\use_cases\test_sync_market_data_handler.py

```python
import pytest
from unittest.mock import Mock, call
from datetime import datetime, timezone, timedelta
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.application.use_cases.sync_market_data_handler import SyncMarketDataCommandHandler
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.domain.entities.market_data import MarketData

@pytest.fixture
def mock_exchange_client():
    return Mock()

@pytest.fixture
def mock_repo():
    return Mock()

@pytest.fixture
def handler(mock_exchange_client, mock_repo):
    return SyncMarketDataCommandHandler(mock_exchange_client, mock_repo)

def test_sync_empty_db(handler, mock_exchange_client, mock_repo):

    mock_repo.get_latest_kline_time.return_value = None
    
    mock_klines = [Mock(spec=MarketData)]
    mock_exchange_client.get_historical_klines.return_value = mock_klines
    
    command = SyncMarketDataCommand(symbols=["BTCUSDT"], interval=TimeFrame.ONE_MINUTE, days_back_if_empty=5)
    handler.execute(command)

mock_repo.get_latest_kline_time.assert_called_once_with("BTCUSDT", TimeFrame.ONE_MINUTE)

call_args = mock_exchange_client.get_historical_klines.call_args[0]
    assert call_args[0] == "BTCUSDT"
    assert call_args[1] == TimeFrame.ONE_MINUTE
    assert isinstance(call_args[2], datetime)

mock_repo.save_klines.assert_called_once_with(mock_klines)

def test_sync_existing_data(handler, mock_exchange_client, mock_repo):

    latest_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    mock_repo.get_latest_kline_time.return_value = latest_time
    
    mock_klines = [Mock(spec=MarketData)]
    mock_exchange_client.get_historical_klines.return_value = mock_klines
    
    command = SyncMarketDataCommand(symbols=["ETHUSDT"], interval=TimeFrame.ONE_HOUR)
    handler.execute(command)
    
    mock_exchange_client.get_historical_klines.assert_called_once_with("ETHUSDT", TimeFrame.ONE_HOUR, latest_time)
    mock_repo.save_klines.assert_called_once_with(mock_klines)

def test_sync_no_new_data(handler, mock_exchange_client, mock_repo):
    mock_repo.get_latest_kline_time.return_value = datetime.now(timezone.utc)

    mock_exchange_client.get_historical_klines.return_value = []
    
    command = SyncMarketDataCommand(symbols=["BNBUSDT"], interval=TimeFrame.ONE_DAY)
    handler.execute(command)

mock_repo.save_klines.assert_not_called()

def test_sync_multiple_symbols(handler, mock_exchange_client, mock_repo):
    mock_repo.get_latest_kline_time.return_value = None
    mock_exchange_client.get_historical_klines.return_value = []
    
    command = SyncMarketDataCommand(symbols=["BTCUSDT", "ETHUSDT"], interval=TimeFrame.ONE_MINUTE)
    handler.execute(command)
    
    assert mock_repo.get_latest_kline_time.call_count == 2
    assert mock_exchange_client.get_historical_klines.call_count == 2

def test_sync_exchange_exception(handler, mock_exchange_client, mock_repo):

mock_repo.get_latest_kline_time.return_value = None
    mock_exchange_client.get_historical_klines.side_effect = Exception("API Error")
    
    command = SyncMarketDataCommand(symbols=["BTCUSDT"], interval=TimeFrame.ONE_MINUTE)
    
    with pytest.raises(Exception, match="API Error"):
        handler.execute(command)
    
    mock_repo.save_klines.assert_not_called()
``````

# FILE: tests\unit\infrastructure\binance\test_binance_websocket_service.py

```python
import pytest
from unittest.mock import Mock
from datetime import datetime, timezone
from Binace_Bot.src.infrastructure.binance.binance_websocket_service import BinanceWebsocketService
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent

def test_parse_kline():
    event_bus = Mock()
    config = Mock()
    service = BinanceWebsocketService(event_bus, config)
    
    mock_payload = {
        "e": "kline",
        "E": 123456789,
        "s": "BTCUSDT",
        "k": {
            "t": 123400000,
            "T": 123460000,
            "s": "BTCUSDT",
            "i": "1m",
            "f": 100,
            "L": 200,
            "o": "0.0010",
            "c": "0.0020",
            "h": "0.0025",
            "l": "0.0015",
            "v": "1000",
            "n": 100,
            "x": False,
            "q": "1.0000",
            "V": "500",
            "Q": "0.500",
            "B": "123456"
        }
    }
    
    market_data = service._parse_kline(mock_payload)
    
    assert market_data.symbol == "BTCUSDT"
    assert market_data.interval == "1m"
    assert market_data.open_price == 0.0010
    assert market_data.close_price == 0.0020
    assert market_data.high_price == 0.0025
    assert market_data.low_price == 0.0015
    assert market_data.volume == 1000.0
    assert market_data.is_closed is False

mock_payload["k"]["x"] = True
    market_data_closed = service._parse_kline(mock_payload)
    assert market_data_closed.is_closed is True
``````

# FILE: tests\unit\presentation\cli\handlers\test_stream_handler.py

```python
from unittest.mock import Mock, patch
from sagittarius_engine import App
from Binace_Bot.src.presentation.cli.handlers.stream_handler import StartStreamMenuHandler, StopStreamMenuHandler
from Binace_Bot.src.application.use_cases.manage_live_stream import (
    StartLiveStreamCommand, StartLiveStreamResponse,
    StopLiveStreamCommand, StopLiveStreamResponse
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

def test_start_stream_menu_handler_success():
    app = Mock(spec=App)

    app.dispatch.return_value = StartLiveStreamResponse(success=True, message="Success")
    
    handler = StartStreamMenuHandler()
    
    with patch("builtins.input", side_effect=["BTCUSDT, ETHUSDT", "1m"]):
        handler.handle(app)
        
    app.dispatch.assert_called_once()
    args, kwargs = app.dispatch.call_args
    assert args[0] == StartLiveStreamCommand
    cmd = args[1]
    assert cmd.symbols == ["BTCUSDT", "ETHUSDT"]
    assert cmd.interval == TimeFrame("1m")

def test_start_stream_menu_handler_empty_symbols():
    app = Mock(spec=App)
    handler = StartStreamMenuHandler()
    
    with patch("builtins.input", side_effect=["", "1m"]):
        handler.handle(app)
        
    app.dispatch.assert_not_called()

def test_stop_stream_menu_handler_success():
    app = Mock(spec=App)
    app.dispatch.return_value = StopLiveStreamResponse(success=True, message="Success")
    
    handler = StopStreamMenuHandler()
    handler.handle(app)
        
    app.dispatch.assert_called_once()
    args, kwargs = app.dispatch.call_args
    assert args[0] == StopLiveStreamCommand
``````

# FILE: tests\unit\presentation\cli\handlers\test_sync_handler.py

```python
from unittest.mock import Mock, patch
from sagittarius_engine import App
from Binace_Bot.src.presentation.cli.handlers.sync_handler import SyncMenuHandler
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

def test_sync_menu_handler_success():
    app = Mock(spec=App)
    handler = SyncMenuHandler()

with patch("builtins.input", side_effect=["BTCUSDT, ETHUSDT", "1m", "30"]):
        handler.handle(app)
        
    app.dispatch.assert_called_once()
    args, kwargs = app.dispatch.call_args
    assert args[0] == SyncMarketDataCommand
    cmd = args[1]
    assert cmd.symbols == ["BTCUSDT", "ETHUSDT"]
    assert cmd.interval == TimeFrame("1m")
    assert cmd.days_back_if_empty == 30

def test_sync_menu_handler_empty_symbols():
    app = Mock(spec=App)
    handler = SyncMenuHandler()
    
    with patch("builtins.input", side_effect=["", "1m", "30"]):
        handler.handle(app)
        
    app.dispatch.assert_not_called()

def test_sync_menu_handler_invalid_days():
    app = Mock(spec=App)
    handler = SyncMenuHandler()
    
    with patch("builtins.input", side_effect=["BTC", "1m", "abc"]):
        handler.handle(app)
        
    app.dispatch.assert_not_called()
``````

# FILE: tests\unit\presentation\cli\test_menu_service.py

```python
from unittest.mock import Mock, patch
from sagittarius_engine import App
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken
from Binace_Bot.src.presentation.cli.menu_service import TerminalMenuService

def test_menu_service_routing():
    app = Mock(spec=App)
    service = TerminalMenuService(app)
    token = CancellationToken()
    
    mock_handler = Mock()
    service.handlers["1"] = mock_handler

with patch("builtins.input", side_effect=["1", "", "4"]):
        service._run_loop(token)
        
    mock_handler.handle.assert_called_once_with(app)

def test_menu_service_graceful_shutdown_on_interrupt():
    app = Mock(spec=App)
    service = TerminalMenuService(app)
    token = CancellationToken()

with patch("builtins.input", side_effect=KeyboardInterrupt):
        service._run_loop(token)

assert True
``````

