"""One colour helper left over from the Backtest screen's QML port.

This module used to hold `MetricCardWidget` and `DynamicTabBarWidget`, the
QtWidgets ports of `MetricCard.qml` and `DynamicTabBar.qml` (`EPIC-006E`).
`EPIC-007F` replaced both with the engine's `StatCard` and `TabBar` and
deleted them, leaving only the helper below — still used by
`backtest_trade_logs_panel.py` for its P&L pill backgrounds.

Kept as its own module rather than inlined into that one consumer: a
second consumer is likely the moment another panel needs a tinted
background, and moving it back out again is the more disruptive edit.
"""

from __future__ import annotations

_RGB_HEX_LENGTH = 6


def with_alpha(hex_color: str, alpha: float) -> str:
    """Builds an `rgba()` QSS literal from a `#RRGGBB` string.

    Originally a port of `MetricCard.qml`'s `root._withAlpha()`, matching
    `Qt.rgba()`'s semantics without needing a QML `Qt.color()` call. That
    card is gone; the trade-log rows still need the same tint.
    """
    color = hex_color.lstrip("#")
    if len(color) != _RGB_HEX_LENGTH:
        return hex_color
    r, g, b = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"
