"""Standalone live preview for the KlineInspectorTable QML component.

Seeds real `MarketData` entities, built the same way
`test_kline_inspector_table_model.py`'s `_make_candle()` does — not a
fabricated dict shape.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.KlineInspectorTable.kline_inspector_vm import (
    KlineInspectorVM,
)
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

_QML_FILE = Path(__file__).with_name("KlineInspectorTable.qml")

_START = datetime(2026, 7, 25, 13, 46, tzinfo=UTC)
#: (open, close) pairs, matching the mockup's mixed up/down candles.
_PRICES = (
    (64_234.14, 64_248.09),
    (64_248.09, 64_231.10),
    (64_231.09, 64_236.33),
    (64_236.33, 64_242.00),
    (64_242.01, 64_235.80),
    (64_235.80, 64_218.01),
)


def _candle(index: int, open_price: float, close_price: float) -> MarketData:
    open_time = _START + timedelta(minutes=index)
    return MarketData(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=1),
        open_price=open_price,
        high_price=max(open_price, close_price) + 3.0,
        low_price=min(open_price, close_price) - 3.0,
        close_price=close_price,
        volume=10.0 + index,
        quote_asset_volume=(10.0 + index) * close_price,
        number_of_trades=600 + index * 200,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=5.0 * close_price,
    )


_CANDLES = tuple(
    _candle(index, open_price, close_price)
    for index, (open_price, close_price) in enumerate(_PRICES)
)


def build_preview() -> QWidget:
    """Builds the table body with six example candles, no host chrome."""
    vm = KlineInspectorVM(
        get_klines=lambda: _CANDLES,
        get_symbol=lambda: "BTCUSDT",
        get_interval=lambda: "1m",
    )
    vm.refresh()

    quick = QQuickWidget()
    quick.setObjectName("klineInspectorTablePreview")
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", get_theme_bridge())
    # QML context properties are borrowed references; retain for the scene
    # lifetime, same reasoning `QmlOverlay.__init__` documents.
    quick._kline_inspector_vm = vm

    quick.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
    if quick.status() is not QQuickWidget.Status.Ready:
        raise RuntimeError(
            f"QML failed to load: {_QML_FILE}\n"
            + "\n".join(error.toString() for error in quick.errors())
        )
    quick.resize(900, 420)
    return quick
