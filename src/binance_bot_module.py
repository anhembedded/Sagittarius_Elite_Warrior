import os

from Sagittarius_Elite_Warrior.src.application.event_handlers.market_data.market_tick_event_handler import (
    MarketTickEventHandler,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_live_stream_service import (
    ILiveStreamService,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_backtest import (
    RunBacktestCommand,
    RunBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_backtest.handler import (
    BacktestState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest import (
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.stop_backtest import (
    StopBacktestCommand,
    StopBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_status import (
    GetDatabaseStatusQuery,
    GetDatabaseStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines import (
    GetHistoricalKlinesQuery,
    GetHistoricalKlinesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases import (
    ScanAllDatabasesQuery,
    ScanAllDatabasesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.stream.start_live_stream import (
    StartLiveStreamCommand,
    StartLiveStreamCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.stream.stop_live_stream import (
    StopLiveStreamCommand,
    StopLiveStreamCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.bulk_sync_market_data import (
    BulkSyncMarketDataCommand,
    BulkSyncMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data import (
    SyncMarketDataCommand,
    SyncMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.dev_indicator_script import (
    DevIndicatorScript,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.ema_20_script import (
    Ema20Script,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.ema_50_script import (
    Ema50Script,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.ema_100_script import (
    Ema100Script,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.ema_200_script import (
    Ema200Script,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.ema_cross_script import (
    EmaCrossScript,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.ema_ribbon_script import (
    EmaRibbonScript,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.macd_full_script import (
    MacdFullScript,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.rsi_14_script import (
    Rsi14Script,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.multi_ema_trend_follower_strategy import (
    MultiEmaTrendFollowerStrategy,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service import (
    BinanceWebsocketService,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.client import (
    PythonBinanceClient,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.live_stream_adapter import (
    LiveStreamEngineAdapter,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)
from sagittarius_engine import App
from sagittarius_engine.base import BaseModule
from sagittarius_engine.interfaces.i_config import IConfig
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
        app.container.bind(RunStaticBacktestCommand, RunStaticBacktestCommandHandler)

        # Bind Queries
        app.container.bind(GetHistoricalKlinesQuery, GetHistoricalKlinesQueryHandler)
        app.container.bind(GetDatabaseStatusQuery, GetDatabaseStatusQueryHandler)
        app.container.bind(ScanAllDatabasesQuery, ScanAllDatabasesQueryHandler)

        # Indicator scripts — registered explicitly (no directory auto-scan) so
        # what's installed is greppable here. A guard test fails if a script
        # class exists under domain/indicator_scripts/ but is missing below.
        #
        # BOT-032 Phase 6: no indicator is hardcoded in the engine anymore —
        # rsi_14/ema_20/50/100/200/macd_full are the Dev Board's defaults,
        # replacing the old _ActiveIndicator/RSI/EMA/MACD checkboxes.
        script_registry = IndicatorScriptRegistry()
        script_registry.register("rsi_14", Rsi14Script)
        script_registry.register("ema_20", Ema20Script)
        script_registry.register("ema_50", Ema50Script)
        script_registry.register("ema_100", Ema100Script)
        script_registry.register("ema_200", Ema200Script)
        script_registry.register("macd_full", MacdFullScript)
        script_registry.register("ema_ribbon", EmaRibbonScript)
        script_registry.register("ema_cross", EmaCrossScript)
        script_registry.register("dev_showcase", DevIndicatorScript)
        app.container.singleton(IndicatorScriptRegistry, script_registry)

        # Strategies — same explicit-registration convention as indicator
        # scripts above (BOT-026).
        strategy_registry = StrategyRegistry()
        strategy_registry.register("ema_crossover", EmaCrossoverStrategy)
        strategy_registry.register(
            "multi_ema_trend_follower", MultiEmaTrendFollowerStrategy
        )
        app.container.singleton(StrategyRegistry, strategy_registry)

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
