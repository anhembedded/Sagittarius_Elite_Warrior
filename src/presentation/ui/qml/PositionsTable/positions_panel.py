"""Embeds `PositionsTable.qml` inline in a screen's workspace.

@details A `QQuickWidget` hosted directly on a `kit.Panel`, not through
`QmlOverlay` (this is not a dialog) — the shape `EPIC-015` Phase 2
established for an embedded QML table.

`EPIC-023A` moved this out of `screens/trading/trading_widgets/` into this
already-shared `qml/PositionsTable/` directory (alongside the QML file it
hosts, `positions_row.py` and `positions_vm.py`): the class itself had
nothing Trading-specific in it, and Dev Board needed the exact same widget
— importing across from `screens/dashboard/` into a sibling screen's
private `trading_widgets/` dir would have been the cross-screen-import
anti-pattern `architecture-rule.md` §5 documents (`data_management_widgets.py`).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Panel, StyleRole
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_vm import (
    PositionsVM,
)

_QML = Path(__file__).resolve().parent / "PositionsTable.qml"


class PositionsPanel(Panel):
    """The Positions table, embedded (not modal)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body_layout.setContentsMargins(12, 12, 12, 12)
        self.body_layout.setSpacing(8)

        self._vm = PositionsVM(parent=self)
        # The scene sits on this `Panel`'s SURFACE — `QuickSurface` clears to
        # that same token (BUG-115), so the table body is the panel colour on
        # a real screen, not black.
        self._surface = QuickSurface(
            _QML,
            surface=StyleRole.SURFACE,
            context={"vm": self._vm},
            object_name="positionsTableQuick",
        )
        self.body_layout.addWidget(self._surface, 1)

    def set_rows(self, rows: list[PositionRow]) -> None:
        self._vm.set_rows(rows)

    @property
    def root_object(self) -> QObject:
        """The loaded QML root, for tests to `findChild`/`qml_item` into by
        `objectName` — the same contract every `qml/` panel exposes."""
        return self._surface.root_object
