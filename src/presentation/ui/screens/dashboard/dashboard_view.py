from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QScrollArea
from PySide6.QtCore import Qt
from Binace_Bot.src.presentation.ui.components.control_card import ControlCard
from Binace_Bot.src.presentation.ui.components.monitor_card import MonitorCard

class DashboardView(QWidget):
    """
    @brief The View for the Dashboard Screen. Assembles dumb components into a layout.
    @details Contains ControlCard, MonitorCard, and a placeholder for ChartCard.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Left Column: QScrollArea for Dynamic ChartCards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        # Container for the dynamic cards inside the scroll area
        self.charts_container = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_container)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(15)
        self.charts_layout.addStretch() # Push items up
        
        self.scroll_area.setWidget(self.charts_container)

        # Right Column: Controls and Monitor
        right_column = QVBoxLayout()
        right_column.setSpacing(20)

        # Initialize Global Cards
        self.control_card = ControlCard()
        self.monitor_card = MonitorCard()

        right_column.addWidget(self.control_card, 1) # Control takes less space
        right_column.addWidget(self.monitor_card, 3) # Monitor takes more vertical space

        # Add to main layout
        main_layout.addWidget(self.scroll_area, 3) # Charts take 3 parts width
        main_layout.addLayout(right_column, 1)     # Right column takes 1 part width

    def render_symbol_cards(self, symbols: list[str]) -> list:
        """
        @brief Dynamically instantiates ChartCards for given symbols.
        @returns A list of the created ChartCards.
        """
        # Clear existing cards first (except stretch)
        for i in reversed(range(self.charts_layout.count() - 1)): 
            widget = self.charts_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                
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
