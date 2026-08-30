"""State behind `StatCardRow.qml` — the primary performance stat-card row
(`BackTestViewModel.primaryStatCards`).

Needs a widget VM per `qml-rule.md` §1.3's second question ("does `.qml`
need a derived value not already on the screen ViewModel?"): `.qml` cannot
read a Python `Tone` enum member directly.
`BackTestViewModel.primaryStatCards` still carries raw `Tone.NEUTRAL`/
`POSITIVE`/`NEGATIVE` objects under the `valueTone`/`badgeTone` keys — the
same shape `stat_cards_to_qml()`
(`screens/backtest/logic/performance_metrics_view.py`) produces for the
QtWidgets `StatCard.set_value(..., tone=...)`/`set_badge(..., tone=...)`
calls this widget replaces. QML reads plain data, not a Python `Enum`, so
each card's tone is converted to the lowercase name `StatCard.qml`'s own
`tone`/`badgeTone` properties compare against (`"positive"`/`"negative"`/
`"neutral"`) — the same answer `StatGridVM.refresh()` already gives for the
identical enum, one directory over. That VM uppercases `Tone.name`
(`StatGrid.qml` compares `"POSITIVE"`); this one lowercases it
(`StatCard.qml` compares `"positive"`) — not extracted into one shared
helper both would call, since the two `.qml` files independently chose
different string cases and neither is "the" canonical one.

`title`/`value`/`suffix`/`badgeText` pass through unchanged — no uppercase
here, unlike `StatGridVM`, because `StatCard.qml` already uppercases its
own title (`text: root.title.toUpperCase()`).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from PySide6.QtCore import Property, QObject, Signal
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone


def _tone_name(value: object) -> str:
    """`Tone.POSITIVE` -> `"positive"`. Anything else — a missing key,
    `None`, or a value that is not a `Tone` at all — falls back to
    `"neutral"`, the same "no verdict" default every card dict upstream
    already uses when a tone is left unset."""
    if isinstance(value, Tone):
        return value.name.lower()
    return "neutral"


class StatCardRowVM(QObject):
    """
    @brief The dynamic row of primary performance stat cards, as QML-ready
    data. No selection, no interaction — `BackTestTopPanel` still owns
    show/hide (stat cards vs. result box) and the "expand extended
    metrics" action; this VM only carries the row's own content.
    """

    cardsChanged = Signal()

    def __init__(
        self,
        get_cards: Callable[[], Sequence[Mapping[str, object]]],
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
                "title": str(card.get("title", "")),
                "value": str(card.get("value", "")),
                "suffix": str(card.get("suffix", "")),
                "tone": _tone_name(card.get("valueTone")),
                "badgeText": str(card.get("badgeText", "")),
                "badgeTone": _tone_name(card.get("badgeTone")),
            }
            for card in self._get_cards()
        ]
        self.cardsChanged.emit()
