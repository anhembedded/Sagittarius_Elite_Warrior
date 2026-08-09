from sagittarius_engine.base import BaseModule
from sagittarius_engine import App

from Binace_Bot.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Binace_Bot.src.infrastructure.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)
from Binace_Bot.src.infrastructure.persistence.database_manager import (
    DatabaseManager,
    DatabaseConfig,
)
from sagittarius_engine.interfaces.i_config import IConfig
import os
from Binace_Bot.src.application.ports.i_exchange_client import IExchangeClient
from Binace_Bot.src.infrastructure.binance.client import PythonBinanceClient
from Binace_Bot.src.application.use_cases.sync.sync_market_data import (
    SyncMarketDataCommand,
    SyncMarketDataCommandHandler,
)
from Binace_Bot.src.application.use_cases.sync.bulk_sync_market_data import (
    BulkSyncMarketDataCommand,
    BulkSyncMarketDataCommandHandler,
)
from Binace_Bot.src.application.use_cases.stream.start_live_stream import (
    StartLiveStreamCommand,
    StartLiveStreamCommandHandler,
)
from Binace_Bot.src.application.use_cases.stream.stop_live_stream import (
    StopLiveStreamCommand,
    StopLiveStreamCommandHandler,
)
from Binace_Bot.src.application.use_cases.backtest.run_backtest import (
    RunBacktestCommand,
    RunBacktestCommandHandler,
)
from Binace_Bot.src.application.use_cases.backtest.run_backtest.handler import (
    BacktestState,
)
from Binace_Bot.src.application.use_cases.backtest.stop_backtest import (
    StopBacktestCommand,
    StopBacktestCommandHandler,
)
from Binace_Bot.src.application.use_cases.queries.get_historical_klines import (
    GetHistoricalKlinesQuery,
    GetHistoricalKlinesQueryHandler,
)
from Binace_Bot.src.application.use_cases.queries.get_database_status import (
    GetDatabaseStatusQuery,
    GetDatabaseStatusQueryHandler,
)
from Binace_Bot.src.application.use_cases.queries.scan_all_databases import (
    ScanAllDatabasesQuery,
    ScanAllDatabasesQueryHandler,
)
from Binace_Bot.src.application.ports.i_live_stream_service import (
    ILiveStreamService,
)
from Binace_Bot.src.infrastructure.binance.binance_websocket_service import (
    BinanceWebsocketService,
)
from Binace_Bot.src.infrastructure.engine_adapters.live_stream_adapter import (
    LiveStreamEngineAdapter,
)
from Binace_Bot.src.application.event_handlers.market_data.market_tick_event_handler import (
    MarketTickEventHandler,
)
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Binace_Bot.src.domain.indicator_scripts.dev_indicator_script import (
    DevIndicatorScript,
)
from Binace_Bot.src.domain.indicator_scripts.ema_cross_script import EmaCrossScript
from Binace_Bot.src.domain.indicator_scripts.ema_ribbon_script import EmaRibbonScript
from Binace_Bot.src.domain.indicator_scripts.macd_full_script import MacdFullScript
from sagittarius_engine.interfaces.i_task_manager import ITaskManager


class BinanceBotModule(BaseModule):
    """
    Sagittarius Application Module for Binance Trading Bot.
    Registers repositories, use cases, and domain background services.
    """

    def __init__(self):
        pass

    def register(self, app: App) -> None:
        # Bind engine context dependencies for infrastructure services
        app.container.singleton(ITaskManager, app.context.tasks)

        # Register Repositories & Clients
        config: IConfig = app.container.resolve(IConfig)
        db_dir = config.get("database.dir") or os.path.join(os.getcwd(), "database")
        app.container.singleton(DatabaseConfig, DatabaseConfig(db_dir=db_dir))

        app.container.singleton(DatabaseManager, DatabaseManager)
        app.container.singleton(IMarketDataRepository, SQLAlchemyMarketDataRepository)
        app.container.singleton(IExchangeClient, PythonBinanceClient)

        # State Singletons
        app.container.singleton(BacktestState, BacktestState)

        # Bind UseCases (Command -> Handler)
        app.container.bind(SyncMarketDataCommand, SyncMarketDataCommandHandler)
        app.container.bind(BulkSyncMarketDataCommand, BulkSyncMarketDataCommandHandler)
        app.container.bind(StartLiveStreamCommand, StartLiveStreamCommandHandler)
        app.container.bind(StopLiveStreamCommand, StopLiveStreamCommandHandler)
        app.container.bind(RunBacktestCommand, RunBacktestCommandHandler)
        app.container.bind(StopBacktestCommand, StopBacktestCommandHandler)

        # Bind Queries
        app.container.bind(GetHistoricalKlinesQuery, GetHistoricalKlinesQueryHandler)
        app.container.bind(GetDatabaseStatusQuery, GetDatabaseStatusQueryHandler)
        app.container.bind(ScanAllDatabasesQuery, ScanAllDatabasesQueryHandler)

        # Indicator scripts — registered explicitly (no directory auto-scan) so
        # what's installed is greppable here. A guard test fails if a script
        # class exists under domain/indicator_scripts/ but is missing below.
        script_registry = IndicatorScriptRegistry()
        script_registry.register("ema_ribbon", EmaRibbonScript)
        script_registry.register("macd_full", MacdFullScript)
        script_registry.register("ema_cross", EmaCrossScript)
        script_registry.register("dev_showcase", DevIndicatorScript)
        app.container.singleton(IndicatorScriptRegistry, script_registry)

        # Register the WebsocketService as bound to its Interface
        app.container.singleton(ILiveStreamService, BinanceWebsocketService)
        # Register the Adapter
        app.container.bind(LiveStreamEngineAdapter, LiveStreamEngineAdapter)

    def boot(self, app: App) -> None:
        # Register the adapter as a HostedService so it receives the EngineContext and is managed
        # by the App lifecycle, delegating to the pure ILiveStreamService.
        adapter = app.container.resolve(LiveStreamEngineAdapter)
        app.context.hosted_services.register(adapter)

        # Initialize Event Handlers and subscribe to the Event Bus
        event_handler = MarketTickEventHandler(app)
        app.event_bus.on(MarketTickEvent, event_handler.handle)
