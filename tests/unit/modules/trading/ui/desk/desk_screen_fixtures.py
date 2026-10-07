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
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
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
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_chart_overlay_reader_adapter import (
    StrategyChartOverlayReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    FakeArmedStrategy,
    FakeStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing.fake_strategy_chart_overlay import (
    FakeStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
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
    #: Its New order and Emergency stop, bound as the window binds them.
    actions: DeskActions
    notifier: RecordingNotifier


@dataclass
class DeskFakes:
    """The fakes behind one venue's desk, and the dependencies built on them."""

    session: FakeTradingSession
    submission: FakeOrderSubmission
    activity: FakeAccountActivity
    arming: FakeStrategyArming
    armed: FakeArmedStrategy
    deps: DeskDependencies
    notifier: RecordingNotifier


@dataclass(frozen=True)
class DeskSetup:
    """How a test wants one desk's fakes: `ports_venue` and `strategy_venue`
    hand it another venue's ports or strategy, which the desk must refuse."""

    ports_venue: TradingVenue | None = None
    strategy_venue: TradingVenue | None = None
    account_snapshot: FakeAccountSnapshot | None = None
    order_entry_terms: FakeOrderEntryTerms | None = None
    trading_on: bool = False
    precisions: ISymbolPrecisions = NO_SYMBOL_PRECISIONS


def desk_fakes(
    world: DeskWorld, venue: TradingVenue, setup: DeskSetup | None = None
) -> DeskFakes:
    """`venue`'s desk dependencies over verified fakes, every order
    confirmed Yes."""
    setup = setup or DeskSetup()
    market = venue.market_type
    assert market is not None
    session, submission = FakeTradingSession(), FakeOrderSubmission()
    session.set_enabled(enabled=setup.trading_on)
    activity = FakeAccountActivity()
    arming, armed = FakeStrategyArming(), FakeArmedStrategy()
    threads = InlineThreadManager()
    notifier = RecordingNotifier()
    deps = DeskDependencies(
        ports=fake_venue_ports(
            setup.ports_venue or venue,
            trading_session=session,
            order_submission=submission,
            account_activity=activity,
            account_snapshot=setup.account_snapshot,
            order_entry_terms=setup.order_entry_terms,
        ),
        strategy=VenueStrategyControls(
            venue=setup.strategy_venue or venue,
            arming=StrategyArmingControlAdapter(arming),
            armed=ArmedStrategyReaderAdapter(armed),
        ),
        chart=DeskChartPorts(
            thread_manager=threads,
            market_data_sync=world.sync,
            historical_klines=world.history,
            market_stream=world.stream,
            overlay=StrategyChartOverlayReaderAdapter(FakeStrategyChartOverlay()),
            market=market,
            stream_owner=stream_owner_for(venue),
            interval="1m",
            notifier=notifier,
            scope=TRADE_ROUTE,
        ),
        thread_manager=threads,
        notifier=notifier,
        confirm=lambda _confirmation: True,
        precisions=setup.precisions,
    )
    return DeskFakes(session, submission, activity, arming, armed, deps, notifier)


#: The account tables' questions, answered Yes.
YES_TO_EVERY_TABLE_QUESTION = AccountTabConfirmations(
    cancel_one=lambda _row: True,
    cancel_all=lambda _rows: True,
    close_position=lambda _row: True,
)


def world_container(world: DeskWorld) -> Mock:
    """The container a desk's presenter resolves its bus and config from."""
    return fake_container({IEventBus: world.bus, IConfig: world.config})


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
    fakes = desk_fakes(
        world,
        venue,
        DeskSetup(
            ports_venue,
            strategy_venue,
            account_snapshot,
            order_entry_terms,
            trading_on,
            precisions,
        ),
    )
    profile = desk_profile_for(venue)
    view = DeskView(profile, confirmations=YES_TO_EVERY_TABLE_QUESTION)
    qtbot.addWidget(view)
    presenter = DeskPresenter(view, world_container(world), profile, fakes.deps)
    actions = bind_desk_actions(view, presenter)
    return Desk(
        venue,
        view,
        presenter,
        fakes.session,
        fakes.submission,
        fakes.activity,
        fakes.arming,
        fakes.armed,
        actions,
        fakes.notifier,
    )


def market_of(venue: TradingVenue) -> MarketType:
    market = venue.market_type
    assert market is not None
    return market


def open_session(world: DeskWorld, desk: Desk, qapp) -> None:
    """What an action that opens the venue's order session leaves behind
    (`EPIC-034C`): the session open, and the bus told, as
    `SessionReadiness` tells it. The desk's chart goes live on that event."""
    desk.session.set_enabled(enabled=True)
    world.bus.emit(
        TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=desk.venue)
    )
    qapp.processEvents()
