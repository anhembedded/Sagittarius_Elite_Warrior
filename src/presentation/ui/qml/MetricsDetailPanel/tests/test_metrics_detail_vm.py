"""No-GUI tests for MetricsDetailVM."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.MetricsDetailPanel.metrics_detail_vm import (
    MetricsDetailVM,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.performance_metrics_view import (
    StatCardData,
)

_NEUTRAL = Tone.NEUTRAL

_MOCKUP_CARDS = (
    StatCardData("Gross Profit", "1,148.19", _NEUTRAL, "USD", "", _NEUTRAL),
    StatCardData("Gross Loss", "-9,341.72", _NEUTRAL, "USD", "", _NEUTRAL),
    StatCardData("Avg Trade", "-9.20", Tone.NEGATIVE, "USD", "", _NEUTRAL),
    StatCardData("Total Closed Trades", "891", _NEUTRAL, "lệnh", "", _NEUTRAL),
    StatCardData("Avg Winning Trade", "12.48", Tone.POSITIVE, "USD", "", _NEUTRAL),
    StatCardData("Avg Losing Trade", "-11.69", Tone.NEGATIVE, "USD", "", _NEUTRAL),
    StatCardData("Largest Winning Trade", "124.48", Tone.POSITIVE, "USD", "", _NEUTRAL),
    StatCardData("Largest Losing Trade", "-40.12", Tone.NEGATIVE, "USD", "", _NEUTRAL),
    StatCardData("Sharpe Ratio", "-63.24", _NEUTRAL, "", "", _NEUTRAL),
    StatCardData("Sortino Ratio", "-84.59", _NEUTRAL, "", "", _NEUTRAL),
    StatCardData("Calmar Ratio", "-1.22", _NEUTRAL, "", "", _NEUTRAL),
    StatCardData("Max Drawdown Duration", "48368", _NEUTRAL, "bars", "", _NEUTRAL),
    StatCardData("Max Consecutive Wins", "4", Tone.POSITIVE, "lệnh", "", _NEUTRAL),
    StatCardData("Max Consecutive Losses", "46", _NEUTRAL, "lệnh", "", _NEUTRAL),
    StatCardData("Total Fees Paid", "500.00", _NEUTRAL, "USD", "", _NEUTRAL),
)


def _vm(
    cards=_MOCKUP_CARDS,
    *,
    gross_profit: float = 1148.19,
    gross_loss: float = -9341.72,
    profit_factor: float = 0.123,
    total_closed_trades: int = 891,
    fee_rate_percent: float = 0.1,
    timeframe_seconds: int = 60,
) -> MetricsDetailVM:
    vm = MetricsDetailVM(
        get_cards=lambda: cards,
        get_gross_profit=lambda: gross_profit,
        get_gross_loss=lambda: gross_loss,
        get_profit_factor=lambda: profit_factor,
        get_total_closed_trades=lambda: total_closed_trades,
        get_fee_rate_percent=lambda: fee_rate_percent,
        get_timeframe_seconds=lambda: timeframe_seconds,
    )
    vm.refresh()
    return vm


def _group(vm, label):
    return next(g for g in vm.groups if g["label"] == label)


def _row(vm, title):
    for group in vm.groups:
        for row in group["rows"]:
            if row["title"] == title.upper():
                return row
    raise AssertionError(f"no row titled {title!r}")


def test_cards_are_split_into_the_mockups_four_groups():
    vm = _vm()

    labels = [g["label"] for g in vm.groups]
    assert labels == [
        "LÃI & LỖ",
        "TRUNG BÌNH MỖI LỆNH",
        "RỦI RO",
        "CHUỖI LIÊN TIẾP",
        "KHÁC",
    ]


def test_a_card_the_mockup_does_not_group_falls_into_khac_not_lost():
    vm = _vm()

    other = _group(vm, "KHÁC")
    assert [row["title"] for row in other["rows"]] == ["TOTAL FEES PAID"]


def test_negative_sharpe_gets_the_very_poor_verdict_on_value_and_badge():
    vm = _vm()

    row = _row(vm, "Sharpe Ratio")
    assert row["tone"] == "NEGATIVE"
    assert row["badgeText"] == "Rất kém"
    assert row["badgeTone"] == "NEGATIVE"


def test_negative_calmar_gets_the_am_verdict():
    vm = _vm()

    row = _row(vm, "Calmar Ratio")
    assert row["badgeText"] == "Âm"


def test_positive_ratio_gets_a_non_negative_verdict():
    vm = _vm(cards=(StatCardData("Sharpe Ratio", "1.5", _NEUTRAL, "", "", _NEUTRAL),))

    row = _row(vm, "Sharpe Ratio")
    assert row["badgeText"] == "Tốt"
    assert row["tone"] == "POSITIVE"


def test_consecutive_losses_above_threshold_warns():
    vm = _vm()

    row = _row(vm, "Max Consecutive Losses")
    assert row["badgeText"] == "Cảnh báo"


def test_consecutive_losses_below_threshold_has_no_badge():
    vm = _vm(
        cards=(
            StatCardData("Max Consecutive Losses", "3", _NEUTRAL, "lệnh", "", _NEUTRAL),
        )
    )

    row = _row(vm, "Max Consecutive Losses")
    assert row["badgeText"] == ""


def test_max_drawdown_duration_converts_bars_to_days_using_the_real_timeframe():
    vm = _vm(timeframe_seconds=60)  # 1-minute bars

    row = _row(vm, "Max Drawdown Duration")
    assert row["infoBadge"] == "≈ 34 ngày"


def test_gross_profit_and_loss_bar_matches_the_mockup():
    vm = _vm()

    assert vm.grossProfitText == "+1,148.19"
    assert vm.grossLossText == "-9,341.72"
    # 9341.72 / 1148.19 = 8.1361...; the mockup image reads "8.13" but that
    # is 2-decimal *truncation* rather than the round-half-up this test
    # computes independently — off by the last digit, not a logic bug.
    assert "8.14 USD lỗ" in vm.barCaption
    assert "0.123" in vm.barCaption


def test_gross_loss_stored_negative_is_not_zeroed_out():
    """Regression: an earlier version used `max(value, 0.0)`, which
    silently zeroed `BacktestMetrics.gross_loss` (stored `<= 0`) instead of
    taking its magnitude."""
    vm = _vm(gross_loss=-9341.72)

    assert vm.grossLossText == "-9,341.72"
    assert vm.grossProfitShare < 0.2  # profit is a small share of the total


def test_footer_text_matches_the_mockup():
    vm = _vm()

    assert vm.footerText == "Tính trên 891 lệnh đã đóng · phí 0.1% mỗi lệnh"


def test_request_copy_and_close_emit_their_signals():
    vm = _vm()
    copies: list[None] = []
    closes: list[None] = []
    vm.copyRequested.connect(lambda: copies.append(None))
    vm.closeRequested.connect(lambda: closes.append(None))

    vm.requestCopy()
    vm.requestClose()

    assert copies == [None]
    assert closes == [None]
