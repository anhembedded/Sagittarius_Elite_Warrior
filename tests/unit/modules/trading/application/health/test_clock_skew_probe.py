"""The host measures the clock skew on its health interval; the trading section reports it (`EPIC-038D`).

`IHealthContributor.snapshot()` may not make a network call, so the measurement is a
probe the `run` host calls before it publishes (`IHealthProbe`), and the section reads
what the probe left. The probe asks through the same `VenueReads.connection` the
`clock-skew` pre-flight check does, so there is one way to ask the exchange its time.
"""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.health.clock_skew_probe import (
    ClockSkewProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.clock_skew_recorder import (
    ClockSkewRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.trading_health_contributor import (
    TradingHealthContributor,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.user_stream_recorder import (
    UserStreamRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.preflight.preflight_world import (
    reads_over,
    status,
    venue,
)

NOW = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET


def _world(*venues: tuple[TradingVenue, int | None, ConnectionFailureKind | None]):
    recorder = ClockSkewRecorder()
    probe = ClockSkewProbe(
        reads_over(*(venue(v, status(v, skew_ms=s, failure=f)) for v, s, f in venues)),
        recorder,
    )
    section = TradingHealthContributor(UserStreamRecorder(), lambda: NOW, recorder)
    return probe, section


def test_before_the_first_measurement_the_skew_is_unknown_not_zero() -> None:
    _, section = _world((FUTURES, 120, None))

    assert section.snapshot()["skew_ms"] is None


def test_a_measured_skew_reaches_the_section_with_its_sign() -> None:
    probe, section = _world((FUTURES, -120, None))

    probe.measure()

    assert section.snapshot()["skew_ms"] == -120


def test_the_venue_furthest_from_the_exchanges_clock_is_the_one_reported() -> None:
    probe, section = _world((FUTURES, 300, None), (SPOT, -700, None))

    probe.measure()

    assert section.snapshot()["skew_ms"] == -700


def test_an_exchange_that_does_not_answer_leaves_the_skew_unknown_not_stale() -> None:
    recorder = ClockSkewRecorder()
    recorder.record("futures_testnet", 90)
    probe = ClockSkewProbe(
        reads_over(
            venue(
                FUTURES,
                status(FUTURES, skew_ms=None, failure=ConnectionFailureKind.NETWORK),
            )
        ),
        recorder,
    )

    probe.measure()

    assert recorder.worst_ms() is None
