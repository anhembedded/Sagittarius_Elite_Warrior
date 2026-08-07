from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QSplitter,
    QLabel,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

from Binace_Bot.src.presentation.ui.components.control_card import ControlCard
from Binace_Bot.src.presentation.ui.components.indicator_control_card import (
    IndicatorControlCard,
)
from Binace_Bot.src.presentation.ui.components.monitor_card import MonitorCard

_HEADER_TITLE = "Developer Board (Live Testbed)"


class DashboardView(BaseView):
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

        # Horizontal split between the chart column and the right column —
        # a QSplitter (not a fixed-ratio QHBoxLayout) so the user can drag
        # the divider to give either side more room instead of content
        # silently clipping at a fixed proportion of a fixed window size.
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        outer_layout.addWidget(main_splitter, 1)

        # Left Column: QScrollArea for Dynamic ChartCards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # Container for the dynamic cards inside the scroll area
        self.charts_container = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_container)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(15)
        # No trailing stretch here: chart cards are added with a stretch factor
        # (see render_symbol_cards) so they expand to fill the available height
        # instead of being squeezed to their minimum size with empty space below.

        self.scroll_area.setWidget(self.charts_container)

        # Right Column: Controls and Monitor — QScrollArea so a growing set of
        # cards (ControlCard, IndicatorControlCard, MonitorCard, ...) never
        # gets clipped by the window height; it scrolls instead.
        right_scroll_area = QScrollArea()
        right_scroll_area.setWidgetResizable(True)
        # Deliberately no horizontal scrollbar policy override — default
        # AsNeeded means content is scrollable, not silently clipped, if the
        # splitter is ever dragged narrower than a card's natural width.

        right_container = QWidget()
        right_column = QVBoxLayout(right_container)
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(20)

        # Initialize Global Cards
        self.control_card = ControlCard()
        self.indicator_control_card = IndicatorControlCard()
        self.monitor_card = MonitorCard()

        right_column.addWidget(self.control_card)
        right_column.addWidget(self.indicator_control_card)
        right_column.addWidget(self.monitor_card)
        right_column.addStretch()

        right_scroll_area.setWidget(right_container)

        # Add to the splitter — initial sizes only (a hint, not a cap); the
        # user can drag the handle to resize either side at any time.
        main_splitter.addWidget(self.scroll_area)
        main_splitter.addWidget(right_scroll_area)
        main_splitter.setStretchFactor(0, 3)  # Charts get more room initially
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([900, 400])

    def render_symbol_cards(self, symbols: list[str]) -> list:
        """
        @brief Dynamically instantiates ChartCards for given symbols.
        @returns A list of the created ChartCards.
        """
        # Clear existing cards first
        for i in reversed(range(self.charts_layout.count())):
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

        for symbol in symbols:
            from Binace_Bot.src.presentation.ui.components.chart_card import ChartCard

            card = ChartCard(symbol)
            self.chart_cards.append(card)
            # Stretch factor 1: cards share the full available height instead of
            # shrinking to their minimum size (there is no trailing spacer item).
            self.charts_layout.addWidget(card, 1)

        return self.chart_cards
