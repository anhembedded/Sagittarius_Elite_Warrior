"""Trading's section: the user-data streams, answered from memory (`EPIC-038C`)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.trading.application.health.trading_health_contributor import (
    TradingHealthContributor,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.user_stream_recorder import (
    UserStreamRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

NOW = datetime(2026, 10, 12, 12, 0, 0, tzinfo=UTC)


def _event(
    venue: TradingVenue, state: UserStreamState, ago_s: int
) -> UserStreamHealthEvent:
    return UserStreamHealthEvent(
        state=state, since=NOW - timedelta(seconds=ago_s), venue=venue
    )


def _contributor(*events: UserStreamHealthEvent) -> TradingHealthContributor:
    recorder = UserStreamRecorder()
    bus = MemoryEventBus()
    bus.on(UserStreamHealthEvent, recorder.on_health)  # the wiring `boot()` makes
    for event in events:
        bus.emit(event)
    return TradingHealthContributor(recorder, lambda: NOW)


def test_before_any_stream_reports_the_section_says_so_not_zero() -> None:
    section = _contributor().snapshot()

    assert section["user_stream"] == {}
    assert section["stream_down_s"] is None
    assert section["skew_ms"] is None


def test_a_connected_stream_has_been_down_for_zero_seconds() -> None:
    section = _contributor(
        _event(TradingVenue.SPOT_TESTNET, UserStreamState.CONNECTED, 600)
    ).snapshot()

    assert section["user_stream"] == {
        "spot_testnet": {"state": "connected", "state_age_s": 600}
    }
    assert section["stream_down_s"] == 0


def test_the_worst_outage_is_the_headline() -> None:
    section = _contributor(
        _event(TradingVenue.SPOT_TESTNET, UserStreamState.CONNECTED, 600),
        _event(TradingVenue.FUTURES_TESTNET, UserStreamState.RECONNECTING, 45),
        _event(TradingVenue.SPOT_MAINNET, UserStreamState.CONNECTING, 12),
    ).snapshot()

    assert section["stream_down_s"] == 45


def test_the_latest_event_of_a_venue_wins() -> None:
    section = _contributor(
        _event(TradingVenue.SPOT_TESTNET, UserStreamState.RECONNECTING, 90),
        _event(TradingVenue.SPOT_TESTNET, UserStreamState.CONNECTED, 5),
    ).snapshot()

    assert section["stream_down_s"] == 0
    assert section["user_stream"]["spot_testnet"]["state"] == "connected"  # type: ignore[index]


def test_the_section_is_json_ready_and_names_no_account() -> None:
    section = _contributor(
        _event(TradingVenue.FUTURES_TESTNET, UserStreamState.CONNECTED, 3)
    ).snapshot()

    text = json.dumps(dict(section))
    assert "balance" not in text
    assert "key" not in text.lower()
