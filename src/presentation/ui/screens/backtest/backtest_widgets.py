"""QtWidgets building blocks shared across the Backtest screen's sub-panels
(EPIC-006E) — each a direct port of a `components/` QML file used by more
than one of `BackTestTopPanel`/`BackTestTradeLogsPanel`/the modals: `MetricCard`
(top panel stat cards + `ExtendedMetricsModal`) and `DynamicTabBar` (trade
logs' trades/logs switch). `AppProgressBar.qml`'s port already exists —
`data_management.data_management_widgets.AppProgressBarWidget` — reused
as-is rather than duplicated.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)

_CARD_BG = "#14161f"
_CARD_BORDER = "#232634"
_CARD_HOVER_BG = "#1a1d29"
_CARD_HOVER_BORDER = "#363a4d"


def with_alpha(hex_color: str, alpha: float) -> str:
    """Port of `MetricCard.qml`'s `root._withAlpha()` — builds a `rgba()`
    QSS literal from a `#RRGGBB` string, matching `Qt.rgba()`'s semantics
    without needing a QML `Qt.color()` call."""
    color = hex_color.lstrip("#")
    if len(color) != 6:
        return hex_color
    r, g, b = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


class MetricCardWidget(QFrame):
    """Port of `components/MetricCard.qml`: title + value/suffix + optional
    badge, with a hover highlight. Used by `BackTestTopPanel`'s stat-cards
    row and `ExtendedMetricsModal` (EPIC-006E3)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(120, 80)
        self.setStyleSheet(
            f"MetricCardWidget {{ background-color: {_CARD_BG}; "
            f"border: 1px solid {_CARD_BORDER}; border-radius: 8px; }}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self._title_label = QLabel()
        self._title_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 10px; font-weight: bold; "
            f"letter-spacing: 0.8px; background: transparent; border: none;"
        )
        title_row.addWidget(self._title_label, 1)
        self._info_icon = QLabel()
        self._info_icon.setPixmap(
            get_icon_loader().get_icon("info", Palette.MUTED, 12).pixmap(12, 12)
        )
        self._info_icon.setStyleSheet("background: transparent; border: none;")
        title_row.addWidget(self._info_icon)
        layout.addLayout(title_row)

        value_row = QHBoxLayout()
        value_row.setSpacing(4)
        self._value_label = QLabel()
        self._value_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; background: transparent; border: none;"
        )
        value_row.addWidget(self._value_label)
        self._suffix_label = QLabel()
        self._suffix_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 10px; font-weight: bold; "
            f"background: transparent; border: none;"
        )
        value_row.addWidget(self._suffix_label)
        self._badge_label = QLabel()
        self._badge_label.setStyleSheet(
            "font-size: 10px; font-weight: bold; border: none;"
        )
        self._badge_label.setContentsMargins(5, 2, 5, 2)
        value_row.addWidget(self._badge_label)
        value_row.addStretch(1)
        layout.addLayout(value_row)

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self.setStyleSheet(
            f"MetricCardWidget {{ background-color: {_CARD_HOVER_BG}; "
            f"border: 1px solid {_CARD_HOVER_BORDER}; border-radius: 8px; }}"
        )

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.setStyleSheet(
            f"MetricCardWidget {{ background-color: {_CARD_BG}; "
            f"border: 1px solid {_CARD_BORDER}; border-radius: 8px; }}"
        )

    def set_data(
        self,
        *,
        title: str,
        value: str,
        value_color: str,
        suffix: str,
        badge_text: str,
        badge_color: str,
    ) -> None:
        self._title_label.setText(title.upper())
        self._value_label.setText(value)
        self._value_label.setStyleSheet(
            f"color: {value_color}; font-size: {16 if len(value) > 10 else 18}px; "
            f"font-weight: bold; background: transparent; border: none;"
        )
        self._suffix_label.setText(suffix)
        self._suffix_label.setVisible(bool(suffix))
        self._badge_label.setText(badge_text)
        self._badge_label.setVisible(bool(badge_text))
        if badge_text:
            badge_text_color = badge_color if badge_color else Palette.MUTED
            badge_bg = with_alpha(badge_color, 0.2) if badge_color else "transparent"
            self._badge_label.setStyleSheet(
                f"color: {badge_text_color}; background-color: {badge_bg}; "
                f"font-size: 10px; font-weight: bold; border-radius: 4px; border: none;"
            )


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
        badge_bg = "#272a3e" if active else "#141620"
        badge_border = Palette.ACCENT if active else "#242738"
        badge_color = Palette.ACCENT if active else Palette.MUTED
        self._badge.setStyleSheet(
            f"background-color: {badge_bg}; border: 1px solid {badge_border}; "
            f"border-radius: 9px; color: {badge_color}; font-size: 10px; font-weight: bold;"
        )
        self.setStyleSheet(
            f"QPushButton {{ background-color: {'#1c1e2d' if active else 'transparent'}; "
            f"border: 1px solid {'#2c3045' if active else 'transparent'}; border-radius: 6px; }} "
            f"QPushButton:hover {{ background-color: {'#1c1e2d' if active else '#161722'}; }}"
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
