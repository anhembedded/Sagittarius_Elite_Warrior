"""Builders for the Backtest workbench's tests (`EPIC-040D`): the real workbench with the Grid
registered as its only kind, over the real query handlers and the market-data ports' verified fakes.

The pool holds each task until the test runs it, so a test can cancel, or select another bot, while a
run is still in flight (`HeldPool`). The sync is the verified fake, which stores nothing; `StoringSync`
adds what a real sync does for the journey under test."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

from PySide6.QtCore import QDateTime, QTimeZone
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_kind_backtester import (
    GridKindBacktester,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_backtest import (
    RunBacktestQuery,
    RunBacktestQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    RunGridBacktestQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench import (
    BacktestWorkbench,
    WorkbenchPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_selection import (
    WorkbenchSelection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.preview_ports import (
    HeldPool,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import panel_for
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines.handler import (
    StoredKlinesReader,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    BRACKETS,
    position_config,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.backtest.sandbox_fixtures import (
    bot,
    market,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.backtest_workbench.workbench_candles import (
    PERIOD,
    VENUE,
    StoringSync,
    swinging_candles,
)


class RoutingDispatcher(ICommandDispatcher):
    """Runs the real `RunBacktestQueryHandler` over the catalog, as the app's dispatcher resolves it
    from the module's binding; keeps what it was asked."""

    def __init__(self, handler: RunBacktestQueryHandler) -> None:
        self._handler = handler
        self.queries: list[RunBacktestQuery] = []
        #: What the dispatcher raises instead of running, when a test sets it.
        self.raises: Exception | None = None

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> Any:
        if handler_class is not RunBacktestQuery or not isinstance(
            input_dto, RunBacktestQuery
        ):
            raise LookupError(f"no handler for {handler_class.__name__}")
        self.queries.append(input_dto)
        if self.raises is not None:
            raise self.raises
        return self._handler.execute(input_dto)


class ScriptedRouting(RoutingDispatcher):
    """Answers each backtest with the next canned answer instead of running a kind (a refusal for
    missing funding, which the Grid's own tests produce on a Futures venue)."""

    def __init__(self, *answers: object) -> None:
        super().__init__(None)  # type: ignore[arg-type]
        self._answers = list(answers)

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> Any:
        assert isinstance(input_dto, RunBacktestQuery)
        self.queries.append(input_dto)
        return self._answers.pop(0)


@dataclass
class WorkbenchWorld:
    workbench: BacktestWorkbench
    pool: HeldPool
    repository: FakeMarketDataRepository
    dispatcher: RoutingDispatcher
    sync: FakeMarketDataSync
    notifier: RecordingNotifier
    timezone: DisplayTimezonePreference


def selection(
    bot_id: str = "a3f9c1", *, terms: bool = True, **changes: Any
) -> WorkbenchSelection:
    planner = market() if terms else replace(market(), terms=None)
    return WorkbenchSelection(bot(bot_id, **changes), planner)


def futures_selection(
    bot_id: str = "f00001", *, risk: bool = True
) -> WorkbenchSelection:
    """A Long Futures bot at leverage 3 with its stop loss, and its symbol's risk facts."""
    config = position_config("LONG", 3, stop_loss="percent:5")
    facts = (
        PlanRiskFacts(
            FuturesSymbolSetting("BTCUSDT", 3, MarginType.ISOLATED, Decimal(10**9)),
            BRACKETS,
        )
        if risk
        else None
    )
    return WorkbenchSelection(
        bot(bot_id, config, TradingVenue.FUTURES_TESTNET), market(), facts
    )


def build_workbench(
    *,
    stored: bool = True,
    storing_sync: bool = False,
    answers: tuple[object, ...] | None = None,
    kinds: Sequence[IBotKind] | None = None,
    editors: Callable[[str], BotKindPanel] = panel_for,
    zone: str | None = None,
) -> WorkbenchWorld:
    repository = FakeMarketDataRepository()
    if stored:
        repository.save_klines(MarketType.SPOT, swinging_candles())
    sources = FakeMarketDataSources().serving(
        FakeMarketDataSources.ports(
            VENUE.market_data_venue,
            history=StoredKlinesReader(repository),
            repository=repository,
        )
    )
    grid = GridKind(
        None,  # type: ignore[arg-type]
        GridThresholds(),
        GridKindBacktester(RunGridBacktestQueryHandler(sources)),
    )
    catalog = BotKindCatalog(list(kinds) if kinds is not None else [grid])
    dispatcher: RoutingDispatcher = (
        ScriptedRouting(*answers)
        if answers is not None
        else RoutingDispatcher(RunBacktestQueryHandler(catalog))
    )
    pool = HeldPool()
    sync = StoringSync(repository) if storing_sync else FakeMarketDataSync()
    notifier = RecordingNotifier()
    preference = DisplayTimezonePreference()
    if zone is not None:
        assert preference.set_zone(zone)
    feed = MarketDataCandleFeed(
        sync, StoredKlinesReader(repository), FakeMarketStream(), MarketType.SPOT
    )
    workbench = BacktestWorkbench(
        WorkbenchPorts(
            pool,
            lambda query: dispatcher.dispatch(RunBacktestQuery, query),
            sync,
            feed,
            notifier,
            display_timezone=preference,
            kinds=catalog.kind,
            editors=editors,
        )
    )
    view = workbench.view
    utc = QTimeZone.utc()
    view.start.setDateTime(
        QDateTime.fromSecsSinceEpoch(int(PERIOD[0].timestamp()), utc)
    )
    view.end.setDateTime(QDateTime.fromSecsSinceEpoch(int(PERIOD[1].timestamp()), utc))
    return WorkbenchWorld(
        workbench, pool, repository, dispatcher, sync, notifier, preference
    )
