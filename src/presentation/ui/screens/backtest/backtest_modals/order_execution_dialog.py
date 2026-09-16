"""Backtest order-execution settings — the shared `ChecklistOverlay`, plus one
cross-row rule this class keeps.

`EPIC-015` §4c hosted `CheckboxList.qml`; `EPIC-025` PR 4.3f replaced it with
`kit.ChecklistOverlay` (ADR D21). What did **not** move, in either direction, is
the rule: two of these four rows are mutually exclusive, the widget knows
nothing about it, and `_rows()`/`_on_toggled()` are where it lives — exactly
where the pre-QML `_sync()` kept it. Moving the rendering never moves the rule.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    ChecklistItem,
    ChecklistOverlay,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "ORDER EXECUTION"

_EXECUTION_TRIGGERS = (
    ("On bar close", True, ""),
    ("On order fill", True, ""),
    (
        "On every tick of the historical bar",
        False,
        (
            "This mode uses 1-second candles, entirely separate from the "
            "candles you've synced at other timeframes — a separate sync "
            "of 1-second data will be required."
        ),
    ),
    ("On every tick of the real-time bar", True, ""),
)

#: The one row a user can actually toggle. Its key is this index as a string —
#: `ChecklistOverlay` does not know these are execution triggers, only that
#: rows have string keys.
_HISTORICAL_TICK_INDEX = 2
_HISTORICAL_TICK_KEY = str(_HISTORICAL_TICK_INDEX)
_BAR_CLOSE_KEY = "0"
_HISTORICAL_TICK_MODE = "HISTORICAL_TICK"
_BAR_CLOSE_MODE = "BAR_CLOSE"


class OrderExecutionDialog(ChecklistOverlay):
    """@brief When strategy re-evaluation runs."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        super().__init__(_TITLE, parent=parent)
        self.setObjectName("orderExecutionModal")
        self.resize(400, 250)
        self.toggled.connect(self._on_toggled)
        view_model.executionModeChanged.connect(self.refresh)
        self.refresh()

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        """Renders the four triggers against the screen's execution mode."""
        is_realtime = self._vm.executionMode == _HISTORICAL_TICK_MODE
        # Only these two rows are ever driven by executionMode — the other two
        # have no live source and stay unchecked, matching the shape every
        # version of this dialog has had.
        checked_by_key = {
            _BAR_CLOSE_KEY: not is_realtime,
            _HISTORICAL_TICK_KEY: is_realtime,
        }
        self.set_items(
            [
                ChecklistItem(
                    key=str(index),
                    label=text,
                    checked=checked_by_key.get(str(index), False),
                    locked=locked,
                    tooltip=tooltip,
                )
                for index, (text, locked, tooltip) in enumerate(_EXECUTION_TRIGGERS)
            ]
        )

    def _on_toggled(self, key: str, checked: bool) -> None:
        if key != _HISTORICAL_TICK_KEY:
            return
        self._vm.executionMode = _HISTORICAL_TICK_MODE if checked else _BAR_CLOSE_MODE
