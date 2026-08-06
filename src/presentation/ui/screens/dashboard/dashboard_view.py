from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QScrollArea,
    QLabel,
)
from Binace_Bot.src.presentation.ui.components.control_card import ControlCard
from Binace_Bot.src.presentation.ui.components.monitor_card import MonitorCard

_HEADER_TITLE = "Developer Board (Live Testbed)"


class DashboardView(QWidget):
    """
    @brief The View for the Dev Board Screen — a developer testbed, not the app's
    end-user dashboard. Assembles dumb components into a layout.
    @details Contains ControlCard, MonitorCard, and a placeholder for ChartCard.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(20, 20, 20, 20)
        outer_layout.setSpacing(15)

        self.lbl_header = QLabel(_HEADER_TITLE)
        self.lbl_header.setObjectName("PanelTitle")
        outer_layout.addWidget(self.lbl_header)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(20)
        outer_layout.addLayout(main_layout)

        # Left Column: QScrollArea for Dynamic ChartCards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # Container for the dynamic cards inside the scroll area
        self.charts_container = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_container)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(15)
        self.charts_layout.addStretch()  # Push items up

        self.scroll_area.setWidget(self.charts_container)

        # Right Column: Controls and Monitor
        right_column = QVBoxLayout()
        right_column.setSpacing(20)

        # Initialize Global Cards
        self.control_card = ControlCard()
        self.monitor_card = MonitorCard()

        right_column.addWidget(self.control_card, 1)  # Control takes less space
        right_column.addWidget(
            self.monitor_card, 3
        )  # Monitor takes more vertical space

        # Add to main layout
        main_layout.addWidget(self.scroll_area, 3)  # Charts take 3 parts width
        main_layout.addLayout(right_column, 1)  # Right column takes 1 part width

    def render_symbol_cards(self, symbols: list[str]) -> list:
        """
        @brief Dynamically instantiates ChartCards for given symbols.
        @returns A list of the created ChartCards.
        """
        # Clear existing cards first (except stretch)
        for i in reversed(range(self.charts_layout.count() - 1)):
            item = self.charts_layout.itemAt(i)
            widget = item.widget()
            if widget:
                # 1. Clear dữ liệu đồ họa ngầm của pyqtgraph
                if hasattr(widget, "cleanup"):
                    widget.cleanup()

                # 2. Xóa widget khỏi layout
                self.charts_layout.removeItem(item)

                # 3. Ra lệnh hủy hoàn toàn trong bộ nhớ C++
                widget.deleteLater()

        self.chart_cards = []

        # We need to insert before the stretch item
        stretch_index = self.charts_layout.count() - 1

        for symbol in symbols:
            from Binace_Bot.src.presentation.ui.components.chart_card import ChartCard

            card = ChartCard(symbol)
            self.chart_cards.append(card)
            self.charts_layout.insertWidget(stretch_index, card)
            stretch_index += 1

        return self.chart_cards
