from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from sagittarius_engine.extensions.pyside_mvc import BaseView, create_quick_widget

_QML_DIR = Path(__file__).parent
_TOP_PANEL_QML = "BackTestTopPanel.qml"
_TRADE_LOGS_QML = "BackTestTradeLogs.qml"

#: Approximate height for the toolbar + metrics rows in BackTestTopPanel.qml.
_TOP_PANEL_HEIGHT = 120


class BackTestView(BaseView):
    """
    @brief View for the Backtest Screen, using a hybrid QSplitter layout:
    a fixed-height top toolbar/metrics panel (QML), a chart area (QtWidgets
    `ChartCard`, matching the Dev Board's hybrid approach), and a bottom
    trade-logs panel (QML).

    @details
    Two `QQuickWidget`s share one `viewModel` context property — set once via
    `set_view_model()` — rather than one `QmlHostView` per the framework's
    single-document convention, because this screen genuinely needs 2 QML
    documents at once (BOT-022 §2 layout) plus a native chart widget between
    them. Ordering contract mirrors `QmlHostView` exactly: the Presenter
    calls `set_view_model()` before `load_qml()`, so both QML documents parse
    against a view model that already holds real values.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_model = None
        self.chart_cards: list = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(10)

        self.top_widget = create_quick_widget()
        self.top_widget.setFixedHeight(_TOP_PANEL_HEIGHT)
        outer_layout.addWidget(self.top_widget)

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        outer_layout.addWidget(main_splitter, 1)

        self.charts_container = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_container)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(0)
        main_splitter.addWidget(self.charts_container)

        self.bottom_widget = create_quick_widget()
        main_splitter.addWidget(self.bottom_widget)

        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([600, 200])

    def set_view_model(self, view_model, context_name: str = "viewModel") -> None:
        """Registers the screen's ViewModel as a QML context property on
        BOTH quick widgets. Must be called before load_qml() — see the
        ordering contract in this class's docstring."""
        self._view_model = view_model
        self.top_widget.rootContext().setContextProperty(context_name, view_model)
        self.bottom_widget.rootContext().setContextProperty(context_name, view_model)

    def load_qml(self) -> None:
        """Loads this screen's fixed pair of QML documents."""
        self.top_widget.setSource(QUrl.fromLocalFile(str(_QML_DIR / _TOP_PANEL_QML)))
        self.bottom_widget.setSource(
            QUrl.fromLocalFile(str(_QML_DIR / _TRADE_LOGS_QML))
        )

    def apply_ui_mode(self, mode, section_key: str = "main") -> None:
        """Receives FSM state changes from BasePresenter and forwards them to
        the ViewModel's `uiMode` property — same duck-typed hook
        `QmlHostView.apply_ui_mode` provides for single-document screens."""
        if self._view_model is None:
            return
        mode_value = getattr(mode, "value", mode)
        self._view_model.set_ui_mode(str(mode_value))

    def render_symbol_cards(self, symbols: list[str]) -> list:
        for i in reversed(range(self.charts_layout.count())):
            item = self.charts_layout.itemAt(i)
            widget = item.widget()
            if widget:
                if hasattr(widget, "cleanup"):
                    widget.cleanup()
                self.charts_layout.removeItem(item)
                widget.deleteLater()

        self.chart_cards = []
        for symbol in symbols:
            from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
                ChartCard,
            )

            card = ChartCard(symbol)
            self.chart_cards.append(card)
            self.charts_layout.addWidget(card, 1)

        return self.chart_cards
