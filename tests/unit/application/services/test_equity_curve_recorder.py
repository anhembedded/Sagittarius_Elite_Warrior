"""`EPIC-021M` §3/§4 — `EquityCurveRecorder`: a RAM-only accumulator with a
sample ceiling, no persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.application.services.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.domain.trading.equity_sample import EquitySample


def _sample(minute: int) -> EquitySample:
    return EquitySample(
        captured_at=datetime(2026, 9, 2, 12, minute, tzinfo=UTC),
        wallet_balance=Decimal(1000),
        unrealized_pnl=Decimal(minute),
    )


def test_starts_empty() -> None:
    recorder = EquityCurveRecorder()

    assert recorder.samples == []


def test_records_in_order() -> None:
    recorder = EquityCurveRecorder()

    recorder.record(_sample(1))
    recorder.record(_sample(2))
    recorder.record(_sample(3))

    assert recorder.samples == [_sample(1), _sample(2), _sample(3)]


def test_exceeding_the_limit_drops_the_oldest_sample() -> None:
    recorder = EquityCurveRecorder(max_samples=2)

    recorder.record(_sample(1))
    recorder.record(_sample(2))
    recorder.record(_sample(3))

    assert recorder.samples == [_sample(2), _sample(3)]


def test_samples_returns_a_snapshot_not_a_live_view() -> None:
    """Mutating what `.samples` returns must never reach back into the
    recorder's own state."""
    recorder = EquityCurveRecorder()
    recorder.record(_sample(1))

    snapshot = recorder.samples
    snapshot.append(_sample(2))

    assert recorder.samples == [_sample(1)]
