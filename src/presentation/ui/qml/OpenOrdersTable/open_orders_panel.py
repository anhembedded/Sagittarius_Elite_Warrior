"""Embeds `OpenOrdersTable.qml` inline in a screen's workspace.

@details Same shape as `PositionsPanel`.

`EPIC-023A` moved this out of `screens/trading/trading_widgets/` into this
already-shared `qml/OpenOrdersTable/` directory — see `positions_panel.py`'s
own docstring for the full reasoning (Dev Board needed the same widget;
reaching into a sibling screen's private dir would have been the
cross-screen-import anti-pattern `architecture-rule.md` §5 documents).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Panel, StyleRole
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_orders_vm import (
    OpenOrdersVM,
)

_QML = Path(__file__).resolve().parent / "OpenOrdersTable.qml"


class OpenOrdersPanel(Panel):
    """The Open Orders table, embedded (not modal)."""

    #: `EPIC-024B` §0 — re-exposes `OpenOrdersVM.cancelRequested`: a row
    #: action a panel forwards to whichever screen hosts it, identified by
    #: the row it was pressed on.
    cancelRequested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body_layout.setContentsMargins(12, 12, 12, 12)
        self.body_layout.setSpacing(8)

        self._vm = OpenOrdersVM(parent=self)
        self._vm.cancelRequested.connect(self.cancelRequested)
        # Same shape as `PositionsPanel`: the scene sits on this `Panel`'s
        # SURFACE and clears to that token (BUG-115).
        self._surface = QuickSurface(
            _QML,
            surface=StyleRole.SURFACE,
            context={"vm": self._vm},
            object_name="openOrdersTableQuick",
        )
        self.body_layout.addWidget(self._surface, 1)

    def set_rows(self, rows: list[OpenOrderRow]) -> None:
        self._vm.set_rows(rows)

    @property
    def root_object(self) -> QObject:
        """The loaded QML root, for tests to `findChild`/`qml_item` into by
        `objectName` — the same contract every `qml/` panel exposes."""
        return self._surface.root_object
