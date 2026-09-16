"""Standalone live preview for the TradeLogTable QML component.

Seeds six real `TradeLogRow` instances matching the mockup's tab counts
(6 total, 4 long, 2 short, 2 wins, 4 losses) — the same dataclass
`build_trade_log_rows()` produces from a run's actual `Trade` list, not a
fabricated dict shape.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TradeLogTable.trade_log_row import (
    TradeLogRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TradeLogTable.trade_log_vm import (
    TradeLogVM,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import StyleRole

_QML_FILE = Path(__file__).with_name("TradeLogTable.qml")

_ENTRY = datetime(2026, 7, 23, 16, 59, tzinfo=UTC)


def _row(
    index: int,
    side: PositionSide,
    pnl: float,
    minutes: int,
    *,
    entry_reason: str = "",
    metadata: dict[str, object] | None = None,
) -> TradeLogRow:
    entry = _ENTRY + timedelta(minutes=index * 20)
    entry_price = 64_800.0
    exit_price = entry_price + (pnl if side is PositionSide.LONG else -pnl)
    return TradeLogRow(
        index=index,
        entry_time=entry,
        entry_price=entry_price,
        exit_time=entry + timedelta(minutes=minutes),
        exit_price=exit_price,
        quantity=0.154,
        pnl=pnl,
        pnl_percent=pnl / entry_price * 100,
        side=side,
        entry_reason=entry_reason,
        metadata=metadata or {},
    )


_ROWS = (
    _row(1, PositionSide.LONG, -38.49, 7),
    _row(
        2,
        PositionSide.LONG,
        -22.33,
        35,
        entry_reason="EMA Crossover 12/26 crosses up",
        metadata={"r_multiple": "-0.4R", "fee": "9.90 USD"},
    ),
    _row(3, PositionSide.LONG, 41.20, 18),
    _row(4, PositionSide.LONG, -32.64, 12),
    _row(5, PositionSide.SHORT, 57.30, 44),
    _row(6, PositionSide.SHORT, -20.31, 44),
)


def build_preview() -> QWidget:
    """Builds the table body with six example trades, no host chrome."""
    vm = TradeLogVM(get_rows=lambda: _ROWS, get_timezone_name=lambda: "UTC")
    vm.refresh()

    surface = QuickSurface(
        _QML_FILE,
        surface=StyleRole.SURFACE,
        context={"vm": vm},
        object_name="tradeLogTablePreview",
    )
    surface.resize(900, 420)
    return surface
