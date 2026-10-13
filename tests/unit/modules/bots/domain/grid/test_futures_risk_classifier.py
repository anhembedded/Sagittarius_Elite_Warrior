"""`EPIC-039F` - a running position's distance to the exchange's liquidation price.

@details The business promise: distance is measured on mark; a stale or incomplete snapshot is
UNKNOWN and never SAFE; the thresholds are the owner's numbers; a mark hovering on the warning
line does not flap."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import (
    RiskLevel,
    RiskSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_risk_classifier import (
    classify_risk,
    liquidation_distance,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)

D = Decimal
_NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)
_T = FuturesGridThresholds()  # warn 5 %, critical 2 %, re-arm x1.1, 60 s


def _snapshot(
    mark: str,
    liquidation: str | None,
    position: str = "1",
    age_s: int = 1,
) -> RiskSnapshot:
    return RiskSnapshot(
        D(position),
        D(mark),
        None if liquidation is None else D(liquidation),
        _NOW - timedelta(seconds=age_s),
    )


@pytest.mark.parametrize(
    ("mark", "liquidation", "level"),
    [
        ("100", "90", RiskLevel.SAFE),  # 10 %
        ("100", "96", RiskLevel.WARN),  # 4 %
        ("100", "98.5", RiskLevel.CRITICAL),  # 1.5 %
        ("100", "101", RiskLevel.CRITICAL),  # the mark passed it
    ],
)
def test_a_long_is_judged_on_the_mark_prices_distance(
    mark: str, liquidation: str, level: RiskLevel
) -> None:
    state = classify_risk(_snapshot(mark, liquidation), _NOW, RiskLevel.SAFE, _T)

    assert state.level is level


def test_a_short_is_judged_the_same_on_the_other_side() -> None:
    near = classify_risk(
        _snapshot("100", "104", position="-1"), _NOW, RiskLevel.SAFE, _T
    )
    passed = classify_risk(
        _snapshot("100", "99", position="-1"), _NOW, RiskLevel.SAFE, _T
    )

    assert near.level is RiskLevel.WARN
    assert passed.level is RiskLevel.CRITICAL
    assert liquidation_distance(_snapshot("100", "99", "-1")) == 0


def test_watch_reports_unknown_when_the_snapshot_is_stale() -> None:
    state = classify_risk(_snapshot("100", "50", age_s=61), _NOW, RiskLevel.SAFE, _T)

    assert state.level is RiskLevel.UNKNOWN
    assert "61" in state.reason


def test_a_position_with_no_reported_liquidation_price_is_unknown_not_safe() -> None:
    state = classify_risk(_snapshot("100", None), _NOW, RiskLevel.SAFE, _T)

    assert state.level is RiskLevel.UNKNOWN


def test_a_flat_symbol_is_safe() -> None:
    state = classify_risk(
        _snapshot("100", None, position="0"), _NOW, RiskLevel.WARN, _T
    )

    assert state.level is RiskLevel.SAFE


def test_a_warning_clears_only_past_the_rearm_band() -> None:
    inside_band = _snapshot("100", "94.8")  # 5.2 %: above warn, below warn x 1.1
    outside_band = _snapshot("100", "94")  # 6 %

    assert classify_risk(inside_band, _NOW, RiskLevel.WARN, _T).level is RiskLevel.WARN
    assert classify_risk(inside_band, _NOW, RiskLevel.SAFE, _T).level is RiskLevel.SAFE
    assert classify_risk(outside_band, _NOW, RiskLevel.WARN, _T).level is RiskLevel.SAFE


def test_the_reason_carries_the_measured_distance() -> None:
    state = classify_risk(_snapshot("100", "96"), _NOW, RiskLevel.SAFE, _T)

    assert state.distance == D("0.04")
    assert "4.00%" in state.reason
