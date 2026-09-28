"""`EPIC-027O` — `HoldingsRefreshService` keeps the Holdings table from
going stale, mirroring `PositionRefreshService`'s own test suite (see that
service's docstring for the shared reasoning)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.holdings_refresh_service import (
    HoldingsRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_holdings import (
    GetHoldingsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.holdings_changed_event import (
    HoldingsChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)

_HOLDING = SpotHolding(
    asset="BTC",
    free=Decimal("0.5"),
    locked=Decimal(0),
    dust_threshold=Decimal("0.0001"),
)


def _service(dispatcher=None, event_publisher=None, session_state=None):
    dispatcher = dispatcher or Mock()
    event_publisher = event_publisher or Mock()
    session_state = session_state or TradingSessionState()
    service = HoldingsRefreshService(dispatcher, event_publisher, session_state)
    return service, dispatcher, event_publisher, session_state


def test_refresh_is_a_no_op_while_trading_is_disabled() -> None:
    service, dispatcher, event_publisher, _ = _service()

    service.refresh_once()

    dispatcher.dispatch.assert_not_called()
    event_publisher.publish.assert_not_called()


def test_refresh_dispatches_get_holdings_and_publishes_the_whole_set() -> None:
    session_state = TradingSessionState()
    session_state.enable(set())
    dispatcher = Mock()
    dispatcher.dispatch.return_value = (_HOLDING,)
    service, _, event_publisher, _ = _service(
        dispatcher=dispatcher, session_state=session_state
    )

    service.refresh_once()

    dispatcher.dispatch.assert_called_once_with(GetHoldingsQuery, GetHoldingsQuery())
    event_publisher.publish.assert_called_once_with(
        HoldingsChangedEvent(holdings=(_HOLDING,))
    )


def test_an_empty_holdings_set_still_publishes() -> None:
    """Unlike positions, a holdings poll that comes back empty (everything
    sold) must still publish — there is no separate 'closed' event, so the
    empty whole-set publish is what clears a stale table row."""
    session_state = TradingSessionState()
    session_state.enable(set())
    dispatcher = Mock()
    dispatcher.dispatch.return_value = ()
    service, _, event_publisher, _ = _service(
        dispatcher=dispatcher, session_state=session_state
    )

    service.refresh_once()

    event_publisher.publish.assert_called_once_with(HoldingsChangedEvent(holdings=()))


def test_a_dispatch_failure_is_swallowed_and_does_not_publish() -> None:
    """A transient network hiccup must not raise out of a scheduler tick —
    the next tick simply tries again."""
    session_state = TradingSessionState()
    session_state.enable(set())
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = RuntimeError("boom")
    service, _, event_publisher, _ = _service(
        dispatcher=dispatcher, session_state=session_state
    )

    service.refresh_once()  # must not raise

    event_publisher.publish.assert_not_called()


def test_disabling_trading_stops_further_dispatches() -> None:
    session_state = TradingSessionState()
    session_state.enable(set())
    dispatcher = Mock()
    dispatcher.dispatch.return_value = ()
    service, _, _, _ = _service(dispatcher=dispatcher, session_state=session_state)
    service.refresh_once()
    dispatcher.dispatch.reset_mock()

    session_state.disable()
    service.refresh_once()

    dispatcher.dispatch.assert_not_called()
