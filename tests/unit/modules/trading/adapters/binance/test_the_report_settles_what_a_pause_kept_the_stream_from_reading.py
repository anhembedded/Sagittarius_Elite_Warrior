"""`BUG-216` - an `ACCOUNT_UPDATE` settles the facts its amount carries while the position cannot be read.

@details The re-read of a changed position is refused while the exchange's pause runs and waits for
the next update (`DeferredRereads`), which can be minutes away. Until then the session believed the
symbol was still flat (or still open) and the desk never heard that a position closed. The payload
carries the signed amount at the event, which is all that those two facts need; the mark, leverage
and liquidation price of a position that is open stay with the deferred read.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.test_futures_user_data_stream import (
    _account_update,
    _stream,
)


def _paused_client() -> Mock:
    client = Mock()
    client.get_positions.side_effect = ExchangeRateLimitedError(
        timedelta(seconds=30), banned=False, raw_message="no request is sent"
    )
    return client


async def test_a_position_that_opened_during_a_pause_is_known_open_without_reading_it() -> (
    None
):
    stream, event_bus = _stream(_paused_client())
    changed: list = []
    event_bus.on(PositionChangedEvent, changed.append)

    await stream._handle_message(
        _account_update([{"s": "BTCUSDT", "pa": "0.002", "ep": "64105.35"}])
    )

    assert stream._session_state.open_position_count("BTCUSDT") == 1
    assert changed == [], "the mark and liquidation price wait for the read"


async def test_a_position_that_closed_during_a_pause_is_told_closed_without_reading_it() -> (
    None
):
    stream, event_bus = _stream(_paused_client())
    stream._session_state.reconcile_position("BTCUSDT", has_position=True)
    closed: list = []
    event_bus.on(PositionClosedEvent, closed.append)

    await stream._handle_message(
        _account_update([{"s": "BTCUSDT", "pa": "0", "ep": "0"}])
    )

    assert stream._session_state.open_position_count("BTCUSDT") == 0
    assert [e.symbol for e in closed] == ["BTCUSDT"]


async def test_a_symbol_the_report_does_not_name_is_not_settled_from_it() -> None:
    """A deferred symbol from an earlier update is re-read with this one's; this payload said
    nothing about it, so nothing is guessed for it."""
    client = _paused_client()
    stream, event_bus = _stream(client)
    stream._session_state.reconcile_position("ETHUSDT", has_position=True)
    await stream._handle_message(
        _account_update([{"s": "ETHUSDT", "pa": "0", "ep": "0"}])
    )
    stream._session_state.reconcile_position("ETHUSDT", has_position=True)
    closed: list = []
    event_bus.on(PositionClosedEvent, closed.append)

    await stream._handle_message(
        _account_update([{"s": "BTCUSDT", "pa": "0.002", "ep": "64105.35"}])
    )

    assert stream._session_state.open_position_count("ETHUSDT") == 1
    assert closed == []
