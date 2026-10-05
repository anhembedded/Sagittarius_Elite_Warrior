"""`Readout` and `ReadoutSlot` — a label–value read-out whose rows can change
while the screen runs (`EPIC-033N`).

The Engine's `ReadoutForm` lays out label–value rows the platform's way (a
`QFormLayout`, values right-aligned in one column) and writes each value
through the application's formatter, so a price in a read-out reads as it
does in a table. Its rows are fixed when it is built. Some read-outs know
their rows only later: an account summary learns whether it counts in USDT or
in USD (Multi-Assets) from its first read, and an order form's units follow
the symbol it is trading. A `Readout` says what rows to show and their
values; a `ReadoutSlot` builds the form for those rows, keeps it while the
rows stay the same — every value update — and builds a new one when they
change. A read-out with fixed rows uses `ReadoutForm` directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from PySide6.QtWidgets import QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnSpec,
    DisplayValue,
    ReadoutForm,
)


@dataclass(frozen=True)
class Readout:
    """The rows of a read-out and the value each shows."""

    specs: tuple[ColumnSpec, ...]
    values: Mapping[str, DisplayValue] = field(default_factory=dict)


class ReadoutSlot(QWidget):  # base-exempt: a container, not a surface
    """Holds the `ReadoutForm` for the rows last shown; empty until then."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._form: ReadoutForm | None = None
        self._specs: tuple[ColumnSpec, ...] = ()

    def show_readout(self, readout: Readout) -> None:
        """Shows `readout`, building a new form only when its rows changed."""
        if self._form is None or readout.specs != self._specs:
            self._replace_form(readout.specs)
        if self._form is not None:
            self._form.set_values(readout.values)

    def clear(self) -> None:
        """No rows: the read-out has nothing to say yet."""
        self._replace_form(())

    @property
    def keys(self) -> tuple[str, ...]:
        """The rows shown, top to bottom."""
        return tuple(spec.key for spec in self._specs)

    def value_text(self, key: str) -> str | None:
        """What row `key` shows, or `None` when there is no such row."""
        if self._form is None or key not in self.keys:
            return None
        return self._form.value_text(key)

    def _replace_form(self, specs: tuple[ColumnSpec, ...]) -> None:
        if self._form is not None:
            self._layout.removeWidget(self._form)
            self._form.deleteLater()
            self._form = None
        self._specs = specs
        if specs:
            self._form = ReadoutForm(specs, APP_VALUE_FORMATTER, self)
            self._layout.addWidget(self._form)
