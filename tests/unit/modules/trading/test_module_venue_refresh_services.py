"""`EPIC-028C` — one account refresh per enabled venue, against the real wiring
and scheduled by `TradingModule.boot()`.

@details The Engine's real `StdLibContainer`, `DictConfig` and
`MemoryEventBus`, and the same `bind_adapters()`/`bind_state()`
`TradingModule.register()` calls. `ICommandDispatcher` and `IEventPublisher`
are `core/` ports; the recording doubles below implement them and show which
query each refresh sends and for which venue, without running a handler.
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.holdings_refresh_service import (
    HoldingsRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.position_refresh_service import (
    PositionRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_account_summary import (
    GetAccountSummaryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_holdings import (
    GetHoldingsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_refresh_services import (
    build_venue_refresh_services,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.module import TradingModule
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.scheduler.scheduler import ScheduledJob, Scheduler

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET


class _RecordingDispatcher(ICommandDispatcher):
    def __init__(self) -> None:
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.dispatched.append(input_dto)
        return ()


class _RecordingPublisher(IEventPublisher):
    def __init__(self) -> None:
        self.published: list[object] = []

    def publish(self, event: object) -> None:
        self.published.append(event)


class InlineThreadManager(IThreadManager):
    """The engine's worker-pool port, running each task at once on the
    caller's thread, so a test sees its effect without waiting on a pool."""

    def __init__(self) -> None:
        self.submitted: list[Callable[..., Any]] = []

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        self.submitted.append(task)
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None


class _RecordingScheduler(Scheduler):
    """The engine's own `Scheduler`, with `add_job` recording instead of
    running: `every(...).do(fn)` goes through the real `JobBuilder`."""

    def __init__(self) -> None:
        self.jobs: list[ScheduledJob] = []

    def add_job(self, job: ScheduledJob) -> None:
        self.jobs.append(job)


def _spot_fill() -> OrderFilledEvent:
    order = Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.05"),
    )
    return OrderFilledEvent(
        order=order,
        fill_price=Decimal(64000),
        fill_quantity=Decimal("0.05"),
        venue=_SPOT,
    )


def _container(
    venues: list[TradingVenue],
) -> tuple[StdLibContainer, _RecordingDispatcher]:
    dispatcher = _RecordingDispatcher()
    container = StdLibContainer()
    container.singleton(IInstanceAccess, InstanceAccess.unguarded())
    container.singleton(
        IConfig,
        DictConfig(
            {ConfigKeys.EXCHANGE_TRADING_VENUES.value: [v.value for v in venues]}
        ),
    )
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    container.singleton(ICommandDispatcher, dispatcher)
    container.singleton(IEventPublisher, _RecordingPublisher())
    container.singleton(IThreadManager, InlineThreadManager())
    bind_adapters(container)
    bind_state(container)
    return container, dispatcher


def test_each_enabled_venue_gets_the_refresh_of_its_own_market() -> None:
    container, _ = _container([_FUTURES, _SPOT])

    services = build_venue_refresh_services(container)

    assert [(type(s), s.venue) for s in services] == [
        (PositionRefreshService, _FUTURES),
        (HoldingsRefreshService, _SPOT),
        (PositionRefreshService, TradingVenue.FUTURES_MAINNET),
        (HoldingsRefreshService, TradingVenue.SPOT_MAINNET),
    ]


def test_each_refresh_reads_only_its_own_venues_session() -> None:
    """Only Spot's trading is on: Spot's holdings are polled, and Futures'
    refresh, reading Futures' own session, stays silent."""
    container, dispatcher = _container([_FUTURES, _SPOT])
    container.resolve(VenueSessionStates).session_state(_SPOT).enable(set())

    for service in build_venue_refresh_services(container):
        service.refresh_once()

    assert dispatcher.dispatched == [GetHoldingsQuery(venue=_SPOT)]


def test_every_venue_is_refreshed_whatever_the_legacy_setting_says() -> None:
    """`EPIC-034B` — an empty list (trading "off" before the toggles left) no
    longer removes a venue's refresh."""
    container, _ = _container([])

    assert [s.venue for s in build_venue_refresh_services(container)] == [
        _FUTURES,
        _SPOT,
        TradingVenue.FUTURES_MAINNET,
        TradingVenue.SPOT_MAINNET,
    ]


def test_boot_schedules_each_venues_market_and_summary_refreshes() -> None:
    container, dispatcher = _container([_FUTURES, _SPOT])
    scheduler = _RecordingScheduler()
    container.singleton(Scheduler, scheduler)
    container.resolve(VenueSessionStates).session_state(_FUTURES).enable(set())
    container.resolve(VenueSessionStates).session_state(_SPOT).enable(set())

    TradingModule().boot(SimpleNamespace(container=container))
    for job in scheduler.jobs:
        job.fn()

    assert dispatcher.dispatched == [
        GetOpenPositionsQuery(venue=_FUTURES),
        GetHoldingsQuery(venue=_SPOT),
        GetAccountSummaryQuery(venue=_FUTURES),
        GetAccountSummaryQuery(venue=_SPOT),
    ]


def test_after_boot_a_fill_refreshes_its_own_venues_summary_on_a_worker() -> None:
    """The subscription is `TradingModule.boot()`'s, not the test's: a fill
    emitted on the container's real bus reaches Spot's summary refresh,
    which runs through `IThreadManager` (`BOT-145`), and Futures' does not."""
    container, dispatcher = _container([_FUTURES, _SPOT])
    container.singleton(Scheduler, _RecordingScheduler())
    container.resolve(VenueSessionStates).session_state(_FUTURES).enable(set())
    container.resolve(VenueSessionStates).session_state(_SPOT).enable(set())
    TradingModule().boot(SimpleNamespace(container=container))

    container.resolve(IEventBus).emit(_spot_fill())

    assert dispatcher.dispatched == [GetAccountSummaryQuery(venue=_SPOT)]
    assert len(container.resolve(IThreadManager).submitted) == 1
