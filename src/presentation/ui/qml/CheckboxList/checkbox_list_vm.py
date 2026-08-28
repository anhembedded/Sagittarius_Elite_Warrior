"""State behind `CheckboxList.qml` — independently toggleable rows, some
optionally locked, with an optional cross-row exclusivity rule."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QObject, Signal, Slot


class CheckboxListVM(QObject):
    """
    @brief A list of independently checkable rows.

    @details Covers two shapes from one class: `indicator_picker_dialog`
    (rows and their checked state both come from a live model — no fixed
    row set, no cross-row rule) and `order_execution_dialog` (a fixed row
    set, some rows locked, and two rows are mutually exclusive). The second
    is not a special case bolted on — `toggled` is a plain signal the screen
    listens to, and enforcing "only one of these two" is the screen's
    business rule to enforce by calling `refresh()` back with new state, the
    same way `OrderExecutionDialog._sync()` already did. This VM only
    renders whatever state it is handed and reports raw toggles.
    """

    rowsChanged = Signal()
    #: (key, checked) — the screen decides what a toggle means.
    toggled = Signal(str, bool)

    def __init__(
        self,
        get_rows: Callable[[], Sequence[dict[str, object]]],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_rows = get_rows
        self._rows: list[dict[str, object]] = []

    @Property("QVariantList", notify=rowsChanged)
    def rows(self) -> list[dict[str, object]]:
        """One entry per row: `key`, `label`, `checked`, `locked`, `tooltip`."""
        return self._rows

    def refresh(self) -> None:
        self._rows = [
            {
                "key": str(row.get("key", "")),
                "label": str(row.get("label", "")),
                "checked": bool(row.get("checked", False)),
                "locked": bool(row.get("locked", False)),
                "tooltip": str(row.get("tooltip", "")),
            }
            for row in self._get_rows()
        ]
        self.rowsChanged.emit()

    @Slot(str, bool)
    def toggle(self, key: str, checked: bool) -> None:
        self.toggled.emit(key, checked)
