"""`BOT-227` - the stop-to-liquidation floor is the larger of the owner's 1 % and a daily-ATR multiple.

@details `BUG-255` refuses an exit closer to its estimated liquidation than a flat share of the
exit's price (the owner's 1 %). A daily ATR may only raise that floor (`CONSTITUTION.md` P8): the
floor is `max(share, multiple x ATR)`, so no ATR, a zero one or a tiny one leaves the owner's floor
exactly as it was, and no setting of the multiple can lower it.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_grid_checks import (
    _stop,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_liq_gap_floor import (
    liq_gap_floor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.test_futures_grid_checks import (
    _inputs,
)

D = Decimal
_THRESHOLDS = FuturesGridThresholds()
#: An exit at 100 keeps 1.00 by the owner's share; an ATR of 4 keeps 0.5 x 4 = 2.00 by the ATR.
_EXIT = D(100)
_TOO_QUIET_FOR_THE_ATR = D(1)
_VOLATILE = D(4)


def test_the_defaults_are_the_owners_share_and_half_a_daily_atr() -> None:
    assert _THRESHOLDS.min_liq_gap_ratio == D("0.01")
    assert _THRESHOLDS.min_liq_gap_atr == D("0.5")


@pytest.mark.parametrize("atr", [None, D(0), D(-3)], ids=["none", "zero", "negative"])
def test_with_no_usable_atr_the_floor_is_the_owners_share(atr: Decimal | None) -> None:
    floor = liq_gap_floor(_THRESHOLDS, _EXIT, atr)

    assert floor.amount == D(1) and floor.by_atr is None and not floor.raised_by_atr


def test_a_quiet_symbols_atr_does_not_lower_the_floor() -> None:
    floor = liq_gap_floor(_THRESHOLDS, _EXIT, _TOO_QUIET_FOR_THE_ATR)

    assert floor.by_atr == D("0.5") and floor.amount == D(1)
    assert not floor.raised_by_atr


def test_a_volatile_symbols_atr_raises_the_floor() -> None:
    floor = liq_gap_floor(_THRESHOLDS, _EXIT, _VOLATILE)

    assert floor.amount == D(2) and floor.raised_by_atr


@pytest.mark.parametrize("multiple", [D(0), D("0.1"), D("0.5"), D(1)])
@pytest.mark.parametrize("atr", [None, D("0.01"), D(1), D(4), D(50)])
def test_no_atr_and_no_multiple_ever_lowers_the_owners_share(
    atr: Decimal | None, multiple: Decimal
) -> None:
    thresholds = replace(_THRESHOLDS, min_liq_gap_atr=multiple)

    assert liq_gap_floor(thresholds, _EXIT, atr).amount >= _EXIT * D("0.01")


def test_the_multiple_may_not_exceed_the_advisory_buffer() -> None:
    with pytest.raises(ValueError, match="min_liq_gap_atr"):
        FuturesGridThresholds(min_liq_gap_atr=D(2))
    with pytest.raises(ValueError, match="min_liq_gap_atr"):
        FuturesGridThresholds(min_liq_gap_atr=D(-1))


def test_the_atr_floor_is_pinned_at_its_boundary_on_both_sides() -> None:
    """A gap exactly at the raised floor (2.00 at ATR 4) passes, a cent under is refused."""
    inputs = replace(_inputs("LONG", 5, atr=_VOLATILE))
    at = _stop(inputs, PositionSide.LONG, D(98), _EXIT)
    under = _stop(inputs, PositionSide.LONG, D("98.01"), _EXIT)
    short_at = _stop(inputs, PositionSide.SHORT, D(102), _EXIT)
    short_under = _stop(inputs, PositionSide.SHORT, D("101.99"), _EXIT)

    assert [v.code for v in at] == [v.code for v in short_at]
    assert "STOP_LOSS_TOO_CLOSE_TO_LIQUIDATION" not in [v.code for v in at]
    for refused in (under, short_under):
        assert [v.code for v in refused] == ["STOP_LOSS_TOO_CLOSE_TO_LIQUIDATION"]


def test_a_gap_the_flat_share_allows_is_refused_once_the_atr_is_known() -> None:
    """The point of the change: 1.50 before liquidation passes the 1 % share, and is refused when
    a daily ATR of 4 makes the floor 2.00; without the ATR it still passes."""
    known = _inputs("LONG", 5, atr=_VOLATILE)
    unknown = _inputs("LONG", 5, atr=None)

    refused = _stop(known, PositionSide.LONG, D("98.5"), _EXIT)
    allowed = _stop(unknown, PositionSide.LONG, D("98.5"), _EXIT)

    assert [v.code for v in refused] == ["STOP_LOSS_TOO_CLOSE_TO_LIQUIDATION"]
    assert "daily ATR 4.00" in refused[0].reason and "above 1.0% of the exit" in (
        refused[0].reason
    )
    assert allowed == []


def test_a_refusal_with_no_atr_says_the_flat_floor_stood_alone_and_why() -> None:
    inputs = replace(
        _inputs("LONG", 5, atr=None),
        daily_atr_unavailable="no daily candles are stored for BTCUSDT",
    )

    (refused,) = _stop(inputs, PositionSide.LONG, D("99.5"), _EXIT)

    assert "1.0% of the exit" in refused.reason
    assert "the daily ATR is not used: no daily candles are stored for BTCUSDT" in (
        refused.reason
    )
