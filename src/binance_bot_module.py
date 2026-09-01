import logging
import os

logger = logging.getLogger("App.BinanceBotModule")

from Sagittarius_Elite_Warrior.src.application.event_handlers.market_data.market_tick_event_handler import (
    MarketTickEventHandler,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_config_reader import (
    IConfigReader,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_session_factory import (
    IExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_live_stream_service import (
    ILiveStreamService,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
)
from Sagittarius_Elite_Warrior.src.application.services.in_flight_sync_guard import (
    InFlightSyncGuard,
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
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_historical_tick_backtest import (
    RunHistoricalTickBacktestCommand,
    RunHistoricalTickBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest import (
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.stop_backtest import (
    StopBacktestCommand,
    StopBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.database.clear_market_data import (
    ClearMarketDataCommand,
    ClearMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.database.prune_empty_shards import (
    PruneEmptyShardsCommand,
    PruneEmptyShardsCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.database.repair_data_gap import (
    RepairDataGapCommand,
    RepairDataGapCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.audit_database_integrity import (
    AuditDatabaseIntegrityQuery,
    AuditDatabaseIntegrityQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_backtest_range_coverage import (
    GetBacktestRangeCoverageQuery,
    GetBacktestRangeCoverageQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_gaps import (
    GetDatabaseGapsQuery,
    GetDatabaseGapsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_status import (
    GetDatabaseStatusQuery,
    GetDatabaseStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines import (
    GetHistoricalKlinesQuery,
    GetHistoricalKlinesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols import (
    ListAvailableSymbolsQuery,
    ListAvailableSymbolsQueryHandler,
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
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
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
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_trend_pullback_strategy import (
    EmaTrendPullbackStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.long_term_trend_zone_strategy import (
    LongTermTrendZoneStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.multi_ema_trend_follower_strategy import (
    MultiEmaTrendFollowerStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.support_resistance_strategy import (
    SupportResistanceStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.volume_spike_flow_strategy import (
    VolumeSpikeFlowStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_endpoints import (
    resolve_market_data_venue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service import (
    BinanceWebsocketService,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.command_dispatcher_adapter import (
    EngineCommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.config_reader_adapter import (
    EngineConfigReader,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.event_publisher_adapter import (
    EngineEventPublisher,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.live_stream_adapter import (
    LiveStreamEngineAdapter,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.json_symbol_catalog_repository import (
    JsonSymbolCatalogRepository,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)
from sagittarius_engine import App
from sagittarius_engine.base import BaseModule
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.utils.path_utils import PathUtils

_DEFAULT_DB_DIR_NAME: str = "database"


class BinanceBotModule(BaseModule):
    """
    Sagittarius Application Module for Binance Trading Bot.
    Registers repositories, use cases, and domain background services.
    """

    def __init__(self) -> None:
        pass

    def register(self, app: App) -> None:
        """
        @brief Registers all components, repositories, use cases, queries,
        indicator scripts, and strategies into the application DI container.
        """
        self._register_infrastructure(app)
        self._register_state_singletons(app)
        self._register_use_cases(app)
        self._register_queries(app)
        self._register_indicator_scripts(app)
        self._register_strategies(app)

    def _register_infrastructure(self, app: App) -> None:
        """Binds engine context and infrastructure services/repositories."""
        app.container.singleton(ITaskManager, app.context.tasks)

        config: IConfig = app.container.resolve(IConfig)
        db_dir = config.get(ConfigKeys.DATABASE_DIR.value) or os.path.join(
            os.getcwd(), _DEFAULT_DB_DIR_NAME
        )
        app.container.singleton(DatabaseConfig, DatabaseConfig(db_dir=db_dir))
        app.container.singleton(DatabaseManager, DatabaseManager)
        app.container.singleton(IMarketDataRepository, SQLAlchemyMarketDataRepository)
        app.container.singleton(ISymbolCatalogRepository, JsonSymbolCatalogRepository)
        # EPIC-021A: market_data_venue is registered as its own singleton so
        # BinanceWebsocketService's constructor (which needs it for the
        # testnet flag) picks up the real configured value via auto-wiring —
        # not its own default fallback, which would silently pin every
        # install to MAINNET_PUBLIC regardless of config.
        market_data_venue = resolve_market_data_venue(config)
        app.container.singleton(MarketDataVenue, market_data_venue)
        session_factory = ExchangeSessionFactory(market_data_venue)
        app.container.singleton(IExchangeSessionFactory, session_factory)
        # Lazy — Client()'s own constructor pings the network (BUG-045), so
        # this must only run when something actually resolves IExchangeClient,
        # not unconditionally on every app boot.
        app.container.singleton(
            IExchangeClient, lambda _c: session_factory.create_market_data_client()
        )
        app.container.singleton(ILiveStreamService, BinanceWebsocketService)

        # EPIC-021B: `secrets.local.json` lives next to `user_config.json`
        # (gitignored, unlike it) — same relative-path idiom `main.py` uses
        # for the config files themselves.
        secrets_file_path = PathUtils.get_relative_path(
            __file__, "config", "secrets.local.json"
        )
        credentials_provider = EnvFirstCredentialsProvider(
            SecretsFileSource(secrets_file_path)
        )
        app.container.singleton(IExchangeCredentialsProvider, credentials_provider)

        # EPIC-008F: the Application layer talks to the engine only through
        # these three ports; the adapters are the only place naming IEventBus,
        # IConfig or IDispatcher.
        app.container.singleton(IEventPublisher, EngineEventPublisher(app.event_bus))
        app.container.singleton(IConfigReader, EngineConfigReader(config))
        app.container.singleton(
            ICommandDispatcher, EngineCommandDispatcher(app.context.dispatcher)
        )
        app.container.bind(LiveStreamEngineAdapter, LiveStreamEngineAdapter)
        # BOT-098F6D: transient — BackTestView has no container access itself,
        # so BackTestPresenter resolves this and pushes it in; never a
        # singleton, since every BackTestView construction needs its own
        # factory instance producing its own (never shared) chart widgets.
        app.container.bind(BacktestChartHostFactory, BacktestChartHostFactory)

    def _register_state_singletons(self, app: App) -> None:
        """Registers long-lived application state singletons."""
        app.container.singleton(BacktestState, BacktestState)
        # BOT-121: must be a singleton, not bind() (transient) — every
        # SyncMarketDataCommandHandler resolve needs the SAME registry so a
        # sync started from Backtest and one started from Data Management see
        # each other's in-flight (symbol, interval) keys.
        app.container.singleton(InFlightSyncGuard, InFlightSyncGuard)

    def _register_use_cases(self, app: App) -> None:
        """Binds CQRS commands to their respective use case command handlers."""
        app.container.bind(SyncMarketDataCommand, SyncMarketDataCommandHandler)
        app.container.bind(BulkSyncMarketDataCommand, BulkSyncMarketDataCommandHandler)
        app.container.bind(StartLiveStreamCommand, StartLiveStreamCommandHandler)
        app.container.bind(StopLiveStreamCommand, StopLiveStreamCommandHandler)
        app.container.bind(RunBacktestCommand, RunBacktestCommandHandler)
        app.container.bind(StopBacktestCommand, StopBacktestCommandHandler)
        app.container.bind(RunStaticBacktestCommand, RunStaticBacktestCommandHandler)
        app.container.bind(
            RunHistoricalTickBacktestCommand, RunHistoricalTickBacktestCommandHandler
        )
        app.container.bind(ClearMarketDataCommand, ClearMarketDataCommandHandler)
        app.container.bind(RepairDataGapCommand, RepairDataGapCommandHandler)
        app.container.bind(PruneEmptyShardsCommand, PruneEmptyShardsCommandHandler)

    def _register_queries(self, app: App) -> None:
        """Binds CQRS queries to their respective query handlers."""
        app.container.bind(GetHistoricalKlinesQuery, GetHistoricalKlinesQueryHandler)
        app.container.bind(GetDatabaseStatusQuery, GetDatabaseStatusQueryHandler)
        app.container.bind(GetDatabaseGapsQuery, GetDatabaseGapsQueryHandler)
        app.container.bind(
            AuditDatabaseIntegrityQuery, AuditDatabaseIntegrityQueryHandler
        )
        app.container.bind(
            GetBacktestRangeCoverageQuery, GetBacktestRangeCoverageQueryHandler
        )
        app.container.bind(ScanAllDatabasesQuery, ScanAllDatabasesQueryHandler)
        app.container.bind(ListAvailableSymbolsQuery, ListAvailableSymbolsQueryHandler)

    def _register_indicator_scripts(self, app: App) -> None:
        """Registers all domain indicator scripts into IndicatorScriptRegistry."""
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

    def _register_strategies(self, app: App) -> None:
        """Registers all domain trading strategies into StrategyRegistry."""
        strategy_registry = StrategyRegistry()
        strategy_registry.register("ema_crossover", EmaCrossoverStrategy)
        strategy_registry.register(
            "multi_ema_trend_follower", MultiEmaTrendFollowerStrategy
        )
        strategy_registry.register("support_resistance", SupportResistanceStrategy)
        strategy_registry.register(
            "ema_trend_confirm_pullback", EmaTrendPullbackStrategy
        )
        strategy_registry.register("long_term_trend_zone", LongTermTrendZoneStrategy)
        strategy_registry.register("volume_spike_flow", VolumeSpikeFlowStrategy)
        app.container.singleton(StrategyRegistry, strategy_registry)

    def boot(self, app: App) -> None:
        # Register the adapter as a HostedService so it receives the EngineContext and is managed
        # by the App lifecycle, delegating to the pure ILiveStreamService.
        adapter = app.container.resolve(LiveStreamEngineAdapter)
        app.context.hosted_services.register(adapter)

        # Initialize Event Handlers and subscribe to the Event Bus
        event_handler = MarketTickEventHandler()
        app.event_bus.on(MarketTickEvent, event_handler.handle)

    def shutdown(self, app: App) -> None:
        """Release application-owned database engines and external client connections during engine shutdown."""
        database_manager = app.container.resolve(DatabaseManager)
        database_manager.dispose_all()
        try:
            exchange_client = app.container.resolve(IExchangeClient)
            if hasattr(exchange_client, "close"):
                exchange_client.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Exchange client shutdown error: %s", exc)
