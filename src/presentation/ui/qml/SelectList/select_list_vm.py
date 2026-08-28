"""State behind `SelectList.qml` — one row per option, at most one selected.

Generalised from `TimezonePickerVM` (`EPIC-015` bậc 1): both were the exact
same shape (options -> rows with a computed `selected`, click -> emit -> the
screen decides what closing means) with different words on the buttons. This
is the shared version; `TimezonePickerVM` is deleted, not kept as a
forwarder — the same rule `EPIC-014` and `EPIC-006F` both followed.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QObject, Signal, Slot

_ID_KEY = "id"
_LABEL_KEY = "label"
_SUBTITLE_KEY = "subtitle"


class SelectListVM(QObject):
    """
    @brief A list of choices, at most one of them current.

    @details Callback-constructed, not handed a screen ViewModel — same
    reasoning as `SymbolPreferences.bind_picker` (`EPIC-014`): this widget has
    no opinion about which screen owns it, and its tests need two lambdas, no
    `QApplication`.

    `selectable` turns off the "current" highlight and the click handler —
    the read-only-bullet-list shape (`limitations_dialog`) is this shape with
    one flag off, not a second component.
    """

    optionsChanged = Signal()
    chosen = Signal(str)

    def __init__(
        self,
        get_options: Callable[[], Sequence[dict[str, str]]],
        get_current: Callable[[], str] | None = None,
        *,
        selectable: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_options = get_options
        self._get_current = get_current
        self._selectable = selectable
        self._rows: list[dict[str, object]] = []

    @Property(bool, constant=True)
    def selectable(self) -> bool:
        return self._selectable

    @Property("QVariantList", notify=optionsChanged)
    def rows(self) -> list[dict[str, object]]:
        """One entry per option: `id`, `label`, `subtitle`, `selected`.

        @details `selected` is computed here, not in the `.qml` delegate — a
        delegate asking "am I current?" is a rule no test in this repo's gate
        can reach (`EPIC-015` §4b finding 1).
        """
        return self._rows

    def refresh(self) -> None:
        current = self._get_current() if self._get_current is not None else None
        self._rows = [
            {
                _ID_KEY: str(option.get(_ID_KEY, "")),
                _LABEL_KEY: str(option.get(_LABEL_KEY, ""))
                or str(option.get(_ID_KEY, "")),
                _SUBTITLE_KEY: str(option.get(_SUBTITLE_KEY, "")),
                "selected": self._selectable
                and current is not None
                and str(option.get(_ID_KEY, "")) == current,
            }
            for option in self._get_options()
        ]
        self.optionsChanged.emit()

    @Slot(str)
    def choose(self, option_id: str) -> None:
        if self._selectable and option_id:
            self.chosen.emit(option_id)
