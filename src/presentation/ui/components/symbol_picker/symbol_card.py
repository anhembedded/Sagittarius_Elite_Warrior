"""One symbol in the picker's grid: the pair, its quote, and its star."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...kit import SelectableCard, StyledButton, StyleRole, apply_role
from .filtering import SymbolEntry

#: Shown under the pair instead of its quote when the symbol is the one the
#: screen is currently running on — the state a user scanning the grid most
#: needs to find, and the one thing worth spending the subtitle line on.
_CURRENT_TEXT = "Đang dùng"
_RECENT_TEXT = "Gần đây"
_QUOTE_TEXT = "Quote {quote}"
_UNKNOWN_QUOTE_TEXT = "—"

_STAR_ON = "★"
_STAR_OFF = "☆"
_STAR_SIZE = 24

_CARD_HEIGHT = 58


class SymbolCard(SelectableCard):
    """
    @brief One tradable pair, rendered as `BASE` + dimmed `quote` over a
    status line, with a star that toggles favourite without choosing it.

    @details The two-tone pair label is the point: a grid of fourteen hundred
    strings that all end in `USDT` is unreadable, and dimming the half every
    row shares is what lets the eye land on the half that differs.

    `favourite_toggled` is separate from `clicked` because starring is not
    choosing — a user curating favourites would otherwise close the dialog on
    every star. The card does not flip its own star either: the favourite set
    lives with the dialog's owner, and a card that toggled in place would show
    a state nothing had stored.
    """

    favourite_toggled = Signal(str)

    def __init__(self, entry: SymbolEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self.setObjectName(f"symbolCard_{entry.symbol}")
        self.setFixedHeight(_CARD_HEIGHT)
        self.selected = entry.is_current

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        text_column.addWidget(self._build_pair_label(entry))
        text_column.addWidget(self._build_status_label(entry))
        row.addLayout(text_column, 1)
        row.addWidget(self._build_star(entry), 0, Qt.AlignmentFlag.AlignTop)

        self.body_layout.addLayout(row)

    @property
    def entry(self) -> SymbolEntry:
        """What this card renders — read by the dialog's keyboard navigation,
        so it never has to parse the symbol back out of a label."""
        return self._entry

    @staticmethod
    def _build_pair_label(entry: SymbolEntry) -> QLabel:
        """`ETH` at full strength, `USDT` dimmed — one label using rich text,
        so the two halves cannot drift apart across a layout change."""
        parts = entry.parts
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        if parts.has_known_quote:
            label.setText(f"<b>{parts.base}</b>{parts.quote}")
        else:
            label.setText(f"<b>{parts.base}</b>")
        apply_role(label, StyleRole.TABLE_CELL_STRONG)
        return label

    @staticmethod
    def _build_status_label(entry: SymbolEntry) -> QLabel:
        if entry.is_current:
            text = _CURRENT_TEXT
        elif entry.is_recent:
            text = _RECENT_TEXT
        elif entry.parts.has_known_quote:
            text = _QUOTE_TEXT.format(quote=entry.parts.quote)
        else:
            text = _UNKNOWN_QUOTE_TEXT
        label = QLabel(text)
        apply_role(label, StyleRole.CAPTION)
        return label

    def _build_star(self, entry: SymbolEntry) -> StyledButton:
        star = StyledButton(
            _STAR_ON if entry.is_favourite else _STAR_OFF,
            role=StyleRole.GHOST_BUTTON,
        )
        star.setObjectName(f"symbolStar_{entry.symbol}")
        star.setFixedSize(_STAR_SIZE, _STAR_SIZE)
        star.setCursor(Qt.CursorShape.PointingHandCursor)
        star.setToolTip("Bỏ yêu thích" if entry.is_favourite else "Đánh dấu yêu thích")
        star.clicked.connect(lambda: self.favourite_toggled.emit(entry.symbol))
        return star
