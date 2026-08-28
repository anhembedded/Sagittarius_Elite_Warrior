"""State behind `StatGrid.qml` — a read-only 2-column grid of stat cards."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QObject, Signal


class StatGridVM(QObject):
    """
    @brief Extended-metrics readout, as data. No selection, no interaction —
    a raw dump of numbers, which is the entire content of this widget.
    """

    cardsChanged = Signal()

    def __init__(
        self,
        get_cards: Callable[[], Sequence[dict[str, object]]],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_cards = get_cards
        self._cards: list[dict[str, object]] = []

    @Property("QVariantList", notify=cardsChanged)
    def cards(self) -> list[dict[str, object]]:
        return self._cards

    def refresh(self) -> None:
        self._cards = [
            {
                "title": str(card.get("title", "")).upper(),
                "value": str(card.get("value", "")),
                "suffix": str(card.get("suffix", "")),
                # `Tone` (NEUTRAL/POSITIVE/NEGATIVE) as a name, not the enum
                # itself — QML reads plain data, not a Python type.
                "tone": getattr(card.get("valueTone"), "name", "NEUTRAL"),
            }
            for card in self._get_cards()
        ]
        self.cardsChanged.emit()
