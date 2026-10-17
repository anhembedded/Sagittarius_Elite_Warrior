"""`EPIC-042C` - the stream status is what the stream's health events last said, per venue."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.user_stream_status import (
    UserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

SPOT = TradingVenue.SPOT_TESTNET
AT = datetime(2026, 10, 17, 12, tzinfo=UTC)


def _said(
    status: UserStreamStatus, state: UserStreamState, venue: TradingVenue = SPOT
) -> None:
    status.record(UserStreamHealthEvent(state=state, since=AT, venue=venue))


def test_a_stream_that_never_reported_is_not_connected() -> None:
    assert UserStreamStatus().is_connected(SPOT) is False


def test_connected_is_connected_until_it_says_anything_else() -> None:
    status = UserStreamStatus()
    _said(status, UserStreamState.CONNECTED)
    assert status.is_connected(SPOT) is True

    _said(status, UserStreamState.RECONNECTING)
    assert status.is_connected(SPOT) is False


@pytest.mark.parametrize(
    "state",
    [s for s in UserStreamState if s is not UserStreamState.CONNECTED],
)
def test_every_state_but_connected_is_not_connected(state: UserStreamState) -> None:
    status = UserStreamStatus()
    _said(status, UserStreamState.CONNECTED)

    _said(status, state)

    assert status.is_connected(SPOT) is False


def test_a_venue_is_judged_by_its_own_stream() -> None:
    status = UserStreamStatus()
    _said(status, UserStreamState.CONNECTED, TradingVenue.FUTURES_TESTNET)

    assert status.is_connected(SPOT) is False
    assert status.is_connected(TradingVenue.FUTURES_TESTNET) is True
