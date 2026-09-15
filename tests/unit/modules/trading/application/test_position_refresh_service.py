"""`BUG-117` — `PositionRefreshService` keeps every open position's mark
price/unrealized PnL from going stale between exchange-driven
`ACCOUNT_UPDATE` events, by re-fetching the real snapshot and republishing
it through the same `PositionChangedEvent`/`PositionClosedEvent` every
screen already listens to via `OrderFeed` — one service, not one per
screen (see the class's own docstring, and `bug-fix-rule.md` §2 for why the
first, per-screen `QTimer` version of this fix was rejected)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.position_refresh_service import (
    PositionRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.live_position import (
    LivePosition,
)


def _position(symbol: str = "ETHUSDT") -> LivePosition:
    return LivePosition(
        symbol=symbol,
        position_amt=Decimal("4.804"),
        entry_price=Decimal("2436.72"),
        mark_price=Decimal("2440.00"),
        unrealized_pnl=Decimal("15.98"),
        leverage=20,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=datetime.now(UTC),
    )


def _service(dispatcher=None, event_publisher=None, session_state=None):
    dispatcher = dispatcher or Mock()
    event_publisher = event_publisher or Mock()
    session_state = session_state or TradingSessionState()
    service = PositionRefreshService(dispatcher, event_publisher, session_state)
    return service, dispatcher, event_publisher, session_state


def test_refresh_is_a_no_op_while_trading_is_disabled():
    service, dispatcher, event_publisher, _ = _service()

    service.refresh_once()

    dispatcher.dispatch.assert_not_called()
    event_publisher.publish.assert_not_called()


def test_refresh_dispatches_get_open_positions_and_publishes_position_changed():
    session_state = TradingSessionState()
    session_state.enable(set())
    position = _position()
    dispatcher = Mock()
    dispatcher.dispatch.return_value = (position,)
    service, _, event_publisher, _ = _service(
        dispatcher=dispatcher, session_state=session_state
    )

    service.refresh_once()

    dispatcher.dispatch.assert_called_once_with(
        GetOpenPositionsQuery, GetOpenPositionsQuery()
    )
    event_publisher.publish.assert_called_once_with(
        PositionChangedEvent(position=position)
    )


def test_a_symbol_no_longer_reported_publishes_position_closed():
    """A position present in a previous refresh but absent from the fresh
    snapshot (closed since the last poll) must be reported as closed —
    the same reconciliation shape `_handle_account_update()` already uses,
    just triggered by a poll instead of a push."""
    session_state = TradingSessionState()
    session_state.enable(set())
    dispatcher = Mock()
    dispatcher.dispatch.return_value = (_position("ETHUSDT"),)
    service, _, event_publisher, _ = _service(
        dispatcher=dispatcher, session_state=session_state
    )
    service.refresh_once()
    event_publisher.publish.reset_mock()

    dispatcher.dispatch.return_value = ()
    service.refresh_once()

    event_publisher.publish.assert_called_once_with(
        PositionClosedEvent(symbol="ETHUSDT")
    )


def test_a_dispatch_failure_is_swallowed_and_does_not_publish():
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


def test_disabling_trading_stops_further_dispatches():
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
