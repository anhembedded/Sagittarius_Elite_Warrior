"""`DataManagementKlineInspectorSource` — pure logic, no `QApplication`
required.

Mirrors `test_backtest_time_range_source.py`'s shape: a screen ViewModel
stand-in with just the members this adapter reads, so the whole suite runs
with `QApplication.instance()` staying `None`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_widgets.kline_inspector_source import (
    DataManagementKlineInspectorSource,
)


class _FakeViewModel:
    """Just the three members `DataManagementKlineInspectorSource` reads
    from a screen ViewModel — a real `DataManagementViewModel` is a
    `QObject` and needs a `QApplication` to construct, which this test
    suite deliberately avoids."""

    def __init__(
        self,
        klines: list[object] | None = None,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
    ) -> None:
        self.kline_inspector_klines = list(klines) if klines is not None else []
        self.klineInspectorSymbol = symbol
        self.klineInspectorInterval = interval


def test_get_klines_reads_the_view_models_raw_candle_list() -> None:
    candles = [object(), object(), object()]
    source = DataManagementKlineInspectorSource(_FakeViewModel(klines=candles))

    assert list(source.get_klines()) == candles


def test_get_klines_is_empty_before_any_inspection_has_run() -> None:
    source = DataManagementKlineInspectorSource(_FakeViewModel())

    assert list(source.get_klines()) == []


def test_get_symbol_reads_the_currently_inspected_symbol() -> None:
    source = DataManagementKlineInspectorSource(_FakeViewModel(symbol="ETHUSDT"))

    assert source.get_symbol() == "ETHUSDT"


def test_get_interval_reads_the_currently_inspected_interval() -> None:
    source = DataManagementKlineInspectorSource(_FakeViewModel(interval="15m"))

    assert source.get_interval() == "15m"


def test_reads_follow_the_view_model_after_a_second_inspection() -> None:
    """`get_klines`/`get_symbol`/`get_interval` are live reads, not a
    snapshot taken at construction — the same shard-swap behaviour
    `set_kline_inspector_data` produces on the real ViewModel."""
    view_model = _FakeViewModel(klines=[object()], symbol="BTCUSDT", interval="1m")
    source = DataManagementKlineInspectorSource(view_model)

    view_model.kline_inspector_klines = [object(), object()]
    view_model.klineInspectorSymbol = "ETHUSDT"
    view_model.klineInspectorInterval = "5m"

    assert len(list(source.get_klines())) == 2
    assert source.get_symbol() == "ETHUSDT"
    assert source.get_interval() == "5m"
