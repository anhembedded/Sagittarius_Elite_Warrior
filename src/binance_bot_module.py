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


class BinanceBotModule(BaseModule):
    """
    Sagittarius Application Module for Binance Trading Bot.

    `EPIC-025E` PR 4.4f-1..4.4f-4 moved every binding this module used to own
    into the bounded context that actually owns it (backtesting's two
    commands, strategy's state/arm-disarm, market_data's leftover venue and
    session factory, and trading's own infrastructure/commands/queries, in
    that order — see `Tasks/epics/EPIC-025_module_theo_bounded_context/
    incomplete/EPIC-025E_phase4_support_and_dissolve_common.md` §3.16). What
    is left is the shared core engine-adapter ports (`IEventPublisher`/
    `IConfigReader`/`ICommandDispatcher`) and the indicator scripts — neither
    owned by any one module — both scheduled to move to
    `shell/composition_root.py` directly in PR 4.4f-5, after which this file
    and its one remaining call site are deleted.
    """

    def __init__(self) -> None:
        pass

    def register(self, app: App) -> None:
        """
        @brief Registers the shared engine-adapter ports and the indicator
        scripts — the only bindings left in this composition root.
        """
        self._register_infrastructure(app)
        self._register_indicator_scripts(app)

    def _register_infrastructure(self, app: App) -> None:
        """Binds engine context and the shared core engine-adapter ports."""
        app.container.singleton(ITaskManager, app.context.tasks)

        config: IConfig = app.container.resolve(IConfig)

        # EPIC-008F: the Application layer talks to the engine only through
        # these three ports; the adapters are the only place naming IEventBus,
        # IConfig or IDispatcher. `EPIC-025E` PR 4.4f-5 moves these to
        # `shell/composition_root.py` directly, since no one module owns them.
        app.container.singleton(IEventPublisher, EngineEventPublisher(app.event_bus))
        app.container.singleton(IConfigReader, EngineConfigReader(config))
        app.container.singleton(
            ICommandDispatcher, EngineCommandDispatcher(app.context.dispatcher)
        )

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

    def boot(self, app: App) -> None:
        """Nothing left to start here.

        `EPIC-025E` PR 4.4f-2 moved the live-strategy arm-from-config seeding
        to `StrategyModule.boot()`; PR 4.4f-4 moved the position-refresh
        scheduling and `ITradingClient`'s conditional bind to
        `TradingModule.boot()`. What remains in this file is registration
        only (see `register()`).
        """

    def shutdown(self, app: App) -> None:
        """Nothing left to close here.

        `EPIC-025` PR 0.4a moved the SQLite engines and the market-data
        client's disposal to `MarketDataModule.shutdown()`; `EPIC-025E` PR
        4.4f-4 moved the user-data stream's to `TradingModule.shutdown()`.
        This composition root holds no closable resource of its own.
        """
