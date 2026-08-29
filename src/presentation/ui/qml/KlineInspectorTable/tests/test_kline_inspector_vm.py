"""No-GUI tests for KlineInspectorVM."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.KlineInspectorTable.kline_inspector_vm import (
    KlineInspectorVM,
)

_T0 = datetime(2026, 7, 25, 13, 46, tzinfo=UTC)


def _candle(index: int, open_price: float, close_price: float) -> MarketData:
    open_time = _T0 + timedelta(minutes=index)
    return MarketData(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=1),
        open_price=open_price,
        high_price=max(open_price, close_price) + 2.0,
        low_price=min(open_price, close_price) - 2.0,
        close_price=close_price,
        volume=10.0,
        quote_asset_volume=10.0 * close_price,
        number_of_trades=50,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=5.0 * close_price,
    )


_CANDLES = (
    _candle(0, 100.0, 105.0),  # bullish
    _candle(1, 105.0, 95.0),  # bearish
)


def _vm(candles=_CANDLES, symbol="BTCUSDT", interval="1m") -> KlineInspectorVM:
    vm = KlineInspectorVM(
        get_klines=lambda: candles,
        get_symbol=lambda: symbol,
        get_interval=lambda: interval,
    )
    vm.refresh()
    return vm


def test_refresh_builds_one_row_per_candle():
    vm = _vm()

    assert vm.rowCount == 2
    assert len(vm.rows) == 2


def test_refresh_reads_symbol_and_interval_from_the_host():
    vm = _vm(symbol="ETHUSDT", interval="5m")

    assert vm.symbol == "ETHUSDT"
    assert vm.interval == "5m"


def test_rows_carry_the_same_formatting_the_real_model_would():
    vm = _vm()

    assert vm.rows[0]["formattedTime"] == "2026-07-25 13:46:00"
    assert vm.rows[0]["closePrice"] == "105.00"
    assert vm.rows[0]["isBullish"] is True
    assert vm.rows[1]["isBullish"] is False


def test_an_empty_candle_list_yields_no_rows():
    vm = _vm(candles=())

    assert vm.rowCount == 0
    assert vm.rows == []


def test_refresh_replaces_the_previous_rows():
    calls = {"candles": _CANDLES}
    vm = KlineInspectorVM(
        get_klines=lambda: calls["candles"],
        get_symbol=lambda: "BTCUSDT",
        get_interval=lambda: "1m",
    )
    vm.refresh()
    assert vm.rowCount == 2

    calls["candles"] = _CANDLES[:1]
    vm.refresh()

    assert vm.rowCount == 1
