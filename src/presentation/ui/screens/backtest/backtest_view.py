from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QScrollArea, QSplitter, QVBoxLayout, QWidget

from sagittarius_engine.extensions.pyside_mvc import BaseView, create_quick_widget
from .backtest_view_model import BackTestViewModel

_QML_DIR = Path(__file__).parent

class BackTestView(BaseView):
    """
    View for the BackTest Screen, using a Hybrid QSplitter layout.
    Left: QScrollArea containing ChartCards.
    Right: QQuickWidget hosting BackTestPanel.qml.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_model = BackTestViewModel()
        self._setup_ui()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(10)

        # 1. Top Panel (Toolbar + Metrics) - Not in splitter so it has fixed height
        self.top_widget = create_quick_widget()
        self.top_widget.setFixedHeight(120)  # Approximate height for toolbar + metrics
        self.top_widget.rootContext().setContextProperty("viewModel", self._view_model)
        self.top_widget.setSource(QUrl.fromLocalFile(str(_QML_DIR / "BackTestTopPanel.qml")))
        
        outer_layout.addWidget(self.top_widget)

        # Vertical Splitter for Chart and Trade Logs
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        outer_layout.addWidget(main_splitter, 1)

        # 2. Middle: Chart (in a container)
        self.charts_container = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_container)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(0)
        
        main_splitter.addWidget(self.charts_container)

        # 3. Bottom: Trade Logs Panel
        self.bottom_widget = create_quick_widget()
        self.bottom_widget.rootContext().setContextProperty("viewModel", self._view_model)
        self.bottom_widget.setSource(QUrl.fromLocalFile(str(_QML_DIR / "BackTestTradeLogs.qml")))
        
        main_splitter.addWidget(self.bottom_widget)

        # Give chart more space initially
        main_splitter.setStretchFactor(0, 3) 
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([600, 200])

    def render_symbol_cards(self, symbols: list[str]) -> list:
        # Clear existing
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
            from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import ChartCard
            card = ChartCard(symbol)
            self.chart_cards.append(card)
            self.charts_layout.addWidget(card, 1)

        return self.chart_cards
