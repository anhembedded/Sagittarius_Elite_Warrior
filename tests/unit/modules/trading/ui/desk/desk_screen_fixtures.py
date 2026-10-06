"""`EPIC-028K`/`028L` — one whole desk over verified fakes, shared by the desk
screen's tests.

@details Every trading and market-data port is its verified fake from
`contracts/testing`; the strategy ports are trading's own, wrapped over the
strategy module's fakes by the same adapters the app binds; the bus is the
engine's real `MemoryEventBus` behind the real feeds; the worker pool runs
inline. Two desks built on one `DeskWorld` share its bus and its market
stream, as the two routes do in the running app.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.armed_strategy_reader_adapter import (
    ArmedStrategyReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_arming_control_adapter import (
    StrategyArmingControlAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_catalog_reader_adapter import (
    StrategyCatalogReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_chart_overlay_reader_adapter import (
    StrategyChartOverlayReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_catalog_service import (
    StrategyCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    FakeArmedStrategy,
    FakeStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing.fake_strategy_chart_overlay import (
    FakeStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_strategy_controls import (
    VenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tab_confirmations import (
    AccountTabConfirmations,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_chart_ports import (
    DeskChartPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_dependencies import (
    DeskDependencies,
    stream_owner_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_presenter import (
    DeskPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view import (
    DeskView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.no_symbol_precisions import (
    NO_SYMBOL_PRECISIONS,
)
from Sagittarius_Elite_Warrior.tests.conftest import fake_container
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .desk_actions import DeskActions, bind_desk_actions
from .order_entry_fixtures import InlineThreadManager

STRATEGY_KEY = "ema_crossover"


@dataclass
class DeskWorld:
    """What both desks share in the running app: one bus, one market
    stream, one store of candles."""

    bus: MemoryEventBus = field(default_factory=MemoryEventBus)
    stream: FakeMarketStream = field(default_factory=FakeMarketStream)
    history: FakeHistoricalKlines = field(default_factory=FakeHistoricalKlines)
    sync: FakeMarketDataSync = field(default_factory=FakeMarketDataSync)
    config: DictConfig = field(
        default_factory=lambda: DictConfig(
            {"DEFAULT_SYMBOLS": ["BTCUSDT", "ETHUSDT"], "DEFAULT_SYMBOL": "BTCUSDT"}
        )
    )


@dataclass
class Desk:
    """One desk: its view, its presenter and the fakes behind its ports."""

    venue: TradingVenue
    view: DeskView
    presenter: DeskPresenter
    session: FakeTradingSession
    submission: FakeOrderSubmission
    activity: FakeAccountActivity
    arming: FakeStrategyArming
    armed: FakeArmedStrategy
    #: Its Enable live trading and Emergency stop, bound as the window binds them.
    actions: DeskActions


def build_desk(
    qtbot,
    venue: TradingVenue,
    world: DeskWorld | None = None,
    *,
    ports_venue: TradingVenue | None = None,
    strategy_venue: TradingVenue | None = None,
    account_snapshot: FakeAccountSnapshot | None = None,
    order_entry_terms: FakeOrderEntryTerms | None = None,
    trading_on: bool = False,
    precisions: ISymbolPrecisions = NO_SYMBOL_PRECISIONS,
) -> Desk:
    """`venue`'s desk, every order confirmed Yes. `ports_venue` and
    `strategy_venue` hand it another venue's ports or strategy, which the
    desk must refuse."""
    world = world or DeskWorld()
    profile = desk_profile_for(venue)
    market = venue.market_type
    assert market is not None
    session, submission = FakeTradingSession(), FakeOrderSubmission()
    session.set_enabled(enabled=trading_on)
    activity = FakeAccountActivity()
    arming, armed = FakeStrategyArming(), FakeArmedStrategy()
    registry = StrategyRegistry()
    registry.register(STRATEGY_KEY, EmaCrossoverStrategy)
    threads = InlineThreadManager()
    deps = DeskDependencies(
        ports=fake_venue_ports(
            ports_venue or venue,
            trading_session=session,
            order_submission=submission,
            account_activity=activity,
            account_snapshot=account_snapshot,
            order_entry_terms=order_entry_terms,
        ),
        strategy=VenueStrategyControls(
            venue=strategy_venue or venue,
            arming=StrategyArmingControlAdapter(arming),
            armed=ArmedStrategyReaderAdapter(armed),
        ),
        catalog=StrategyCatalogReaderAdapter(StrategyCatalogService(registry)),
        chart=DeskChartPorts(
            thread_manager=threads,
            market_data_sync=world.sync,
            historical_klines=world.history,
            market_stream=world.stream,
            overlay=StrategyChartOverlayReaderAdapter(FakeStrategyChartOverlay()),
            market=market,
            stream_owner=stream_owner_for(venue),
            interval="1m",
        ),
        thread_manager=threads,
        confirm=lambda _confirmation: True,
        precisions=precisions,
    )
    view = DeskView(
        profile,
        confirmations=AccountTabConfirmations(
            cancel_one=lambda _row: True,
            cancel_all=lambda _rows: True,
            close_position=lambda _row: True,
        ),
    )
    qtbot.addWidget(view)
    container = fake_container({IEventBus: world.bus, IConfig: world.config})
    presenter = DeskPresenter(view, container, profile, deps)
    actions = bind_desk_actions(view, presenter, venue)
    return Desk(
        venue, view, presenter, session, submission, activity, arming, armed, actions
    )


def market_of(venue: TradingVenue) -> MarketType:
    market = venue.market_type
    assert market is not None
    return market
