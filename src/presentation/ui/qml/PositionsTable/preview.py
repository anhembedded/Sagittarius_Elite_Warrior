"""Standalone live preview for `PositionsTable.qml` (`EPIC-021I`)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_vm import (
    PositionsVM,
)
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

_QML_FILE = Path(__file__).with_name("PositionsTable.qml")

_SAMPLE_POSITIONS = [
    LivePosition(
        symbol="BTCUSDT",
        position_amt=Decimal("0.05"),
        entry_price=Decimal("64000.00"),
        mark_price=Decimal("64850.50"),
        unrealized_pnl=Decimal("42.53"),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=Decimal("32140.00"),
        updated_at=datetime.now(UTC),
    ),
    LivePosition(
        symbol="ETHUSDT",
        position_amt=Decimal("-1.2"),
        entry_price=Decimal("3400.00"),
        mark_price=Decimal("3455.10"),
        unrealized_pnl=Decimal("-66.12"),
        leverage=5,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=datetime.now(UTC),
    ),
]


def build_preview() -> QWidget:
    """Builds the PositionsTable preview, no host chrome."""
    vm = PositionsVM()
    vm.set_rows([build_position_row(position) for position in _SAMPLE_POSITIONS])

    quick = QQuickWidget()
    quick.setObjectName("positionsTablePreview")
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", get_theme_bridge())

    quick.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
    if quick.status() is not QQuickWidget.Status.Ready:
        raise RuntimeError(
            f"QML failed to load: {_QML_FILE}\n"
            + "\n".join(error.toString() for error in quick.errors())
        )
    quick.resize(760, 320)
    return quick
