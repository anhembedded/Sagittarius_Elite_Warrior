from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


# ---------------------------------------------------------------------------
# Type alias: (display_label, route_name)
# ---------------------------------------------------------------------------
NavRoute = Tuple[str, str]


class Sidebar(QWidget):
    """
    @brief Self-contained navigation sidebar component.

    @details
    Follows SRP: responsible only for rendering nav buttons and tracking
    which route is currently active. Navigation decisions are communicated
    upward via sig_navigate — this widget knows nothing about screens.

    Usage:
        routes = [("Dashboard", "dashboard"), ("Database", "data_management")]
        sidebar = Sidebar(routes=routes)
        sidebar.sig_navigate.connect(main_window.switch_screen)
        sidebar.set_active("dashboard")  # Set initial active state
    """

    # Emitted when the user clicks a nav button. Carries the route_name.
    sig_navigate = Signal(str)

    _TITLE_STYLE = "font-size: 20px; font-weight: bold; margin-bottom: 20px;"
    _SIDEBAR_STYLE = "background-color: #2b2b2b; color: white;"
    _MIN_BUTTON_HEIGHT = 40
    _MAX_WIDTH = 250

    def __init__(self, routes: List[NavRoute], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMaximumWidth(self._MAX_WIDTH)
        self.setStyleSheet(self._SIDEBAR_STYLE)

        self._buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(10)

        self._build_title(layout)
        self._build_nav_buttons(layout, routes)

    def _build_title(self, layout: QVBoxLayout) -> None:
        title = QLabel("Binance Bot")
        title.setStyleSheet(self._TITLE_STYLE)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

    def _build_nav_buttons(self, layout: QVBoxLayout, routes: List[NavRoute]) -> None:
        for label, route_name in routes:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setMinimumHeight(self._MIN_BUTTON_HEIGHT)
            # Capture route_name in default arg to avoid late-binding closure issue
            btn.clicked.connect(lambda checked, r=route_name: self.sig_navigate.emit(r))
            self._buttons[route_name] = btn
            layout.addWidget(btn)

    def set_active(self, route_name: str) -> None:
        """
        @brief Update button checked states to reflect the active route.
        @param route_name The currently active route.
        """
        for name, btn in self._buttons.items():
            btn.setChecked(name == route_name)
