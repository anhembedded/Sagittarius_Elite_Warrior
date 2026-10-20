"""`EPIC-043C` — a state told as an icon and a word, the word in the state's tone.

Two plain labels in a row: the icon, then the word. A QLabel shows a picture or a text, never both,
so the badge is the stock composite the notice bar is. It keeps the label's `text()` and `setText()`
for what reads it, shows `StateLook`'s icon in the tone's colour and the word in the same colour
(`paint_label_tone`), and draws the icon again when the palette changes (a switch of colour scheme reaches every
widget as `QEvent.PaletteChange`). A state with no look
is its word alone. The word is what carries the meaning; the icon and colour add to it
(`ui-presentation-rule.md` §1).

Capability: Show a state as an icon and a word, coloured by meaning (a bot's state, a connection)
    Also: status badge, state badge, status icon, state label, connection state, lifecycle state
    Use: StateBadge, StateLook
    User: src/modules/bots/ui/bots_screen/identity_strip.py
    Status: stable
"""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QStyle, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.state_look import StateLook
from Sagittarius_Elite_Warrior.src.support.ui_kit.tone_icon import tone_icon
from Sagittarius_Elite_Warrior.src.support.ui_kit.tone_label import paint_label_tone


class StateBadge(QWidget):
    """@brief An icon and a word for a state."""

    def __init__(
        self, object_name: str, parent: QWidget | None = None, *, wrap: bool = False
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._look: StateLook | None = None
        self._icon = plain_label()
        self._icon.setObjectName(f"{object_name}::icon")
        self._text = plain_label()
        self._text.setObjectName(f"{object_name}::text")
        self._text.setWordWrap(wrap)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._icon, 0)
        row.addWidget(self._text, 1)
        # Held to its content in a status bar, where a stretching label would crowd its neighbours.
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self._icon.hide()

    def text(self) -> str:
        return self._text.text()

    def setText(self, text: str) -> None:
        self._text.setText(text)

    def show_state(self, text: str, look: StateLook | None) -> None:
        """Says `text` with `look`'s icon and tone, or as the word alone with `None`."""
        self._look = look
        self._text.setText(text)
        paint_label_tone(self._text, Tone.NEUTRAL if look is None else look.tone)
        self._show_icon()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._show_icon()

    def _show_icon(self) -> None:
        look = self._look
        if look is None:
            self._icon.hide()
            return
        size = self.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        self._icon.setPixmap(tone_icon(look.icon, look.tone, size).pixmap(size, size))
        self._icon.show()
