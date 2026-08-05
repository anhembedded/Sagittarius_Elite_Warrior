from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from Binace_Bot.src.presentation.ui.components.base_card import BaseCard

class ChartCard(BaseCard):
    """
    @brief A dumb component containing a Chart (e.g. pyqtgraph).
    @details Instantiated dynamically by the View for each Symbol.
    """
    def __init__(self, symbol: str, parent=None):
        # Pass the symbol to the title of the BaseCard
        super().__init__(title=f"Live Chart: {symbol}", parent=parent)
        self.symbol = symbol
        self._setup_content()

    def _setup_content(self):
        # Placeholder for pyqtgraph plot
        self.lbl_placeholder = QLabel(f"Candlestick Chart for {self.symbol} will go here.")
        self.lbl_placeholder.setAlignment(Qt.AlignCenter)
        self.lbl_placeholder.setStyleSheet("color: #888888; font-size: 16px;")
        
        self.body_layout.addWidget(self.lbl_placeholder)

    def update_price(self, data: dict) -> None:
        """
        @brief Public method for the Presenter to push chart data.
        """
        pass # To be implemented
