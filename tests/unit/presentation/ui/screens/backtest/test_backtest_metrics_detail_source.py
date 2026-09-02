"""`BacktestMetricsDetailSource` — pure logic, no `QApplication` required.

Mirrors `test_backtest_time_range_source.py`'s shape: a screen ViewModel
stand-in with just the members this adapter reads, so the whole suite runs
with `QApplication.instance()` staying `None`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.MetricsDetailPanel.performance_metrics_view import (
    StatCardData,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_modals.backtest_metrics_detail_source import (
    BacktestMetricsDetailSource,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.extended_metrics_snapshot import (
    ExtendedMetricsSnapshot,
)

_NEUTRAL = Tone.NEUTRAL

_SNAPSHOT = ExtendedMetricsSnapshot(
    cards=(StatCardData("Gross Profit", "100.00", _NEUTRAL, "USD", "", _NEUTRAL),),
    gross_profit=1148.19,
    gross_loss=-9341.72,
    profit_factor=0.123,
    total_closed_trades=891,
    fee_rate_percent=0.1,
)


class _FakeViewModel:
    """Just the two members `BacktestMetricsDetailSource` reads from a screen
    ViewModel — a real `BackTestViewModel` is a `QObject` and needs a
    `QApplication` to construct, which this test suite deliberately avoids.
    """

    def __init__(
        self,
        snapshot: ExtendedMetricsSnapshot | None = None,
        selected_timeframe: str = "1m",
    ) -> None:
        self._snapshot = snapshot
        self.selectedTimeframe = selected_timeframe

    def extended_metrics_snapshot(self) -> ExtendedMetricsSnapshot | None:
        return self._snapshot


def test_get_cards_reads_the_retained_snapshots_cards() -> None:
    source = BacktestMetricsDetailSource(_FakeViewModel(_SNAPSHOT))

    assert list(source.get_cards()) == list(_SNAPSHOT.cards)


def test_get_gross_profit_and_loss_read_the_snapshot() -> None:
    source = BacktestMetricsDetailSource(_FakeViewModel(_SNAPSHOT))

    assert source.get_gross_profit() == 1148.19
    assert source.get_gross_loss() == -9341.72


def test_get_profit_factor_and_total_closed_trades_read_the_snapshot() -> None:
    source = BacktestMetricsDetailSource(_FakeViewModel(_SNAPSHOT))

    assert source.get_profit_factor() == 0.123
    assert source.get_total_closed_trades() == 891


def test_get_fee_rate_percent_reads_the_snapshot() -> None:
    source = BacktestMetricsDetailSource(_FakeViewModel(_SNAPSHOT))

    assert source.get_fee_rate_percent() == 0.1


def test_no_snapshot_yet_falls_back_to_empty_zero_values_not_a_crash() -> None:
    """`None` means "no successful run yet" (or the last one failed/returned
    no data) — same convention `_extended_stat_cards`'s empty-list default
    already uses, translated to this adapter's shape."""
    source = BacktestMetricsDetailSource(_FakeViewModel(None))

    assert list(source.get_cards()) == []
    assert source.get_gross_profit() == 0.0
    assert source.get_gross_loss() == 0.0
    assert source.get_profit_factor() == 0.0
    assert source.get_total_closed_trades() == 0
    assert source.get_fee_rate_percent() == 0.0


def test_get_timeframe_seconds_reads_the_current_selected_timeframe_live() -> None:
    """Live, not retained in the snapshot — the same
    `BacktestTimeRangeSource.get_timeframe_seconds` pattern, and it must
    reflect whatever the toolbar shows *now*, not what the last run used."""
    source = BacktestMetricsDetailSource(
        _FakeViewModel(_SNAPSHOT, selected_timeframe="1h")
    )

    assert source.get_timeframe_seconds() == 3600


def test_get_timeframe_seconds_falls_back_for_an_unknown_code() -> None:
    source = BacktestMetricsDetailSource(
        _FakeViewModel(_SNAPSHOT, selected_timeframe="not-a-code")
    )

    assert source.get_timeframe_seconds() == 60
