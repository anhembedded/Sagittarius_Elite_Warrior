from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget


class BaseCard(QFrame):
    """
    @brief The standard QFrame layout for all UI Cards.
    @details Provides a consistent header, body, and footer structure.
    Styling is handled globally via QSS targeting '#base_card'.
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("base_card")

        # Main layout for the entire card (No margins to allow header to touch edges)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._setup_header(title)
        self._setup_body()
        self._setup_footer()

    def _setup_header(self, title: str):
        self.header = QFrame()
        self.header.setObjectName("base_card_header")

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(15, 10, 15, 10)

        # Default Title Label
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("base_card_title")

        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        self.main_layout.addWidget(self.header)

    def _setup_body(self):
        self.body = QWidget()
        self.body.setObjectName("base_card_body")

        # Body Layout (Subclasses will add their widgets here)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(15, 15, 15, 15)
        self.body_layout.setSpacing(10)

        self.main_layout.addWidget(self.body, 1)  # Body expands

    def _setup_footer(self):
        self.footer = QWidget()
        self.footer.setObjectName("base_card_footer")
        self.footer.setVisible(False)  # Hidden by default

        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(15, 10, 15, 10)

        self.main_layout.addWidget(self.footer)

    def add_to_header(self, widget: QWidget):
        """Allows subclasses to inject widgets (like buttons) into the header."""
        self.header.layout().addWidget(widget)

    def add_to_footer(self, widget: QWidget):
        """Allows subclasses to inject widgets into the footer."""
        self.footer.setVisible(True)
        self.footer.layout().addWidget(widget)
