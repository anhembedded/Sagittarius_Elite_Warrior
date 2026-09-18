"""`StrategyModule.boot()` is what puts the live tick path on the bus.

`EPIC-025` PR 2.1c-2 moved `MarketTickEventHandler` into this module and moved
the subscription with it, out of `binance_bot_module.boot()`. Two different
claims fall out of that, and only one of them is made by the handler's own
tests:

  · *the handler delegates every tick to the session* —
    `application/event_handlers/test_market_tick_event_handler.py`, which
    constructs its own handler;
  · **that anything constructs and subscribes one at all** — this file.

The second is the claim [`CS-002`](../../../../Docs/CASE_STUDIES/
CS-002_the_subscriber_nobody_built.md) is about. `SystemErrorFeed` subscribed
to the two events `EPIC-008` had found unsubscribed, its own tests constructed
it and passed, and for two epics **nothing in the application built one**. A
test that constructs its subject can say nothing about production doing so, so
the subscription needs a test whose subject is `boot()`.

`test_a_bus_subscriber_is_constructed.py` is the mechanical half — it reads the
AST and fails on a subscribing class no other module names — and it answers
"is it named", not "does the tick arrive". This answers the second, and
`tests/integration/test_app_integration.py` then asserts that a **real** boot
of the shipping module list leaves exactly one subscriber, which is the half
neither of these two can see.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.event_handlers.market_tick_event_handler import (
    MarketTickEventHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.module import StrategyModule
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig


class _RecordingSession:
    """Stands in for `LiveStrategySession`, recording what a tick hands it.

    This module's own class in this module's own tests — the substitution
    `test_no_foreign_port_is_mocked.py` permits, and `dispatch_tick(MarketData)`
    is the whole surface `boot()` wires. The real session needs a
    `LiveStrategyFactory` and an armed config to answer anything, none of which
    this file's subject touches: what is under test is whether the bus reaches
    the object the *container* holds.
    """

    def __init__(self) -> None:
        self.ticks: list[MarketData] = []

    def dispatch_tick(self, market_data: MarketData) -> None:
        self.ticks.append(market_data)


def _market_data(symbol: str = "BTCUSDT") -> MarketData:
    dt = datetime(2023, 1, 1, tzinfo=UTC)
    return MarketData(
        symbol=symbol,
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=dt,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=dt,
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
    )


def _booted(session: _RecordingSession) -> tuple[StrategyModule, MemoryEventBus]:
    """The three things `boot()` reads, as the real context gives them to it.

    `IConfig` is bound to an empty `DictConfig` (the engine's own cheap
    real implementation, `test_no_foreign_port_is_mocked.py`'s allowed
    substitute for a Mock) since `EPIC-025E` PR 4.4f-2: `boot()` now also
    seeds the live strategy from config before subscribing the tick path,
    and an empty config answers "nothing saved" — `is_complete` is `False`,
    so `_arm_from_config()` returns before ever calling `.arm()` on
    `_RecordingSession`, which does not have one. What this file tests is
    still only the subscription, untouched by that seeding.
    """
    container = StdLibContainer()
    container.singleton(LiveStrategySession, session)
    container.singleton(IConfig, DictConfig())
    event_bus = MemoryEventBus()

    module = StrategyModule()
    module.boot(SimpleNamespace(container=container, event_bus=event_bus))
    return module, event_bus


def test_a_market_tick_on_the_bus_reaches_the_live_session() -> None:
    """The wiring itself, end to end through a real `MemoryEventBus`.

    Delete `context.event_bus.on(...)` from `boot()` and this is the test that
    fails — measured by breaking that line, not assumed (`pr-review` E12).
    """
    session = _RecordingSession()
    _, event_bus = _booted(session)

    event_bus.emit(MarketTickEvent(market_data=_market_data("ETHUSDT")))

    assert [md.symbol for md in session.ticks] == ["ETHUSDT"], (
        "a MarketTickEvent published on the bus did not reach the live "
        "strategy session — the tick path is unsubscribed, which is the app "
        "silently not trading (EPIC-022B's symptom)"
    )


def test_boot_subscribes_the_session_the_container_already_holds() -> None:
    """Not *a* session — **the** session.

    `composition/port_bindings.py` records why: a second `LiveStrategySession`
    built inside this module would give the screens an armed state the tick
    path never drives, which is the class of bug the `ExchangeSessionFactory`
    split took four pull requests to leave behind. `boot()` resolves, so the
    object that receives the tick is the one the container hands everybody
    else — asserted by identity, because two sessions would both answer
    `dispatch_tick` and only one of them is the armed one.
    """
    session = _RecordingSession()
    _, event_bus = _booted(session)
    tick = _market_data()

    event_bus.emit(MarketTickEvent(market_data=tick))

    assert session.ticks and session.ticks[0] is tick


def test_boot_subscribes_one_tick_handler_and_nothing_else() -> None:
    """One handler, under the event's own name, and no other subscription.

    Two would run the armed strategy twice per candle and try to submit two
    orders for one signal — the failure PR 2.1c-2 could cause by adding the
    subscription here without removing `binance_bot_module.boot()`'s. This bus
    is fresh and `boot()` is the only thing that has touched it, so the whole
    subscription table is readable and the count means what it says; on a real
    boot it does not, because `MarketTickFeed` legitimately subscribes to the
    same event, which is why
    `tests/integration/test_app_integration.py` filters to
    `MarketTickEventHandler` instead of counting subscribers.
    """
    _, event_bus = _booted(_RecordingSession())
    subscribed = event_bus.subscriptions()

    assert list(subscribed) == [MarketTickEvent.__name__]
    handlers = subscribed[MarketTickEvent.__name__]
    assert [type(handler.__self__) for handler in handlers] == [MarketTickEventHandler]
