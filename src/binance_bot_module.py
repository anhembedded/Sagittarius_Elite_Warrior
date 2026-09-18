import logging
from datetime import timedelta
from decimal import Decimal

logger = logging.getLogger("App.BinanceBotModule")

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import (
    IConfigReader,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
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
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.futures_symbol_metadata_cache import (
    InMemoryFuturesSymbolMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_historical_tick_backtest import (
    RunHistoricalTickBacktestCommand,
    RunHistoricalTickBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_static_backtest import (
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.market_data_session_factory import (
    MarketDataSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_session_factory import (
    IExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_config_store import (
    LiveStrategyConfigStore,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_factory import (
    LiveStrategyFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyCommand,
    ArmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy import (
    DisarmStrategyCommand,
    DisarmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_trend_pullback_strategy import (
    EmaTrendPullbackStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.long_term_trend_zone_strategy import (
    LongTermTrendZoneStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.multi_ema_trend_follower_strategy import (
    MultiEmaTrendFollowerStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.support_resistance_strategy import (
    SupportResistanceStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.volume_spike_flow_strategy import (
    VolumeSpikeFlowStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order import (
    CancelOrderCommand,
    CancelOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order import (
    ExecuteOrderCommand,
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.submit_order import (
    SubmitOrderCommand,
    SubmitOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.position_refresh_service import (
    PositionRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
    GetExchangeConnectionStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
    GetOpenPositionsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.disable_trading import (
    DisableTradingCommand,
    DisableTradingCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop import (
    EmergencyStopCommand,
    EmergencyStopCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.enable_trading import (
    EnableTradingCommand,
    EnableTradingCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_symbol_metadata_cache import (
    IFuturesSymbolMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimits,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_market_data_venue,
    resolve_trading_venue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.dev_indicator_script import (
    DevIndicatorScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_20_script import (
    Ema20Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_50_script import (
    Ema50Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_100_script import (
    Ema100Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_200_script import (
    Ema200Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_cross_script import (
    EmaCrossScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_ribbon_script import (
    EmaRibbonScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.macd_full_script import (
    MacdFullScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.rsi_14_script import (
    Rsi14Script,
)
from sagittarius_engine import App
from sagittarius_engine.base import BaseModule
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.runtime.scheduler.scheduler import Scheduler
from sagittarius_engine.utils.path_utils import PathUtils

_DEFAULT_DB_DIR_NAME: str = "database"

#: `BUG-117` — Binance's own UI recomputes unrealized PnL roughly every
#: second; polling `GetOpenPositionsQuery` that often for a number that
#: only needs to look alive, not tick-perfect, would spend request weight
#: for nothing. 5s keeps the Positions table honestly current without it.
#: Overridable via `ConfigKeys.TRADING_POSITION_REFRESH_INTERVAL_SECONDS`,
#: clamped to `_MIN_POSITION_REFRESH_INTERVAL_SECONDS` below.
_DEFAULT_POSITION_REFRESH_INTERVAL_SECONDS: float = 5.0

#: `BUG-117` — floor for the config override above. `futures_position_
#: information()` (`python-binance`) calls Binance's documented "Position
#: Information V3" (`GET /fapi/v3/positionRisk`), weight 5 per Binance's
#: published USDⓈ-M Futures API weight table (not re-verified against a
#: live call — egress to `*.binance.*` is policy-blocked in this sandbox,
#: same disclosure `futures_account_reader.py` already carries). Binance's
#: default IP weight budget is 2400/min; at 1 call/s this poll alone spends
#: `60 * 5 = 300` weight/min (12.5% of that budget), leaving headroom for
#: every other request this app makes. Below 1s the app would be trading
#: budget for a number that does not need sub-second freshness.
_MIN_POSITION_REFRESH_INTERVAL_SECONDS: float = 1.0


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
        # `EPIC-025` PR 0.4a: the database, the repositories, the live stream
        # and `IExchangeClient` moved to `MarketDataModule` — that context owns
        # them, and `shell/modules.py` registers it right after this module.
        # EPIC-021A: market_data_venue is registered as its own singleton so
        # BinanceWebsocketService's constructor (which needs it for the
        # testnet flag) picks up the real configured value via auto-wiring —
        # not its own default fallback, which would silently pin every
        # install to MAINNET_PUBLIC regardless of config.
        market_data_venue = resolve_market_data_venue(config)
        app.container.singleton(MarketDataVenue, market_data_venue)
        # `EPIC-025` PR 1.3c-4 — one factory per bounded context, where there
        # used to be one instance answering both. Each is its own module's
        # adapter; the SDK session behind both comes from
        # `support/binance_gateway`, still the only place allowed to construct
        # a `python-binance` `Client`.
        app.container.singleton(
            IExchangeSessionFactory, MarketDataSessionFactory(market_data_venue)
        )
        session_factory = FuturesSessionFactory()
        # EPIC-024A: ExecuteOrderCommandHandler/EnableTradingCommandHandler/
        # EmergencyStopCommandHandler depend on this port, not the concrete
        # factory, so they auto-wire to this same shared instance rather than
        # the container silently constructing each of them a throwaway one.
        app.container.singleton(ITradingSessionFactory, session_factory)

        # EPIC-021C: `FuturesMetadataProvider` takes the concrete factory, not
        # `ITradingSessionFactory` — `create_futures_metadata_client()` is
        # deliberately not on that port (see the factory's own docstring), and
        # both are `trading`'s own adapters, so there is no boundary between
        # them to put one across.
        app.container.singleton(
            IFuturesSymbolMetadataCache, InMemoryFuturesSymbolMetadataCache
        )
        app.container.singleton(
            IMarketMetadataProvider,
            lambda c: FuturesMetadataProvider(
                session_factory, c.resolve(IFuturesSymbolMetadataCache)
            ),
        )

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

        # EPIC-021D: read-only, does not require TradingVenue to be
        # "enabled" anywhere — see FuturesAccountReader's own docstring for
        # why this check works off credentials alone.
        app.container.singleton(
            ITradingAccountReader,
            FuturesAccountReader(session_factory, credentials_provider),
        )

        # EPIC-021H: read-only like ITradingAccountReader — registered
        # unconditionally (not gated on TradingVenue, unlike ITradingClient
        # just below) so EnableTradingCommandHandler stays constructible
        # regardless of trading being enabled. Nothing calls `.start()` on
        # it except that handler's own successful-enable path — the app
        # never opens this stream merely by booting.
        # `EPIC-021M` — registered here, not lazily inside the lambda below,
        # so the Trading screen's equity chart can resolve the *same*
        # instance regardless of whether the stream has started yet (both
        # sides read/write through one shared singleton).
        app.container.singleton(EquityCurveRecorder, EquityCurveRecorder())

        app.container.singleton(
            IUserDataStream,
            lambda c: FuturesUserDataStream(
                app.event_bus,
                c.resolve(ITaskManager),
                session_factory,
                credentials_provider,
                c.resolve(IMarketMetadataProvider),
                c.resolve(TradingSessionState),
                c.resolve(EquityCurveRecorder),
            ),
        )

        # EPIC-021F: unlike ITradingAccountReader (read-only, always safe),
        # ITradingClient can place/cancel a real order — registered only
        # when trading is explicitly turned on, so resolving this port
        # anywhere trading is DISABLED fails loudly (DependencyResolutionError)
        # instead of silently handing back a client nobody asked to enable.
        trading_venue = resolve_trading_venue(config)
        app.container.singleton(TradingVenue, trading_venue)
        if trading_venue is not TradingVenue.DISABLED:
            app.container.singleton(
                ITradingClient,
                lambda c: FuturesTradingClient(
                    session_factory,
                    credentials_provider,
                    c.resolve(IMarketMetadataProvider),
                    OrderSubmissionMode.VALIDATE_ONLY,
                ),
            )

        # EPIC-021G: the four trading limits, all on by default — see
        # TradingLimitPolicy's own docstring for why there is no "disable
        # this one" toggle, only these numeric thresholds.
        trading_limits = TradingLimits(
            max_orders_per_session=int(
                config.get(ConfigKeys.TRADING_MAX_ORDERS_PER_SESSION.value, 20)
            ),
            max_notional_per_order=Decimal(
                str(
                    config.get(
                        ConfigKeys.TRADING_MAX_NOTIONAL_PER_ORDER_USDT.value, 500
                    )
                )
            ),
            max_positions_per_symbol=int(
                config.get(ConfigKeys.TRADING_MAX_POSITIONS_PER_SYMBOL.value, 1)
            ),
            min_order_interval=timedelta(
                seconds=int(
                    config.get(ConfigKeys.TRADING_MIN_ORDER_INTERVAL_SECONDS.value, 60)
                )
            ),
        )
        app.container.singleton(TradingLimitPolicy, TradingLimitPolicy(trading_limits))

        # EPIC-008F: the Application layer talks to the engine only through
        # these three ports; the adapters are the only place naming IEventBus,
        # IConfig or IDispatcher.
        app.container.singleton(IEventPublisher, EngineEventPublisher(app.event_bus))
        app.container.singleton(IConfigReader, EngineConfigReader(config))
        app.container.singleton(
            ICommandDispatcher, EngineCommandDispatcher(app.context.dispatcher)
        )
        # BOT-098F6D: transient — BackTestView has no container access itself,
        # so BackTestPresenter resolves this and pushes it in; never a
        # singleton, since every BackTestView construction needs its own
        # factory instance producing its own (never shared) chart widgets.
        app.container.bind(BacktestChartHostFactory, BacktestChartHostFactory)

    def _register_state_singletons(self, app: App) -> None:
        """Registers long-lived application state singletons."""
        # EPIC-021G: one per app process — never persisted, never seeded
        # from config on boot (see the class's own docstring for why).
        app.container.singleton(TradingSessionState, TradingSessionState)
        # EPIC-022A: unlike `TradingSessionState`, this one IS seeded from
        # config at boot (`_arm_from_config`) — remembering which strategy
        # to run is not the same risk as remembering that trading was on.
        # Singleton because the tick path and the Arm/Disarm command
        # handlers must all see one instance (`EnableTradingCommand`
        # itself no longer reads this at all — `BUG-112`).
        app.container.singleton(
            LiveStrategyFactory,
            lambda c: LiveStrategyFactory(
                c.resolve(StrategyRegistry),
                c.resolve(IEventPublisher),
                c.resolve(IOrderSubmission),
                c.resolve(ITradingAccountReader),
                c.resolve(IMarketMetadataProvider),
            ),
        )
        app.container.singleton(
            LiveStrategySession,
            lambda c: LiveStrategySession(c.resolve(LiveStrategyFactory)),
        )
        # `BUG-117` — keeps every open position's mark price/unrealized PnL
        # from going stale between `ACCOUNT_UPDATE` events (a fill, a
        # funding settlement); nothing else ever refreshed it. One instance,
        # scheduled once at boot (`boot()` below) via the engine's own
        # `Scheduler`, not one per screen — it reads `TradingSessionState.
        # enabled` itself every tick, so no Enable/Disable/Emergency-Stop
        # handler needs to start or stop it.
        app.container.singleton(
            PositionRefreshService,
            lambda c: PositionRefreshService(
                c.resolve(ICommandDispatcher),
                c.resolve(IEventPublisher),
                c.resolve(TradingSessionState),
            ),
        )

    def _register_use_cases(self, app: App) -> None:
        """Binds CQRS commands to their respective use case command handlers."""
        app.container.bind(RunStaticBacktestCommand, RunStaticBacktestCommandHandler)
        app.container.bind(
            RunHistoricalTickBacktestCommand, RunHistoricalTickBacktestCommandHandler
        )
        app.container.bind(SubmitOrderCommand, SubmitOrderCommandHandler)
        app.container.bind(ArmStrategyCommand, ArmStrategyCommandHandler)
        app.container.bind(DisarmStrategyCommand, DisarmStrategyCommandHandler)
        app.container.bind(EnableTradingCommand, EnableTradingCommandHandler)
        app.container.bind(DisableTradingCommand, DisableTradingCommandHandler)
        app.container.bind(ExecuteOrderCommand, ExecuteOrderCommandHandler)
        app.container.bind(EmergencyStopCommand, EmergencyStopCommandHandler)
        app.container.bind(CancelOrderCommand, CancelOrderCommandHandler)

    def _register_queries(self, app: App) -> None:
        """Binds CQRS queries to their respective query handlers."""
        app.container.bind(GetOpenPositionsQuery, GetOpenPositionsQueryHandler)
        app.container.bind(
            GetExchangeConnectionStatusQuery, GetExchangeConnectionStatusQueryHandler
        )
        app.container.bind(PreviewOrderQuery, PreviewOrderQueryHandler)

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

        # `EPIC-022A`: which strategy runs live is no longer decided here
        # once and frozen — `LiveStrategySession` holds it, and the Trading
        # screen's strategy card re-arms it through `ArmStrategyCommand`.
        # Boot only seeds it from config, so an install that was
        # configured by file keeps working exactly as before.
        config = app.container.resolve(IConfig)
        session = app.container.resolve(LiveStrategySession)
        self._arm_from_config(config, session)

        # `BUG-117` — one recurring job, registered once, for the lifetime
        # of the process; `PositionRefreshService.refresh_once()` is a
        # no-op while trading is disabled, so nothing else needs to start
        # or stop this alongside Enable/Disable/Emergency-Stop.
        position_refresh = app.container.resolve(PositionRefreshService)
        app.container.resolve(Scheduler).every(
            seconds=self._position_refresh_interval_seconds(config)
        ).do(position_refresh.refresh_once)

    @staticmethod
    def _position_refresh_interval_seconds(config: IConfig) -> float:
        """`BUG-117` — reads `TRADING_POSITION_REFRESH_INTERVAL_SECONDS`,
        clamped to `_MIN_POSITION_REFRESH_INTERVAL_SECONDS` (see that
        constant's own comment for the Binance request-weight reasoning
        behind the floor). Logs once, at boot, if the configured value was
        raised — silently ignoring a below-floor setting would leave an
        admin who deliberately tightened it with no idea it never took
        effect."""
        configured = float(
            config.get(
                ConfigKeys.TRADING_POSITION_REFRESH_INTERVAL_SECONDS.value,
                _DEFAULT_POSITION_REFRESH_INTERVAL_SECONDS,
            )
        )
        if configured < _MIN_POSITION_REFRESH_INTERVAL_SECONDS:
            logger.warning(
                "%s=%.3f is below the %.3fs floor (Binance request-weight "
                "budget) — using %.3fs instead.",
                ConfigKeys.TRADING_POSITION_REFRESH_INTERVAL_SECONDS.value,
                configured,
                _MIN_POSITION_REFRESH_INTERVAL_SECONDS,
                _MIN_POSITION_REFRESH_INTERVAL_SECONDS,
            )
            return _MIN_POSITION_REFRESH_INTERVAL_SECONDS
        return configured

    @staticmethod
    def _arm_from_config(config: IConfig, session: LiveStrategySession) -> None:
        """Seeds the live strategy from `trading.live_*` at startup.

        @details The gate is the same three-way check `EPIC-021G` used —
        a live symbol, a live strategy AND a live interval (`BUG-085`) —
        now asked of `LiveStrategyConfig.is_complete`. An empty
        `TRADING_LIVE_STRATEGY_KEY`/`TRADING_LIVE_INTERVAL` (the shipped
        default) still means "nothing armed", and every tick is ignored
        until the user arms one from the screen. A missing interval must
        never default to a guessed one — a wrong guess is a wrong strategy.

        A bad saved config (a strategy key that no longer exists, a
        parameter a strategy stopped declaring) is logged and left
        disarmed rather than crashing the whole app boot: the user can
        pick a working one on the Trading screen, which is exactly the
        recovery path that did not exist before `EPIC-022`.
        """
        try:
            live_config = LiveStrategyConfigStore(config).load()
        except ValueError as exc:
            logger.warning(
                "The saved strategy config is invalid (%s) — starting unarmed.",
                exc,
            )
            return

        if not live_config.is_complete:
            return
        try:
            session.arm(live_config)
        except ValueError as exc:
            logger.warning(
                "Could not arm the strategy saved in config (%s) — starting disarmed.",
                exc,
            )

    def shutdown(self, app: App) -> None:
        """Release the external connections this module still owns.

        `EPIC-025` PR 0.4a: the SQLite engines and the market-data client left
        with `MarketDataModule`, which now closes them in its own `shutdown()`.
        What stays here is the user-data stream, because trading owns it — and
        it becomes `TradingModule.shutdown()` in Phase 2.
        """
        try:
            # EPIC-021H: harmless no-op if trading was never enabled this
            # session (`IUserDataStream.stop()` returns `False`, does not
            # raise) — still worth calling unconditionally so a session
            # that *did* enable trading always tears its stream down.
            app.container.resolve(IUserDataStream).stop()
        except Exception as exc:  # noqa: BLE001
            logger.debug("User data stream shutdown error: %s", exc)
