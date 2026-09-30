"""`EPIC-028D` — `AccountSummaryRefreshService` republishes a venue's summary
when it changed, and a fill on that venue asks for a refresh off the thread
it arrived on.

@details The dispatcher and publisher are recording doubles derived from
their `core/` ports (`testing-rule.md` §2); `run_elsewhere` is a list the
test drains itself, so a test can see the refresh was *handed off*, not
performed inline on the fill's thread (`BOT-145`).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_summary_refresh_service import (
    AccountSummaryRefreshPorts,
    AccountSummaryRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_account_summary import (
    GetAccountSummaryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
    SpotAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.account_summary_changed_event import (
    AccountSummaryChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.i_domain_event import IDomainEvent

_SPOT = TradingVenue.SPOT_TESTNET
_FUTURES = TradingVenue.FUTURES_TESTNET


def _summary(free: str) -> SpotAccountSummary:
    return SpotAccountSummary(
        venue=_SPOT,
        available_balance=Decimal(free),
        equity=Decimal(1000),
        quote_asset="USDT",
        quote_free=Decimal(free),
        quote_locked=Decimal(0),
    )


class _ScriptedDispatcher(ICommandDispatcher):
    """Answers each dispatch with the next scripted reply; an exception in
    the script is raised, as a failed account read would be."""

    def __init__(self, *replies: AccountSummary | Exception | None) -> None:
        self._replies = list(replies)
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.dispatched.append(input_dto)
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class _RecordingPublisher(IEventPublisher):
    def __init__(self) -> None:
        self.published: list[IDomainEvent] = []

    def publish(self, event: IDomainEvent) -> None:
        self.published.append(event)


class _Service:
    """The service plus the doubles a test inspects."""

    def __init__(
        self, dispatcher: _ScriptedDispatcher, *, enabled: bool = True
    ) -> None:
        self.dispatcher = dispatcher
        self.publisher = _RecordingPublisher()
        self.handed_off: list[Callable[[], None]] = []
        session_state = TradingSessionState()
        if enabled:
            session_state.enable(set())
        self.service = AccountSummaryRefreshService(
            AccountSummaryRefreshPorts(
                dispatcher=dispatcher,
                event_publisher=self.publisher,
                run_elsewhere=self.handed_off.append,
            ),
            session_state,
            _SPOT,
        )


def _fill(venue: TradingVenue) -> OrderFilledEvent:
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
        venue=venue,
    )


def test_refresh_is_a_no_op_while_the_venues_trading_is_disabled() -> None:
    setup = _Service(_ScriptedDispatcher(_summary("900")), enabled=False)

    setup.service.refresh_once()

    assert setup.dispatcher.dispatched == []
    assert setup.publisher.published == []


def test_the_first_read_asks_this_venue_and_publishes_its_summary() -> None:
    setup = _Service(_ScriptedDispatcher(_summary("900")))

    setup.service.refresh_once()

    assert setup.dispatcher.dispatched == [GetAccountSummaryQuery(venue=_SPOT)]
    assert setup.publisher.published == [
        AccountSummaryChangedEvent(summary=_summary("900"))
    ]


def test_an_unchanged_summary_is_not_republished() -> None:
    setup = _Service(_ScriptedDispatcher(_summary("900"), _summary("900")))

    setup.service.refresh_once()
    setup.service.refresh_once()

    assert len(setup.dispatcher.dispatched) == 2
    assert setup.publisher.published == [
        AccountSummaryChangedEvent(summary=_summary("900"))
    ]


def test_a_changed_summary_is_republished() -> None:
    setup = _Service(_ScriptedDispatcher(_summary("900"), _summary("850")))

    setup.service.refresh_once()
    setup.service.refresh_once()

    assert setup.publisher.published == [
        AccountSummaryChangedEvent(summary=_summary("900")),
        AccountSummaryChangedEvent(summary=_summary("850")),
    ]


def test_an_unreadable_account_publishes_nothing_and_keeps_the_last_summary() -> None:
    """`None` (the reader could not build a summary) must not replace the
    last good one with nothing, and the next real read that matches it is
    still recognised as unchanged."""
    setup = _Service(_ScriptedDispatcher(_summary("900"), None, _summary("900")))

    for _ in range(3):
        setup.service.refresh_once()

    assert setup.publisher.published == [
        AccountSummaryChangedEvent(summary=_summary("900"))
    ]


def test_a_failed_read_skips_the_tick_instead_of_raising() -> None:
    setup = _Service(_ScriptedDispatcher(ConnectionError("reset"), _summary("900")))

    setup.service.refresh_once()
    setup.service.refresh_once()

    assert setup.publisher.published == [
        AccountSummaryChangedEvent(summary=_summary("900"))
    ]


def test_a_fill_on_this_venue_hands_a_refresh_off_rather_than_reading_inline() -> None:
    setup = _Service(_ScriptedDispatcher(_summary("850")))

    setup.service.on_order_filled(_fill(_SPOT))

    assert setup.dispatcher.dispatched == []
    assert len(setup.handed_off) == 1
    setup.handed_off[0]()
    assert setup.publisher.published == [
        AccountSummaryChangedEvent(summary=_summary("850"))
    ]


def test_another_venues_fill_asks_for_nothing() -> None:
    setup = _Service(_ScriptedDispatcher())

    setup.service.on_order_filled(_fill(_FUTURES))

    assert setup.handed_off == []
