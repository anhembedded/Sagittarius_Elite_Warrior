"""QtWidgets building blocks shared across the Backtest screen's sub-panels
(EPIC-006E) — each a direct port of a `components/` QML file used by more
than one of `BackTestTopPanel`/`BackTestTradeLogsPanel`/the modals: `MetricCard`
(top panel stat cards + `ExtendedMetricsModal`) and `DynamicTabBar` (trade
logs' trades/logs switch). `AppProgressBar.qml`'s port lives in
`components/app_progress_bar.py` — reused rather than duplicated. It sat in
`data_management/` until `EPIC-007E`, which is why two other screens used to
import across a screen boundary to reach it.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
)

_RGB_HEX_LENGTH = 6
_COMPACT_VALUE_LENGTH_THRESHOLD = 10


def with_alpha(hex_color: str, alpha: float) -> str:
    """Port of `MetricCard.qml`'s `root._withAlpha()` — builds a `rgba()`
    QSS literal from a `#RRGGBB` string, matching `Qt.rgba()`'s semantics
    without needing a QML `Qt.color()` call."""
    color = hex_color.lstrip("#")
    if len(color) != _RGB_HEX_LENGTH:
        return hex_color
    r, g, b = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


class _TabButton(QPushButton):
    """One `DynamicTabBarWidget` entry — label + optional count badge, with
    an accent left-dot when active. Mirrors `DynamicTabBar.qml`'s per-tab
    `Rectangle` delegate."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        self._dot = QFrame()
        self._dot.setFixedSize(3, 12)
        self._dot.setStyleSheet(
            f"background-color: {Palette.ACCENT}; border-radius: 1px; border: none;"
        )
        self._dot.hide()
        layout.addWidget(self._dot)

        self._label = QLabel()
        self._label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._label)

        self._badge = QLabel()
        self._badge.setStyleSheet("background: transparent; border: none;")
        self._badge.setContentsMargins(6, 0, 6, 0)
        self._badge.setFixedHeight(18)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._badge)

        self._is_active = False

    def set_content(self, label: str, badge: str) -> None:
        self._label.setText(label)
        self._badge.setText(str(badge) if badge else "")
        self._badge.setVisible(bool(badge))
        self._apply_style()

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self._dot.setVisible(active)
        self._apply_style()

    def _apply_style(self) -> None:
        active = self._is_active
        self._label.setStyleSheet(
            f"background: transparent; border: none; "
            f"color: {Palette.TEXT_PRIMARY if active else Palette.MUTED}; "
            f"font-size: 11px; font-weight: {'bold' if active else 'normal'};"
        )
        badge_bg = Palette.STATE_HOVER_BG if active else Palette.BG_CARD_HEADER
        badge_border = Palette.ACCENT if active else Palette.STATE_NAV_BORDER
        badge_color = Palette.ACCENT if active else Palette.MUTED
        self._badge.setStyleSheet(
            f"background-color: {badge_bg}; border: 1px solid {badge_border}; "
            f"border-radius: 9px; color: {badge_color}; font-size: 10px; font-weight: bold;"
        )
        self.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.STATE_HOVER_BG if active else 'transparent'}; "
            f"border: 1px solid {Palette.STATE_NAV_BORDER if active else 'transparent'}; border-radius: 6px; }} "
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )


class DynamicTabBarWidget(QWidget):
    """Port of `components/DynamicTabBar.qml`: a row of styled tab buttons
    with count badges. Used by `BackTestTradeLogsPanel`'s trades/logs
    switch (EPIC-006E2)."""

    tabSelected = Signal(int, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._buttons: list[_TabButton] = []
        self._tabs_model: list[dict[str, object]] = []
        self._current_index = 0

    def set_tabs_model(self, tabs: list[dict[str, object]]) -> None:
        self._tabs_model = tabs
        for btn in self._buttons:
            self._layout.removeWidget(btn)
            btn.deleteLater()
        self._buttons = []
        while self._layout.count():
            self._layout.takeAt(0)

        for index, tab in enumerate(tabs):
            tab_id = str(tab.get("id", index))
            btn = _TabButton()
            btn.setObjectName(f"tabBtn_{tab_id}")
            btn.set_content(str(tab.get("label", "")), str(tab.get("badge", "")))
            btn.clicked.connect(
                lambda _checked=False, i=index, tid=tab_id: self._on_clicked(i, tid)
            )
            self._layout.addWidget(btn)
            self._buttons.append(btn)
        self._layout.addStretch(1)
        self._apply_active()

    def set_current_index(self, index: int) -> None:
        if index != self._current_index:
            self._current_index = index
            self._apply_active()

    def _apply_active(self) -> None:
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == self._current_index)

    def _on_clicked(self, index: int, tab_id: str) -> None:
        self._current_index = index
        self._apply_active()
        self.tabSelected.emit(index, tab_id)
