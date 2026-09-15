"""Standalone live preview for `PositionsTable.qml` (`EPIC-021I`)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import StyleRole
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_vm import (
    PositionsVM,
)

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

    surface = QuickSurface(
        _QML_FILE,
        surface=StyleRole.SURFACE,
        context={"vm": vm},
        object_name="positionsTablePreview",
    )
    surface.resize(760, 320)
    return surface
