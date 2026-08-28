"""State and rules behind `TimezonePicker.qml`. No Qt GUI, no QML import."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QObject, Signal, Slot

_ID_KEY = "id"
_LABEL_KEY = "label"


class TimezonePickerVM(QObject):
    """
    @brief The display-timezone chooser, as data.

    @details Callback-constructed rather than handed the screen's ViewModel,
    for the same reason `SymbolPickerOverlay` is (`EPIC-014`): the widget then
    has no opinion about which screen owns it, and its tests need nothing but
    two lambdas — no `QApplication`, no QML, no screen.

    Re-reads on `refresh()` rather than caching at construction, because the
    dialog is built once and reused, and the current timezone changes between
    opens.
    """

    optionsChanged = Signal()
    chosen = Signal(str)

    def __init__(
        self,
        get_options: Callable[[], Sequence[dict[str, str]]],
        get_current: Callable[[], str],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_options = get_options
        self._get_current = get_current
        self._rows: list[dict[str, str]] = []

    @Property("QVariantList", notify=optionsChanged)
    def rows(self) -> list[dict[str, str]]:
        """One entry per timezone: `id`, `label`, and `selected`.

        @details `selected` is computed here, not in QML. A `Repeater`
        delegate asking "am I the current one?" is a rule, and rules that
        live in `.qml` are rules no test in this repo's gate can reach.
        """
        return self._rows

    def refresh(self) -> None:
        current = self._get_current()
        self._rows = [
            {
                _ID_KEY: str(option.get(_ID_KEY, "")),
                _LABEL_KEY: str(option.get(_LABEL_KEY, ""))
                or str(option.get(_ID_KEY, "")),
                "selected": str(option.get(_ID_KEY, "")) == current,
            }
            for option in self._get_options()
        ]
        self.optionsChanged.emit()

    @Slot(str)
    def choose(self, timezone_id: str) -> None:
        """Called from QML. Emits rather than writing through, so the screen
        decides what choosing means — and so this stays testable alone."""
        if timezone_id:
            self.chosen.emit(timezone_id)
