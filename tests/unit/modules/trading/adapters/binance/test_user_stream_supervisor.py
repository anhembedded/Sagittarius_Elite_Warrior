"""`EPIC-035B` — the supervisor both user-data streams run under.

One retry loop for Spot and Futures (`code/quality.md`: fix the mechanism, not
the call site): it retries any failure with a capped, jittered exponential
backoff, publishes the stream's health, resets the backoff only after a
connection that stayed up, and never logs a secret or a signed URL.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.user_stream_supervisor import (
    DEFAULT_RECONNECT_POLICY,
    ReconnectPolicy,
    UserStreamSupervisor,
    redact_secrets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.emitter_builder import (
    venue_emitter,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_T0 = datetime(2026, 10, 8, 12, tzinfo=UTC)
_P = ReconnectPolicy(
    base_seconds=1, cap_seconds=60, jitter_fraction=0.25, stable_after_seconds=30
)


class _Clock:
    """Wall time and monotonic time, moved only by the test."""

    def __init__(self) -> None:
        self.wall = _T0
        self.mono = 1000.0

    def now(self) -> datetime:
        return self.wall

    def monotonic(self) -> float:
        return self.mono

    def advance(self, seconds: float) -> None:
        self.wall += timedelta(seconds=seconds)
        self.mono += seconds


class _Harness:
    """A supervisor over a scripted session, its events and its sleeps."""

    def __init__(self, spread: float = 0.5) -> None:
        self.clock = _Clock()
        self.bus = MemoryEventBus()
        self.events: list[UserStreamHealthEvent] = []
        self.bus.on(UserStreamHealthEvent, self.events.append)
        self.delays: list[float] = []
        self.current = True
        self.supervisor = UserStreamSupervisor(
            "TestStream",
            venue_emitter(self.bus, TradingVenue.SPOT_TESTNET),
            _P,
            now=self.clock.now,
            monotonic=self.clock.monotonic,
            spread=lambda: spread,
        )

    async def run(
        self, session: Callable[[Callable[[], None]], Awaitable[None]]
    ) -> None:
        async def record_sleep(delay: float, *_a: object, **_k: object) -> None:
            self.delays.append(delay)

        with patch("asyncio.sleep", new=record_sleep):
            await self.supervisor.run(session, lambda: self.current)

    def states(self) -> list[tuple[UserStreamState, int]]:
        return [(e.state, e.attempt) for e in self.events]


def _failing_then_stopping(
    h: _Harness, failures: int, *, lived: float = 0.0
) -> Callable[[Callable[[], None]], Awaitable[None]]:
    """The first `failures` sessions connect, live `lived` s, then fail; the
    next one stops the stream."""
    calls = 0

    async def session(connected: Callable[[], None]) -> None:
        nonlocal calls
        calls += 1
        if calls <= failures:
            connected()
            h.clock.advance(lived)
            raise ValueError("Failed to subscribe to user data stream")
        h.current = False

    return session


@pytest.mark.parametrize(
    ("attempt", "expected_raw"),
    [(0, 1), (1, 2), (2, 4), (5, 32), (6, 60), (7, 60), (50, 60)],
)
def test_the_delay_doubles_to_the_cap(attempt: int, expected_raw: float) -> None:
    """Boundary: 2^6 = 64 is the first value past the 60 s cap."""
    assert _P.delay(attempt, spread=0.5) == pytest.approx(expected_raw)


def test_the_jitter_spans_plus_and_minus_its_fraction() -> None:
    assert _P.delay(3, spread=0.0) == pytest.approx(8 * 0.75)
    assert _P.delay(3, spread=1.0) == pytest.approx(8 * 1.25)
    assert _P.delay(40, spread=1.0) == pytest.approx(60 * 1.25), "the cap is jittered"


def test_the_default_policy_is_the_documented_one() -> None:
    assert DEFAULT_RECONNECT_POLICY.base_seconds == 1
    assert DEFAULT_RECONNECT_POLICY.cap_seconds == 60
    assert DEFAULT_RECONNECT_POLICY.jitter_fraction == pytest.approx(0.2)
    assert DEFAULT_RECONNECT_POLICY.stable_after_seconds == 30


async def test_every_failure_is_retried_with_a_growing_delay() -> None:
    h = _Harness()

    await h.run(_failing_then_stopping(h, failures=4))

    assert h.delays == pytest.approx([1, 2, 4, 8])


async def test_a_session_that_stayed_up_resets_the_backoff() -> None:
    h = _Harness()

    await h.run(_failing_then_stopping(h, failures=3, lived=_P.stable_after_seconds))

    assert h.delays == pytest.approx([1, 1, 1]), "each long-lived link starts over"


async def test_a_session_that_flaps_does_not_reset_the_backoff() -> None:
    """Boundary: one second short of stable is still flapping."""
    h = _Harness()

    await h.run(
        _failing_then_stopping(h, failures=3, lived=_P.stable_after_seconds - 1)
    )

    assert h.delays == pytest.approx([1, 2, 4])


async def test_the_stream_publishes_connecting_connected_reconnecting_and_back() -> (
    None
):
    h = _Harness()

    await h.run(_failing_then_stopping(h, failures=2, lived=_P.stable_after_seconds))

    assert h.states() == [
        (UserStreamState.CONNECTING, 0),
        (UserStreamState.CONNECTED, 0),
        (UserStreamState.RECONNECTING, 1),
        (UserStreamState.CONNECTED, 0),
        (UserStreamState.RECONNECTING, 1),
    ]


async def test_the_attempt_count_keeps_growing_while_the_link_flaps() -> None:
    h = _Harness()

    await h.run(_failing_then_stopping(h, failures=3, lived=1))

    assert [e.attempt for e in h.events if e.state is UserStreamState.RECONNECTING] == [
        1,
        2,
        3,
    ]


async def test_the_outage_is_dated_from_its_first_failure_not_its_last() -> None:
    h = _Harness()
    attempts = 0

    async def session(connected: Callable[[], None]) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            connected()
            h.clock.advance(100)
            raise OSError("link dropped")
        if attempts <= 4:
            h.clock.advance(10)
            raise ValueError("cannot subscribe")
        h.current = False

    await h.run(session)

    outage = [e for e in h.events if e.state is UserStreamState.RECONNECTING]
    assert [e.attempt for e in outage] == [1, 2, 3, 4]
    assert {e.since for e in outage} == {_T0 + timedelta(seconds=100)}
    connected_at_start = h.events[1]
    assert connected_at_start.state is UserStreamState.CONNECTED
    assert connected_at_start.since == _T0


async def test_a_stream_that_never_connects_dates_its_outage_from_its_start() -> None:
    h = _Harness()
    attempts = 0

    async def session(connected: Callable[[], None]) -> None:
        nonlocal attempts
        attempts += 1
        h.clock.advance(5)
        if attempts <= 2:
            raise ValueError("no subscription ID")
        h.current = False

    await h.run(session)

    assert h.events[0].state is UserStreamState.CONNECTING
    assert {e.since for e in h.events} == {_T0}


async def test_a_session_that_returns_while_still_wanted_is_reconnected() -> None:
    """Never a hot loop: a session returning without being told to stop is a
    failure with a delay."""
    h = _Harness()
    calls = 0

    async def session(connected: Callable[[], None]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            h.current = False

    await h.run(session)

    assert calls == 2
    assert h.delays == pytest.approx([1])


async def test_a_stream_stopped_during_a_failure_does_not_reconnect() -> None:
    h = _Harness()

    async def session(connected: Callable[[], None]) -> None:
        h.current = False
        raise ValueError("raised while being stopped")

    await h.run(session)

    assert h.delays == []
    assert UserStreamState.RECONNECTING not in {e.state for e in h.events}


async def test_each_failed_attempt_is_logged_once_without_a_secret(caplog) -> None:
    h = _Harness()
    calls = 0

    async def session(connected: Callable[[], None]) -> None:
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise ValueError(
                "GET https://api.binance.com/api/v3/userDataStream?listenKey=ABCDEF1234"
                "&timestamp=1&signature=deadbeef0123 failed"
            )
        h.current = False

    with caplog.at_level(logging.INFO, logger="App.UserDataStream"):
        await h.run(session)

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 2
    text = "\n".join(r.getMessage() for r in errors)
    assert "ValueError" in text
    assert "deadbeef0123" not in text
    assert "ABCDEF1234" not in text


@pytest.mark.parametrize(
    ("raw", "hidden"),
    [
        ("...&signature=0f1e2d3c4b5a69788796a5b4c3d2e1f0 end", "0f1e2d3c4b5a69788796"),
        ("/ws/listenKey=pqrSTU123456 x", "pqrSTU123456"),
        ("X-MBX-APIKEY: AKIAEXAMPLEKEY123", "AKIAEXAMPLEKEY123"),
        ("api_key=SECRETVALUE&other=1", "SECRETVALUE"),
    ],
)
def test_a_secret_is_removed_from_an_error_text(raw: str, hidden: str) -> None:
    assert hidden not in redact_secrets(raw)


def test_a_text_without_a_secret_is_left_alone() -> None:
    assert redact_secrets("Cannot connect to host testnet.binance.vision:443") == (
        "Cannot connect to host testnet.binance.vision:443"
    )


def test_stopping_publishes_stopped() -> None:
    h = _Harness()

    h.supervisor.publish_stopped()

    assert h.states() == [(UserStreamState.STOPPED, 0)]
    assert h.events[0].venue is TradingVenue.SPOT_TESTNET
